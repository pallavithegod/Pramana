# Deployment Guide — Vercel + Render

This runbook deploys the two public frontends with the Vercel CLI and the
read-only FastAPI viewer on Render. All deployment, Git commit/push, account,
DNS, billing, and secret-entry steps are intentionally performed by the project
owner—not by an automated coding agent.

## Final architecture

```text
Local Windows scraper node                 Hosted judging services
──────────────────────────                 ───────────────────────
Playwright + SerpAPI collectors            Landing page → Vercel
        ↓                                  Dashboard    → Vercel
writable data/lake/apix.sqlite              Read-only API → Render
raw evidence + append-only ledger                    ↓
        ↓                                  immutable SQLite snapshot
verified snapshot publication              + publish-time trust manifest
```

The local database, raw captures, collector credentials, and browser automation
never run on Render. Render receives only a transactionally consistent SQLite
copy and a manifest that binds the copy to its SHA-256 hash and the verified
ledger head. Render cannot create tables, enable WAL, register demo users, or
write to that database.

## Important boundaries

- Keep the `air-sankhyiki` repository private. Render supports private GitHub
  repositories through its GitHub App; grant it access only to this repository.
- Vercel CLI deployments upload the selected local directory. They do not need
  a GitHub connection. Run the production command again whenever local frontend
  changes should become live.
- Do not place `SERPAPI_KEY`, `SERPAPI_KEYS`, Akasa tokens, `.env`, raw captures,
  or the writable `data/lake/apix.sqlite` in Git, Vercel, or Render.
- The deployed API is a dated, read-only evaluation snapshot. It is not the
  scraper node and does not update until the owner publishes another snapshot.
- Use a paid Render web-service instance for final judging to avoid free-tier
  sleeping/cold starts. No persistent disk is needed because the database is
  bundled and immutable.

## 0. One-time prerequisites

Open PowerShell and confirm the local applications pass before deploying:

```powershell
Set-Location "D:\Engineering Resources\SIH 26\project\air-sankhyiki"
uv run --project packages/apix_index pytest packages/apix_index/tests -q
uv run --project services/collectors pytest services/collectors/tests -q
uv run --project apps/api pytest apps/api/tests -q

Set-Location apps\dashboard
npm install
npm run build
Set-Location ..\..
```

Install and authenticate the Vercel CLI yourself:

```powershell
npm install --global vercel
vercel --version
vercel login
vercel whoami
```

Create or use these accounts:

1. A Vercel account for the landing page and dashboard.
2. A Render account for the API.
3. A GitHub account with admin access to the private backend repository. For an
   organization-owned repository, an organization owner might need to approve
   the Render GitHub App installation.

## 1. Prepare and verify the read-only API snapshot

Do this only after the nightly collector has finished. Do not run it while a
manual collection is still active.

```powershell
Set-Location "D:\Engineering Resources\SIH 26\project\air-sankhyiki"

uv run --project services/collectors ledger verify
uv run --project apps/api python scripts/prepare_render_snapshot.py
```

The second command performs all of the following:

1. Re-verifies the complete local ledger and raw-file coverage.
2. Refuses publication if any file is missing, modified, or unsealed.
3. Uses SQLite's online backup API to copy a consistent database view.
4. Rebuilds a sanitized snapshot containing `fare_quotes` plus derived,
   publish-time API response caches; local demo-user tables and their
   underlying SQLite pages are excluded.
5. Runs `PRAGMA integrity_check` on the sanitized copy.
6. Writes `data/deploy/apix.snapshot.sqlite`.
7. Materializes index, route, PRISM, competition, nowcast and Fair Fare
   responses so Render does not recompute pandas pipelines during page clicks.
8. Writes `data/deploy/snapshot-manifest.json` with database and ledger hashes,
   row count, collection range, cache count, ledger head, and coverage counts.

Inspect the non-secret manifest:

```powershell
Get-Content data\deploy\snapshot-manifest.json
Get-FileHash data\deploy\apix.snapshot.sqlite -Algorithm SHA256
```

The displayed file hash must equal `database.sha256` in the manifest. The
generated snapshot is currently the only `.sqlite` file explicitly permitted
by `.gitignore`; never use `git add -f` on the writable lake.

Run the API locally in the same locked mode Render will use:

```powershell
$env:APIX_READ_ONLY = "1"
$env:APIX_SQLITE_IMMUTABLE = "1"
$env:APIX_DB_PATH = "data/deploy/apix.snapshot.sqlite"
$env:APIX_SNAPSHOT_MANIFEST = "data/deploy/snapshot-manifest.json"
$env:APIX_REQUIRE_AUTH = "0"
$env:APIX_CORS_ORIGINS = "http://127.0.0.1:3000"

uv run --project apps/api uvicorn api.main:app --host 127.0.0.1 --port 8001
```

In a second PowerShell window:

```powershell
curl.exe http://127.0.0.1:8001/health
curl.exe http://127.0.0.1:8001/api/apix/getAPIxIndex
curl.exe http://127.0.0.1:8001/api/apix/getLedgerStatus
```

`/health` must report `read-only-snapshot`. The ledger response must say its
verification scope is `publish-time scraper-node verification`. Stop the local
server with `Ctrl+C`; those environment variables affect only that terminal.

## 2. Link the dashboard project in Vercel (no deployment yet)

Linking first creates the stable Vercel project name needed for API CORS.

```powershell
Set-Location "D:\Engineering Resources\SIH 26\project\air-sankhyiki\apps\dashboard"
vercel link
```

Answer the prompts:

1. Select your Vercel account/team.
2. Choose **Create a new project** unless the dashboard project already exists.
3. Use a clear name such as `air-sankhyiki-dashboard`.
4. Confirm this directory as the project directory.
5. Accept the detected **Next.js** framework settings.

Vercel creates a local `.vercel` link directory; it is deployment metadata and
must remain uncommitted. Your normal production origin will be similar to:

```text
https://air-sankhyiki-dashboard.vercel.app
```

Check the exact project domain in Vercel Dashboard → Project → Settings →
Domains. Save it as `<DASHBOARD_ORIGIN>` without a trailing slash.

## 3. Put the private backend repository on GitHub

Render's Git-based deployment requires the prepared code and snapshot to exist
in the private remote. Review the changes before committing:

```powershell
Set-Location "D:\Engineering Resources\SIH 26\project\air-sankhyiki"
git status --short
git diff --check
git diff
```

Confirm that these deployment files are present:

```text
render.yaml
data/deploy/apix.snapshot.sqlite
data/deploy/snapshot-manifest.json
apps/api/src/api/snapshot.py
scripts/prepare_render_snapshot.py
```

Perform the commit and push yourself. A narrowly scoped example is:

```powershell
git add .gitignore .env.example render.yaml DEPLOY.md `
  apps/api/src/api/main.py apps/api/src/api/snapshot.py `
  apps/api/tests/test_read_only_snapshot.py `
  services/collectors/src/collectors/storage.py `
  scripts/prepare_render_snapshot.py data/deploy data/ledger.jsonl

git status --short
git commit -m "Prepare immutable read-only judging deployment"
git push origin main
```

Before confirming the commit, verify that `.env`, `data/raw`, and `data/lake`
do not appear in `git status` or the staged diff.

## 4. Give Render access to only the private backend repository

In a browser, perform these manual account-sensitive steps:

1. Sign in to Render.
2. Open **Account Settings → Git Providers** and connect GitHub.
3. Install or configure the **Render GitHub App**.
4. Under repository access, choose **Only select repositories**.
5. Select only the private `air-sankhyiki` backend repository.
6. If GitHub shows **Request** instead of **Install**, ask the GitHub
   organization owner to approve that request. Render cannot list the private
   org repository until this approval is complete.
7. Return to Render and refresh the repository list.

This does not make the repository public. If organization policy permanently
forbids third-party GitHub Apps, create a private personal mirror under your own
GitHub account and connect only that mirror; do not make either repository
public.

## 5. Create the Render API from `render.yaml`

The repository contains a Render Blueprint with safe defaults: Singapore
region, paid 512 MB web service, manual deploys, `/health` checks, and read-only
snapshot environment flags.

1. In Render, select **New → Blueprint**.
2. Connect the private backend repository.
3. Select the branch containing the reviewed deployment commit.
4. Confirm Render detects the root `render.yaml`.
5. For `APIX_CORS_ORIGINS`, enter the exact `<DASHBOARD_ORIGIN>` from step 2,
   for example `https://air-sankhyiki-dashboard.vercel.app`. Do not add a
   trailing slash and do not use `*` for the judging deployment.
6. Review the service settings and create the Blueprint.
7. Keep **Auto Deploy** disabled. This makes every data publication a deliberate
   owner-approved action.
8. Wait for build, health check, and deployment to finish.

The effective commands from `render.yaml` are:

```text
Build: pip install uv && uv sync --frozen --no-dev --project apps/api
Start: uv run --frozen --project apps/api uvicorn api.main:app --host 0.0.0.0 --port $PORT
Health: /health
```

Do not add scraper credentials or a persistent disk. The service should contain
these non-secret settings:

```text
APIX_READ_ONLY=1
APIX_SQLITE_IMMUTABLE=1
APIX_DB_PATH=data/deploy/apix.snapshot.sqlite
APIX_SNAPSHOT_MANIFEST=data/deploy/snapshot-manifest.json
APIX_REQUIRE_AUTH=0
APIX_CORS_ORIGINS=https://<your-dashboard-domain>
```

Copy the stable API origin shown by Render, such as:

```text
https://air-sankhyiki-api.onrender.com
```

Save it as `<API_ORIGIN>` without a trailing slash.

## 6. Verify Render before connecting the dashboard

Run these commands locally, substituting the real Render URL:

```powershell
curl.exe https://air-sankhyiki-api.onrender.com/health
curl.exe https://air-sankhyiki-api.onrender.com/api/apix/getAPIxIndex
curl.exe https://air-sankhyiki-api.onrender.com/api/apix/getLedgerStatus
curl.exe https://air-sankhyiki-api.onrender.com/api/apix/getCompetition
```

Required results:

- `/health` returns HTTP 200, `mode: read-only-snapshot`, the publication time,
  the snapshot hash, and a non-zero `api_cache_entries` count.
- The index endpoint returns real dated observations.
- Ledger status reports `intact: true`, complete publish-time coverage, and the
  same snapshot hash as `/health`.
- Render logs contain no `attempt to write a readonly database`, missing-file,
  checksum, or health-check errors.

An intentional write-path check is optional:

```powershell
curl.exe -X POST https://air-sankhyiki-api.onrender.com/api/auth/signup `
  -H "content-type: application/json" `
  -d '{"email":"write-test@example.invalid","password":"not-a-real-password"}'
```

It must return HTTP 503 and state that account storage is disabled. This proves
the hosted process did not silently create or modify an SQLite table.

## 7. Configure and deploy the dashboard with Vercel CLI

Return to the linked dashboard directory:

```powershell
Set-Location "D:\Engineering Resources\SIH 26\project\air-sankhyiki\apps\dashboard"
vercel env add NEXT_PUBLIC_APIX_BASE production
vercel env add NEXT_PUBLIC_APIX_BASE preview
```

When prompted for each value, paste `<API_ORIGIN>` without a trailing slash.
This variable is public by design: it is the browser-visible API origin, not a
secret. Confirm it exists:

```powershell
vercel env ls
```

Build locally first:

```powershell
npm install
npm run build
```

Create a Vercel preview deployment from the local directory:

```powershell
vercel deploy --logs
```

The preview may be CORS-blocked because its generated hostname is not the
production origin allow-listed on Render. Verify the build and layout, then
deploy production:

```powershell
vercel deploy --prod --logs
```

Open the stable production domain and inspect browser DevTools → Network. API
requests must go to `<API_ORIGIN>` and return HTTP 200. Test Overview, Routes,
PRISM, Competition, Nowcast, Fair Fare, and Trust pages.

If the dashboard domain differs from `<DASHBOARD_ORIGIN>`, update
`APIX_CORS_ORIGINS` in Render, save it, and manually redeploy/restart the API.

## 8. Deploy the standalone landing page with Vercel CLI

The landing page is a separate static project and does not need GitHub:

```powershell
Set-Location "D:\Engineering Resources\SIH 26\project\landing-page\landing-page"
vercel link
```

Answer the prompts:

1. Select your Vercel account/team.
2. Create or link a project such as `air-sankhyiki-landing`.
3. Select **Other** if asked for a framework preset.
4. Keep the project root as the current directory.
5. Use no build command and use `.` as the output directory if Vercel asks.

Deploy a preview, check all links and assets, then deploy production:

```powershell
vercel deploy --logs
vercel deploy --prod --logs
```

Vercel CLI uploads the current local landing-page files. Because this project
is not connected to GitHub, later edits are not deployed automatically—rerun
`vercel deploy --prod` whenever you intentionally want to publish them.

## 9. Custom domains (optional, manual)

A simple final layout is:

```text
www.<domain>   → Vercel landing project
app.<domain>   → Vercel dashboard project
api.<domain>   → Render API service
```

Add each domain in its provider dashboard and create exactly the DNS records
shown there. After adding a dashboard custom domain, replace Render's
`APIX_CORS_ORIGINS` value with the final `https://app.<domain>` origin. Keep the
default `vercel.app` and `onrender.com` URLs available as emergency fallbacks.

## 10. Publish a later nightly snapshot

Local scraping does not automatically alter the hosted database. After a
successful collection, use this controlled release sequence:

```powershell
Set-Location "D:\Engineering Resources\SIH 26\project\air-sankhyiki"
uv run --project services/collectors ledger verify
uv run --project apps/api python scripts/prepare_render_snapshot.py
Get-Content data\deploy\snapshot-manifest.json
Get-FileHash data\deploy\apix.snapshot.sqlite -Algorithm SHA256
git status --short
```

Review, commit, and push only the intended ledger/snapshot update yourself:

```powershell
git add data/ledger.jsonl data/deploy/apix.snapshot.sqlite `
  data/deploy/snapshot-manifest.json
git diff --cached --stat
git commit -m "Publish verified APIx snapshot YYYY-MM-DD"
git push origin main
```

Because auto-deploy is disabled, open Render → API service → **Manual Deploy →
Deploy latest commit**. Wait for `/health` to pass, then repeat the four endpoint
checks from step 6. Vercel does not need redeployment when only API data changes.

## 11. Rollback and incident procedure

If a new snapshot fails verification or produces an unexpected dashboard:

1. Do not modify historical raw captures, the local lake, or old ledger entries.
2. In Render, open the API service's deploy history.
3. Redeploy the last known-good commit/deploy.
4. Confirm `/health`, index, and ledger endpoints.
5. Diagnose the new local snapshot separately. Publish it only after ledger,
   database integrity, tests, and displayed results all pass.

If a credential is ever exposed, rotate it at its provider immediately and
remove it from the Git history before any further deployment. A normal deletion
commit is insufficient for a secret already present in repository history.

## 12. Final judging checklist

- [ ] Both GitHub repositories remain private where intended.
- [ ] Landing and dashboard production domains load in an incognito window.
- [ ] Render uses a non-sleeping paid web-service plan.
- [ ] `/health` says `read-only-snapshot` and reports the expected hash.
- [ ] API, dashboard, and manifest show the same latest collection date.
- [ ] Ledger shows intact and full coverage at snapshot publication time.
- [ ] Render contains no scraper/API-provider secrets and no persistent disk.
- [ ] CORS contains only the final dashboard origin(s), never `*`.
- [ ] All seven dashboard pages render with no failed API requests.
- [ ] The landing-page CTA points to the production dashboard.
- [ ] The previous Render deployment and default provider URLs are recorded as
      rollback links.

## Official references

- Vercel CLI deployment: <https://vercel.com/docs/cli/deploy>
- Vercel end-to-end CLI workflow: <https://vercel.com/docs/projects/deploy-from-cli>
- Render FastAPI deployment: <https://render.com/docs/deploy-fastapi>
- Render private Git-provider access: <https://render.com/docs/git-provider>
- Render Blueprint specification: <https://render.com/docs/blueprint-spec>
- Render free-instance limits: <https://render.com/docs/free>
