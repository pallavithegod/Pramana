"""Validation and trust metadata for an immutable hosted SQLite snapshot."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from functools import lru_cache
from pathlib import Path

from collectors.storage import DB_PATH, REPO_ROOT, read_only_enabled


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path() -> Path:
    configured = os.environ.get("APIX_SNAPSHOT_MANIFEST", "data/deploy/snapshot-manifest.json")
    path = Path(configured)
    return path if path.is_absolute() else REPO_ROOT / path


@lru_cache(maxsize=1)
def validated_manifest() -> dict:
    """Load the manifest and prove that it describes the deployed DB bytes."""
    if not read_only_enabled():
        raise RuntimeError("Snapshot validation is only available in APIX_READ_ONLY mode")
    manifest_path = _manifest_path()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Snapshot manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported snapshot manifest schema")

    stated_manifest_hash = manifest.get("manifest_sha256")
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    actual_manifest_hash = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if not stated_manifest_hash or not hmac.compare_digest(
        stated_manifest_hash, actual_manifest_hash
    ):
        raise ValueError("Snapshot manifest checksum mismatch")

    if not DB_PATH.is_file():
        raise FileNotFoundError(f"Snapshot database not found: {DB_PATH}")
    actual_db_hash = _sha256_file(DB_PATH)
    if not hmac.compare_digest(manifest["database"]["sha256"], actual_db_hash):
        raise ValueError("Snapshot database checksum mismatch")

    uri = f"{DB_PATH.resolve().as_uri()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as conn:
        result = conn.execute("PRAGMA quick_check").fetchone()[0]
    if result != "ok":
        raise ValueError(f"SQLite quick_check failed: {result}")
    return manifest


def hosted_ledger_status() -> dict:
    """Truthful ledger status when raw captures intentionally remain off-cloud."""
    manifest = validated_manifest()
    ledger = manifest["ledger"]
    return {
        "entries": ledger["entries"],
        "head": ledger["head"],
        "last_sealed_at": ledger["last_sealed_at"],
        "intact": ledger["verified_at_publish"],
        "detail": (
            "Ledger chain and raw-file coverage were verified on the scraper node "
            f"when this immutable snapshot was published ({manifest['generated_at']})."
        ),
        "raw_files": ledger["raw_files"],
        "sealed_files": ledger["sealed_files"],
        "unsealed_files": ledger["unsealed_files"],
        "coverage_complete": ledger["coverage_complete"],
        "verification_scope": "publish-time scraper-node verification",
        "snapshot_sha256": manifest["database"]["sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
    }
