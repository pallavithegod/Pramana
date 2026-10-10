# Hosted data snapshot

This directory is the only approved Git-tracked location for a serving database.
`apix.snapshot.sqlite` and `snapshot-manifest.json` are generated artifacts; the
writable lake and raw captures remain local and ignored.

From the repository root, after the nightly run and ledger verification finish:

```powershell
uv run --project services/collectors python scripts/prepare_render_snapshot.py
```

The command refuses to publish unless the full local raw-evidence set is sealed
and verifies. It uses SQLite's backup API for a transactionally consistent copy,
then records the database hash, ledger hash/head, row counts and collection range.
It never edits `data/lake/apix.sqlite`, `data/raw`, or historical ledger entries.
