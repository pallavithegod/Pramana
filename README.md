# Pramāna

A local econometric agent and MIT-licensed Python SDK. SerpApi supplies live market observations; LangChain orchestrates a local Ollama model; the preserved Kalman primitive estimates comparable price baselines. The frontend is a developer Agent Workspace with streaming tool telemetry.

## Manual tasks you must perform

1. Install Ollama for Windows from https://ollama.com/download/windows. It is absent from this machine's PATH. Open a new PowerShell terminal after installation.
2. Download a tool-capable local model: `ollama pull qwen2.5:7b`. Run `ollama serve` only if the desktop service is not already running. Choose a smaller tool-capable model if your hardware cannot run 7B and change `OLLAMA_MODEL` accordingly.
3. In this repository, copy `.env.pramana.example` to `.env.pramana` and privately set `SERPAPI_KEY` to your own authorized SerpApi key. No hosted LLM key is needed. Model inference is local; SerpApi consumes search credits. Check your account's balance.
4. After a live run, review changes and perform Git version control yourself. No commits, pushes, uploads, or submissions are automated here. Suggested commands, run from this repo after reviewing `git diff`:

```powershell
git status --short
git diff --check
git add .gitignore .env.pramana.example README.md pyproject.toml uv.lock apps/api apps/dashboard packages/pramana_sdk
git diff --cached --stat
git commit -m "Pivot to Pramana agent workspace and SerpApi SDK"
git push
```

5. Record the functioning local workflow, publish a publicly accessible video under three minutes, and submit the repository/video yourself. Disclose AI-assisted development. Official submission rules: https://serpapi.github.io/serpapi-india-hackathon-2026/rules.html . The published deadline is October 10, 2026, 23:59 IST.

## Run locally

PowerShell, starting in the outer workspace:

```powershell
Set-Location 'D:\Engineering Resources\SERPAPI\air-sankhyiki'
Copy-Item -LiteralPath .env.pramana.example -Destination .env.pramana
# Edit .env.pramana privately before starting the API.
uv sync --all-packages
uv run --package api uvicorn api.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
Set-Location 'D:\Engineering Resources\SERPAPI\air-sankhyiki\apps\dashboard'
npm ci
npm run dev
```

Open http://localhost:3000 and http://127.0.0.1:8000/docs . The API loads only `.env.pramana`, without overriding existing shell environment variables. Next proxies `/api/chat/*` to `127.0.0.1:8000`; configure `PRAMANA_BASE_URL` in the frontend server environment for another port. This loopback application has no authentication and is intended for local use. Public deployment requires authentication, per-user quotas and separate stores.

## Exact pivot directory structure

The historical enclosing folder name is retained so excluded scripts and research references continue to resolve. These are the authored pivot files; generated caches and untouched legacy files are omitted.

```text
SERPAPI/
|-- Documentation/                         # existing Mintlify repo; untouched
|-- analysis/                              # previous audit; untouched
|-- prompt.md / project.md                 # workspace inputs; untouched
|-- air-sankhyiki/                          # main monorepo
    |-- README.md
    |-- .env.pramana.example
    |-- .gitignore
    |-- pyproject.toml / uv.lock
    |-- packages/
    |   |-- apix_index/                    # original mathematical core, unchanged
    |   |-- pramana_sdk/
    |       |-- LICENSE / pyproject.toml
    |       |-- src/pramana/
    |       |   |-- __init__.py / config.py / errors.py
    |       |   |-- providers.py / normalize.py / client.py
    |       |   |-- store.py / filter.py / tools.py
    |       |   |-- workflow.py / agent.py
    |       |-- tests/test_agent_sdk.py
    |-- apps/
    |   |-- api/
    |   |   |-- pyproject.toml
    |   |   |-- src/api/__init__.py / main.py / chat.py
    |   |   |-- tests/test_chat.py           # existing regression tests also retained
    |   |-- dashboard/
    |       |-- package.json / package-lock.json / next.config.ts
    |       |-- src/
    |           |-- app/layout.tsx / page.tsx / globals.css / icon.svg
    |           |-- lib/chat.ts
    |           |-- components/agent/
    |               |-- AgentWorkspace.tsx
    |               |-- ChatPanel.tsx
    |               |-- TelemetryConsole.tsx
    |               |-- SignalResults.tsx
    |-- services/collectors/               # existing collectors, unchanged
    |-- data/
        |-- deploy/                       # immutable analytical snapshot, unchanged
        |-- runtime/pramana.sqlite         # generated mutable observations/reports
```

No authored `CONTRIBUTING.md` existed in either repository, so there was no such file to delete. PPT, scripts, research and Mintlify content remain untouched. The legacy dashboard pages, shell, branding icon and unused frontend components were removed. Historical backend analytical endpoints remain compatible.

## Modular Python implementation

`providers.py` wraps the official `serpapi.Client`, bounds per-run searches and redacts transport errors. `normalize.py` handles Google Flights, Hotels, Shopping, Amazon India, Jobs and News. `client.py` validates query specifications and returns normalized JSON with capture timestamps, stable product identities, source metadata, raw payload fingerprints, pagination and coverage warnings. `store.py` persists mutable comparable histories outside the immutable snapshot.

`tools.py` creates six actual LangChain `@tool` functions: `get_flight_fares`, `get_hotel_rates`, `get_retail_prices`, `get_labor_salaries`, `get_market_context`, `run_prism_filter`. Tools share a run-local registry and emit started/completed telemetry. Shopping plus Amazon costs two searches. Failed dispatches count toward the search budget. There is no hidden paid model fallback.

`filter.py` calls the original `apix_index.nowcast.local_level_filter` unchanged. It requires at least three distinct, timezone-aware comparable observations per product, validates positive finite single-currency prices, exposes q/r, posterior variance, conditional bands, trajectory and normalized innovations. It estimates a latent baseline; it does not establish a true price or a national CPI. Search result rankings are not time series. Repeated searches seconds apart are not meaningful economic history; collect matching specifications over an appropriate interval. Room/seller/pack changes require further comparability checks before published indexing. Q and R use the primitive's empirical variance convention; the conditional bands are not independently calibrated, and anomaly scores are descriptive rather than validated causal detectors.

The agent-facing filter requires `{"result_id":"result_..."}` from a prior price tool so the model cannot supply fabricated observations. The public SDK filter accepts the full normalized JSON for standalone use.

`agent.py` uses native LangChain `create_agent` and `ChatOllama`, including the exact requested system prompt. `workflow.py` fills missing Filter and News dependencies when the model tries to finish after a price search. Dispatch remains bounded by tool/search limits; errors, missing history and budget exhaustion are surfaced. News provides candidate explanations, not established causal attribution. Tool-output grounding is an instruction and data-access constraint, not a guarantee that an LLM can never misstate a result.

Standalone SDK example (no backend required):

```python
import asyncio
from pathlib import Path
from pramana import PramanaClient, run_prism_filter
from pramana.providers import SerpApiGateway
from pramana.store import SignalStore
import os

async def main():
    client = PramanaClient(SerpApiGateway(os.environ["SERPAPI_KEY"]),
                           SignalStore(Path("data/runtime/sdk.sqlite")))
    raw = await client.get_retail_prices("Samsung 990 PRO 1TB SSD", "both")
    print(run_prism_filter(raw))
    print(await client.get_market_context("Samsung SSD prices India"))

asyncio.run(main())
```

## Chat contract and component layout

- `GET /api/chat/status`: local Ollama/model and key readiness; no credentials returned.
- `POST /api/chat`: JSON report after execution.
- `POST /api/chat/stream`: POST-based SSE; actual run/tool started/completed events, heartbeats, final report or sanitized failure. Request: `{"message":"...","history":[{"role":"user","content":"..."}]}`. History permits only user/assistant roles, at most 12 entries. Message maximum 8,000 characters.
- `GET /api/chat/reports/{run_id}`: persisted report or 404.
- Busy requests return 429; unconfigured Ollama/key returns 503; synchronous timeout returns 504. Disconnects cancel orchestration and release streaming capacity. A provider request already dispatched in a worker thread can finish after cancellation; its search credit cannot be recalled.

```text
RootLayout
|-- AgentWorkspace (request lifecycle, readiness, cancellation, history)
    |-- Header (local model status)
    |-- ChatPanel (examples, dialogue, prompt composer)
    |   |-- SignalResults (measured coverage, baselines, source URLs)
    |-- TelemetryConsole (live actual tool events, latency, result/search counts)
```

Report text is rendered as plain text and source links accept only HTTP(S). Keys stay on the API server. The two-column layout collapses into chat plus console on mobile. There are no government, compliance or trust badges. SSE streams tool telemetry and the completed answer; it does not currently stream individual model tokens.

## Verification and packaging

Execution verification: 74 Python tests passed; Ruff, TypeScript and the Next.js production build passed; both wheels built. Chromium checks exercised prompt examples, POST SSE, report rendering, tool telemetry and mobile overflow using explicit provider fixtures, with no browser page errors. The workspace preview PNGs are UI fixtures, not evidence of live SerpApi/Ollama execution.

```powershell
uv run pytest -q
uv run ruff check packages/pramana_sdk apps/api/src/api apps/api/tests/test_chat.py
Set-Location apps/dashboard
npm run typecheck
npm run build
```

Tests cover the real LangChain tool-call graph using an injected model/provider, automatic completion when a model finishes early, all six engine parsers, insufficient history, mixed-currency rejection, original Kalman equivalence, partial provider results, budget exhaustion, redacted errors, report persistence, SSE, input validation, positive quote limits and unique health operation IDs.

`getQuotes?limit=0` now returns 422 before reading the database. GET `/health` has explicit unique operation ID `get_health`; HEAD remains available and is omitted from OpenAPI. Startup uses FastAPI lifespan rather than deprecated startup decorators.

Build distributable packages with `uv build --package apix-index` and `uv build --package pramana-sdk`. The SDK depends on the mathematical package: distribute/install both local wheels, rather than claiming `pip install pramana-sdk` works from PyPI before publication. SDK code has its own MIT license; existing mathematical code retains its existing ownership and licensing. No package publication was performed.

Live Ollama inference and paid/credited SerpApi calls have not been exercised in this execution: the local model is absent and no new key was supplied. Offline regression success does not establish live provider compatibility or demo latency. Run the example prompt after setup and verify actual sources, tool ordering and hardware responsiveness before recording.

## Judge strategy

Choose **AI Agents** for this implementation. That is a fit assessment, not a prediction of competitor strength or first place. A tested multi-engine economic investigation with visible tool sequencing exploits the existing math and workspace. Open-Source Integrations would be stronger with a reusable upstream provider/connector, a real upstream contribution or adoption, complete standalone installation and contract examples; wrapping existing tools in a new SDK alone is weak differentiation. The published rules require selecting one track and weigh idea strength, originality, complexity, usefulness and meaningful SerpApi usage without fixed percentage weights.

Demonstrate one complete investigation: exact-spec live observations -> comparable-history coverage -> PRISM posterior -> dated news -> a bounded, cited report. Show an empty salary, an exhausted budget or insufficient history gracefully. Public setup instructions, tests and an accessible sub-three-minute demo are essential submission evidence. Do not claim causality or an official CPI from search samples.

The concrete cross-engine use case is a **worker relocation purchasing-power comparison**: Google Jobs supplies role/pay opportunities; Google Flights supplies one-time relocation travel cost; Shopping supplies a fixed essential-goods basket; Hotels adds explicitly temporary accommodation. Compare first-month cash requirements across Bengaluru/Pune/Hyderabad, keeping advertised salary periods, one-time expenses and recurring expenses separate. Exclude missing pay instead of inventing it; rent, tax and recurring city costs require additional evidence before claiming full real-income comparisons. This is a scenario, not an implemented affordability calculator.

The proposed wow feature is **uncertainty-driven active investigation**: use Kalman innovations and posterior variance to distinguish a transient quote from persistent movement, allocate the next bounded SerpApi query to the most uncertain comparable series, then test competing explanations against dated News and Jobs signals. Demonstrate a controlled injected transient versus persistent shock, show which query was chosen and how uncertainty changed, and provide a deterministic replay. Current code exposes innovations/variance and tool provenance; adaptive search allocation, replay execution and competing-hypothesis testing remain follow-on work and must not be presented as already implemented. A timeline association alone does not prove causality.
