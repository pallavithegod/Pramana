"""Publish a consistent, verified SQLite snapshot without modifying source data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from collectors import ledger
from collectors.storage import DB_PATH, REPO_ROOT

DEFAULT_OUTPUT = REPO_ROOT / "data" / "deploy" / "apix.snapshot.sqlite"
DEFAULT_MANIFEST = REPO_ROOT / "data" / "deploy" / "snapshot-manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scalar(conn: sqlite3.Connection, sql: str):
    return conn.execute(sql).fetchone()[0]


def build_api_response_cache(snapshot_path: Path) -> int:
    """Materialize immutable analytical responses on the scraper node.

    The public Render process should serve a verified snapshot, not spend its
    cold-start CPU rebuilding pandas indices for every dashboard section.
    """
    from api import main as api_main
    from collectors import storage

    previous_db = storage.DB_PATH
    previous_api_db = api_main.DB_PATH
    previous_read_only = os.environ.get("APIX_READ_ONLY")
    try:
        os.environ["APIX_READ_ONLY"] = "0"
        storage.DB_PATH = snapshot_path
        api_main.DB_PATH = snapshot_path
        api_main._CACHE.clear()
        api_main._SNAPSHOT_RESPONSES = None

        # Headline and booking-window indices.
        api_main.get_apix_index(limit=100, page=1, leadtime_code=None)
        for leadtime in (1, 7, 15, 30, 45):
            api_main.get_apix_index(limit=100, page=1, leadtime_code=leadtime)

        # Shared analytical and trust feeds.
        api_main.get_route_heatmap()
        api_main.get_source_health()
        api_main.get_nowcast()
        api_main.get_prism_decomposition()
        api_main.get_prism_events(route_code=None)
        for days in (7, 14, 30):
            api_main.get_competition(days=days)

        with closing(sqlite3.connect(snapshot_path)) as conn:
            routes = [
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT origin||'-'||dest FROM fare_quotes ORDER BY 1"
                )
            ]

        # Page-specific route payloads. These are derived from the same sealed
        # quotes and are stored inside the database covered by the manifest hash.
        for route in routes:
            api_main.get_route_series(route_code=route)
            api_main.get_fare_ladder(route_code=route)
            api_main.get_fair_fare_panel(route_code=route)

        rows = [
            (key, json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
            for key, (_, payload) in sorted(api_main._CACHE.items())
        ]
        with closing(sqlite3.connect(snapshot_path)) as conn:
            conn.execute(
                "CREATE TABLE api_response_cache ("
                "cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            conn.executemany(
                "INSERT INTO api_response_cache (cache_key, payload) VALUES (?, ?)",
                rows,
            )
            conn.commit()
        return len(rows)
    finally:
        api_main._CACHE.clear()
        api_main._SNAPSHOT_RESPONSES = None
        api_main.DB_PATH = previous_api_db
        storage.DB_PATH = previous_db
        if previous_read_only is None:
            os.environ.pop("APIX_READ_ONLY", None)
        else:
            os.environ["APIX_READ_ONLY"] = previous_read_only


def publish(output: Path, manifest_path: Path) -> dict:
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"Source database not found: {DB_PATH}")

    ledger_ok, ledger_detail = ledger.verify()
    coverage = ledger.coverage()
    if not ledger_ok or not coverage["coverage_complete"]:
        raise RuntimeError(
            "Refusing to publish an unverifiable snapshot: "
            f"{ledger_detail}; coverage={coverage['sealed_files']}/{coverage['raw_files']}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    source_copy = output.with_suffix(output.suffix + ".source.tmp")
    for path in (temporary, source_copy):
        if path.exists():
            path.unlink()

    source_uri = f"{DB_PATH.resolve().as_uri()}?mode=ro"
    try:
        with (
            closing(sqlite3.connect(source_uri, uri=True)) as source,
            closing(sqlite3.connect(source_copy)) as dest,
        ):
            source.backup(dest)

        # Rebuild, rather than DROP, so pages from unrelated local tables (for
        # example demo account hashes) cannot remain recoverable in free pages.
        copied_uri = f"{source_copy.resolve().as_uri()}?mode=ro&immutable=1"
        with (
            closing(sqlite3.connect(copied_uri, uri=True)) as source,
            closing(sqlite3.connect(temporary)) as dest,
        ):
            source.row_factory = sqlite3.Row
            source_tables = [
                row["name"]
                for row in source.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
            ]
            table_sql = source.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='fare_quotes'"
            ).fetchone()
            if not table_sql:
                raise RuntimeError("Source database has no fare_quotes table")
            dest.execute(table_sql["sql"])

            columns = [row["name"] for row in source.execute("PRAGMA table_info(fare_quotes)")]
            quoted_columns = ",".join(f'"{name}"' for name in columns)
            placeholders = ",".join("?" for _ in columns)
            cursor = source.execute(f"SELECT {quoted_columns} FROM fare_quotes")
            while batch := cursor.fetchmany(1_000):
                dest.executemany(
                    f"INSERT INTO fare_quotes ({quoted_columns}) VALUES ({placeholders})",
                    [tuple(row) for row in batch],
                )
            for row in source.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name='fare_quotes' AND sql IS NOT NULL"
            ):
                dest.execute(row["sql"])
            dest.commit()

        api_cache_entries = build_api_response_cache(temporary)

        with closing(
            sqlite3.connect(f"{temporary.resolve().as_uri()}?mode=ro", uri=True)
        ) as snapshot:
            integrity = scalar(snapshot, "PRAGMA integrity_check")
            if integrity != "ok":
                raise RuntimeError(f"Snapshot integrity_check failed: {integrity}")
            database = {
                "path": str(output.relative_to(REPO_ROOT)).replace("\\", "/"),
                "sha256": sha256_file(temporary),
                "bytes": temporary.stat().st_size,
                "fare_quotes": scalar(snapshot, "SELECT COUNT(*) FROM fare_quotes"),
                "collection_dates": scalar(
                    snapshot, "SELECT COUNT(DISTINCT substr(collected_at,1,10)) FROM fare_quotes"
                ),
                "first_collected_at": scalar(snapshot, "SELECT MIN(collected_at) FROM fare_quotes"),
                "last_collected_at": scalar(snapshot, "SELECT MAX(collected_at) FROM fare_quotes"),
                "api_cache_entries": api_cache_entries,
                "included_tables": ["fare_quotes", "api_response_cache"],
                "excluded_source_tables": [name for name in source_tables if name != "fare_quotes"],
            }
        os.replace(temporary, output)
    finally:
        for path in (temporary, source_copy):
            if path.exists():
                path.unlink()

    entries = ledger._read_ledger()
    body = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_mode": "local-scraper-node",
        "serving_mode": "immutable-read-only-snapshot",
        "database": database,
        "ledger": {
            "path": str(ledger.LEDGER_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sha256": sha256_file(ledger.LEDGER_PATH),
            "entries": len(entries),
            "head": entries[-1]["entry"] if entries else None,
            "last_sealed_at": entries[-1]["ts"] if entries else None,
            "verified_at_publish": ledger_ok,
            **coverage,
        },
    }
    body["manifest_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return body


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    result = publish(args.output.resolve(), args.manifest.resolve())
    print(
        f"Prepared {result['database']['fare_quotes']:,} quotes at "
        f"{result['database']['path']} ({result['database']['sha256'][:16]}...)"
    )
    print(f"Materialized {result['database']['api_cache_entries']:,} API responses")
    print(
        f"Ledger verified: {result['ledger']['sealed_files']:,}/"
        f"{result['ledger']['raw_files']:,} raw files sealed"
    )


if __name__ == "__main__":
    main()
