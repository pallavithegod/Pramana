# Air-Sankhyiki dashboard

Next.js 15, Tailwind CSS and Apache ECharts client for the local FastAPI
prototype. It is not currently deployed and does not represent an official
MoSPI publication.

## Run locally

Start the API from the main repository root:

```powershell
uv run --project apps/api uvicorn api.main:app --host 127.0.0.1 --port 8001
```

Then start the dashboard:

```powershell
Set-Location apps\dashboard
npm install
npm run dev
```

Open `http://127.0.0.1:3000/`. `NEXT_PUBLIC_APIX_BASE` can override the API
origin; the local fallback is `http://127.0.0.1:8001`.

## Implemented views

1. Overview — daily APIx, source totals, collection history and nowcast readiness.
2. Routes — route × lead-window movement and drill-down.
3. PRISM — live Akasa RBD ladders plus an explicitly labelled rung heuristic.
4. Nowcast — prototype month-average APIx estimate and PRISM decomposition.
5. Competition — seven-day SerpAPI distinct-flight-number HHI frequency proxy.
6. Fair Fare — percentile comparison against currently observed offers.
7. Trust — source policy, collection health and evidence-ledger status.

All charts read from FastAPI endpoints. SerpAPI totals do not contain native fee
splits; Akasa `availableCount` is not physical cabin utilization; Competition
HHI is not complete scheduled capacity; and the nowcast is not yet an official
CPI forecast.

## Checks

```powershell
npm exec -- tsc --noEmit --incremental false
npm run build
```

Do not run `npm run build` concurrently with `npm run dev` because both use the
Next.js `.next` directory.
