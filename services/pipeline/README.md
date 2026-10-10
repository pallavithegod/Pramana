# Pipeline status — local MVP

The current nightly pipeline is operational without Prefect:

- Windows Task Scheduler calls `scripts/nightly/_collect.ps1`;
- Pydantic validates `collectors.models.FareQuote` during collection;
- `quote_fingerprint` provides insert-time deduplication;
- SQLite is the serving store and daily Parquet files form the analytical lake;
- raw responses are archived before parsing;
- the nightly wrapper seals new raw captures into the hash-chained evidence
  ledger and reports collection and ledger coverage.

As of 13 September 2026, the ledger covers 2,643/2,643 raw captures and verifies
intact. This is a dated prototype result, not a cloud-production SLA.

Prefect, Soda, multi-writer Postgres and hosted alerting are not part of the
current MVP. Any future orchestration or storage migration must preserve the
append-only evidence trail, source-policy decisions and reproducible index path.
