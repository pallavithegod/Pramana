"""Tamper-evident scrape-evidence ledger (PLAN §3.4b).

Append-only hash chain over the raw evidence archive (data/raw/**): each entry
binds a file's SHA-256 to the previous entry's hash, so editing or removing ANY
archived response after the fact breaks the chain arithmetic — Eurostat WIN's
open provenance problem, answered with ~100 lines.

    ledger seal    append entries for archived files not yet in the chain
    ledger verify  recompute every hash; report the first broken link, if any

Ledger file: data/ledger.jsonl — one canonical-JSON entry per line:
    {seq, path, sha256, ts, prev, entry}
    entry = sha256(canonical_json({seq, path, sha256, ts, prev}))
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from .storage import RAW_DIR, REPO_ROOT

LEDGER_PATH = REPO_ROOT / "data" / "ledger.jsonl"
GENESIS = "0" * 64


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _entry_hash(body: dict) -> str:
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def _read_ledger() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    with open(LEDGER_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def seal() -> int:
    """Append chain entries for raw files not yet sealed. Returns count added."""
    entries = _read_ledger()
    sealed = {e["path"] for e in entries}
    prev = entries[-1]["entry"] if entries else GENESIS
    seq = entries[-1]["seq"] + 1 if entries else 0

    new = 0
    files = sorted(p for p in RAW_DIR.rglob("*") if p.is_file())
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "a", encoding="utf-8") as out:
        for p in files:
            rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
            if rel in sealed:
                continue
            body = {
                "seq": seq,
                "path": rel,
                "sha256": _sha256_file(p),
                "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                "prev": prev,
            }
            body["entry"] = _entry_hash(
                {k: body[k] for k in ("seq", "path", "sha256", "ts", "prev")}
            )
            out.write(json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n")
            prev = body["entry"]
            seq += 1
            new += 1
    return new


def verify() -> tuple[bool, str]:
    """Recompute the whole chain and every file hash. (ok, message)."""
    entries = _read_ledger()
    if not entries:
        return True, "ledger empty — nothing sealed yet"
    prev = GENESIS
    for e in entries:
        expected = _entry_hash({k: e[k] for k in ("seq", "path", "sha256", "ts", "prev")})
        if e["prev"] != prev:
            return False, f"chain broken at seq {e['seq']}: prev-hash mismatch"
        if e["entry"] != expected:
            return False, f"chain broken at seq {e['seq']}: entry hash mismatch"
        f = REPO_ROOT / e["path"]
        if not f.exists():
            return False, f"evidence file missing: {e['path']} (seq {e['seq']})"
        if _sha256_file(f) != e["sha256"]:
            return False, f"evidence file MODIFIED after sealing: {e['path']} (seq {e['seq']})"
        prev = e["entry"]
    return True, f"chain intact: {len(entries)} entries, head {prev[:16]}…"


def coverage(entries: list[dict] | None = None) -> dict:
    """Report whether every current raw evidence file has a ledger entry."""
    ledger_entries = _read_ledger() if entries is None else entries
    sealed = {entry["path"] for entry in ledger_entries}
    raw = {
        str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        for path in RAW_DIR.rglob("*")
        if path.is_file()
    }
    return {
        "raw_files": len(raw),
        "sealed_files": len(raw & sealed),
        "unsealed_files": len(raw - sealed),
        "coverage_complete": raw <= sealed,
    }


def status() -> dict:
    entries = _read_ledger()
    ok, msg = verify()
    return {
        "entries": len(entries),
        "head": entries[-1]["entry"] if entries else None,
        "last_sealed_at": entries[-1]["ts"] if entries else None,
        "intact": ok,
        "detail": msg,
        **coverage(entries),
    }


def _print_verification() -> bool:
    ok, msg = verify()
    print(("OK  " if ok else "FAIL ") + msg)
    cov = coverage()
    complete = cov["coverage_complete"]
    print(
        f"{'OK  ' if complete else 'FAIL '}"
        f"coverage: {cov['sealed_files']}/{cov['raw_files']} raw files sealed"
    )
    return ok and complete


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "seal":
        n = seal()
        print(f"sealed {n} new evidence files")
        sys.exit(0 if _print_verification() else 1)
    elif cmd == "verify":
        sys.exit(0 if _print_verification() else 1)
    else:
        print(json.dumps(status(), indent=2))


if __name__ == "__main__":
    main()
