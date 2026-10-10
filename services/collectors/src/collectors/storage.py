"""Storage: SQLite serving store plus a daily Parquet analytical lake.

Raw responses are archived to data/raw/<source>/<date>/ before parsing. The
nightly workflow seals that evidence into the hash-chain ledger.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .models import FareQuote

REPO_ROOT = Path(__file__).resolve().parents[4]
LAKE_DIR = REPO_ROOT / "data" / "lake"
RAW_DIR = REPO_ROOT / "data" / "raw"


def _configured_db_path() -> Path:
    configured = os.environ.get("APIX_DB_PATH")
    if not configured:
        return LAKE_DIR / "apix.sqlite"
    path = Path(configured)
    return path if path.is_absolute() else REPO_ROOT / path


DB_PATH = _configured_db_path()

DDL = """
CREATE TABLE IF NOT EXISTS fare_quotes (
    quote_fingerprint TEXT PRIMARY KEY,
    carrier           TEXT NOT NULL,
    flight_no         TEXT,
    origin            TEXT NOT NULL,
    dest              TEXT NOT NULL,
    departure_date    TEXT NOT NULL,
    collected_at      TEXT NOT NULL,
    lead_days         INTEGER NOT NULL,
    cabin             TEXT NOT NULL,
    nonstop           INTEGER NOT NULL,
    fare_family       TEXT,
    rbd               TEXT,
    total_fare        REAL NOT NULL,
    base_fare         REAL,
    taxes_fees        REAL,
    components        TEXT,
    seats_available   INTEGER,
    integrity_warning TEXT,
    source            TEXT NOT NULL,
    source_tier       TEXT NOT NULL,
    raw_ref           TEXT
);
CREATE INDEX IF NOT EXISTS ix_panel
    ON fare_quotes (carrier, flight_no, departure_date, origin, dest);
CREATE INDEX IF NOT EXISTS ix_route_lead
    ON fare_quotes (origin, dest, lead_days, collected_at);
"""


def read_only_enabled() -> bool:
    """Whether this process is the hosted snapshot viewer, never a collector."""
    return os.environ.get("APIX_READ_ONLY", "0").strip().lower() in {"1", "true", "yes"}


def connect(timeout: float = 10.0, *, read_only: bool | None = None) -> sqlite3.Connection:
    """Single choke-point for opening the lake DB (used by collectors AND the
    API). Concurrency posture (reviewed with an airline backend engineer,
    6 Sep 2026): writes are structurally single-process (the nightly runner is
    the only fare_quotes writer; the API only reads them), so a queue/broker
    would solve a contention we don't have. The real overlap is API reads
    during the nightly write window — WAL lets readers and the one writer
    proceed without blocking, and the timeout makes any residual contention
    wait instead of erroring. A production multi-writer store is outside the
    local MVP and requires an authority-approved deployment design."""
    use_read_only = read_only_enabled() if read_only is None else read_only
    if use_read_only:
        if not DB_PATH.is_file():
            raise FileNotFoundError(f"Read-only APIx snapshot not found: {DB_PATH}")
        immutable = os.environ.get("APIX_SQLITE_IMMUTABLE", "1") == "1"
        query = "mode=ro" + ("&immutable=1" if immutable else "")
        conn = sqlite3.connect(f"{DB_PATH.resolve().as_uri()}?{query}", uri=True, timeout=timeout)
        conn.execute("PRAGMA query_only=ON")
        return conn

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    conn.execute("PRAGMA journal_mode=WAL")  # persistent; idempotent per connect
    conn.execute("PRAGMA synchronous=NORMAL")  # safe with WAL, faster fsync cadence
    return conn


def _connect() -> sqlite3.Connection:
    conn = connect()
    conn.executescript(DDL)
    return conn


def archive_raw(source: str, payload: str | bytes, label: str) -> str:
    """Archive a raw response; returns the relative path used as raw_ref."""
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    out_dir = RAW_DIR / source / day
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%H%M%S")
    path = out_dir / f"{label}_{ts}.raw"
    mode = "wb" if isinstance(payload, bytes) else "w"
    with open(path, mode, encoding=None if isinstance(payload, bytes) else "utf-8") as f:
        f.write(payload)
    return str(path.relative_to(REPO_ROOT))


def save_quotes(quotes: list[FareQuote]) -> int:
    """Insert quotes (idempotent on fingerprint). Also appends today's Parquet partition."""
    if not quotes:
        return 0
    rows = [json.loads(q.model_dump_json()) for q in quotes]
    for r in rows:  # dict column → JSON string for SQLite and Parquet alike
        if r.get("components") is not None:
            r["components"] = json.dumps(r["components"], sort_keys=True)
    conn = _connect()
    cols = list(rows[0].keys())
    placeholders = ",".join("?" for _ in cols)
    inserted = 0
    with conn:
        for r in rows:
            cur = conn.execute(
                f"INSERT OR IGNORE INTO fare_quotes ({','.join(cols)}) VALUES ({placeholders})",
                [r[c] if not isinstance(r[c], bool) else int(r[c]) for c in cols],
            )
            inserted += cur.rowcount
    conn.close()

    day = datetime.now(UTC).strftime("%Y-%m-%d")
    pq_dir = LAKE_DIR / "quotes" / f"date={day}"
    pq_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(
        pq_dir / f"{datetime.now(UTC).strftime('%H%M%S')}.parquet", index=False
    )
    return inserted
