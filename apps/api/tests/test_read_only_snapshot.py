import hashlib
import json
import sqlite3

import pytest


def _manifest(db_path, *, ledger_entries=3):
    db_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
    body = {
        "schema_version": 1,
        "generated_at": "2026-09-13T12:00:00+00:00",
        "source_mode": "local-scraper-node",
        "serving_mode": "immutable-read-only-snapshot",
        "database": {
            "path": "snapshot.sqlite",
            "sha256": db_hash,
            "bytes": db_path.stat().st_size,
        },
        "ledger": {
            "entries": ledger_entries,
            "head": "a" * 64,
            "last_sealed_at": "2026-09-13T11:00:00+00:00",
            "verified_at_publish": True,
            "raw_files": ledger_entries,
            "sealed_files": ledger_entries,
            "unsealed_files": 0,
            "coverage_complete": True,
        },
    }
    body["manifest_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return body


def test_storage_read_only_connection_rejects_writes(tmp_path, monkeypatch):
    from collectors import storage

    db_path = tmp_path / "snapshot.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE sample (value INTEGER)")
        conn.execute("INSERT INTO sample VALUES (1)")

    monkeypatch.setattr(storage, "DB_PATH", db_path)
    monkeypatch.setenv("APIX_READ_ONLY", "1")
    conn = storage.connect()
    assert conn.execute("SELECT value FROM sample").fetchone() == (1,)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("INSERT INTO sample VALUES (2)")
    conn.close()


def test_snapshot_manifest_validates_database_and_ledger(tmp_path, monkeypatch):
    from api import snapshot

    db_path = tmp_path / "snapshot.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE sample (value INTEGER)")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest(db_path)), encoding="utf-8")

    monkeypatch.setattr(snapshot, "DB_PATH", db_path)
    monkeypatch.setenv("APIX_READ_ONLY", "1")
    monkeypatch.setenv("APIX_SNAPSHOT_MANIFEST", str(manifest_path))
    snapshot.validated_manifest.cache_clear()

    status = snapshot.hosted_ledger_status()
    assert status["intact"] is True
    assert status["coverage_complete"] is True
    assert status["verification_scope"] == "publish-time scraper-node verification"


def test_snapshot_manifest_rejects_modified_database(tmp_path, monkeypatch):
    from api import snapshot

    db_path = tmp_path / "snapshot.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE sample (value INTEGER)")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest(db_path)), encoding="utf-8")
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO sample VALUES (1)")

    monkeypatch.setattr(snapshot, "DB_PATH", db_path)
    monkeypatch.setenv("APIX_READ_ONLY", "1")
    monkeypatch.setenv("APIX_SNAPSHOT_MANIFEST", str(manifest_path))
    snapshot.validated_manifest.cache_clear()

    with pytest.raises(ValueError, match="database checksum"):
        snapshot.validated_manifest()
