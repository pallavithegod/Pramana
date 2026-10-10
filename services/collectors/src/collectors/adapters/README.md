# Adapter development contract

Each direct-site adapter (akasa, spicejet, easemytrip, yatra, airindia) needs its
fare-search XHR/DOM contract captured **manually in a browser first** (DevTools →
Network tab while doing a normal search). Store a sanitized sample response as a
fixture in `tests/fixtures/<source>/`, then write the adapter against the fixture.

Rules:
1. Subclass `BaseCollector`; call `await self.policy.allowed(url)` before every request
   and `self.policy.budget(host).wait()` between requests. Authenticated, contracted
   vendor APIs must use an exact HTTPS endpoint in `LICENSED_API_ENDPOINTS`; this
   exception never applies to general website paths or direct-site adapters.
2. Archive the raw response via `self.archive()` BEFORE parsing.
3. Emit `FareQuote` with `flight_no` populated (PRISM needs the panel key) and
   `base_fare`/`taxes_fees` split when the site exposes it.
4. Tier-3 adapters (MMT/Goibibo/IndiGo — robots-disallowed) are fixture-only:
   implement + test against saved HTML, guarded by `SourceTier.T3_FIXTURE`; the
   runner refuses to execute them live.

## SerpAPI credentials and budget

The current full basket is 20 routes × 5 windows = 100 searches per sweep.
Configure either:

- `SERPAPI_KEYS=key1,key2` for ordered failover across credentials authorized
  for this project; or
- `SERPAPI_KEY=key1` for backward-compatible single-key operation.

When both are present, unique list entries are tried first and the legacy key is
the final fallback. A credential is skipped only after an explicit HTTP 429 or
provider quota-exhaustion response. Other provider/authentication errors stop
the request rather than silently switching identities. Keys are never written
to logs or raw evidence.

The nightly preflight sums the reported remaining quota across configured
authorized accounts and runs the sweep only when at least 100 searches remain.
For a smaller manual sweep:

`collect --adapter serpapi --routes DEL-BOM BLR-DEL --windows 7 30`
