# APIx Dashboard — Design Specification

Status: historical design brief, written 1 Sep 2026 before implementation.
For current implemented behavior and limitations, use `README.md`; aspirational
items below are not deployment or validation claims.
Benchmark audited: AITM Airlines (aitmairlines.vercel.app) — feature surface adopted
selectively (see PLAN.md §3.6), visual grammar deliberately NOT adopted.

---

## 1. Design posture

**We are building the instrument panel of a National Statistical Office, not a
flight-sim cockpit.** The reference class is eSankhyiki, RBI's DBIE portal, ONS
visual.ons.gov.uk, and the US BTS — restrained, typographic, data-first. Every
styling decision should survive the question: *"would MoSPI publish this page under
the national emblem tomorrow?"*

### Anti-slop rules (hard, reviewable)

These are the tells that make dashboards read as AI-generated or hobbyist. All are
banned:

1. **No emoji anywhere in the UI.** Icons are a single stroke-icon set (Lucide),
   16/20px, `--ink-secondary`, always beside a text label — never alone, never colored.
2. **No rainbow heatmaps, no red→green scales.** Magnitude = one-hue sequential;
   change-vs-base = blue↔red diverging with a *gray* midpoint (CVD-safe, and red-up
   carries no moral judgment — inflation is measured, not scolded).
3. **No value printed on every mark.** Selective direct labels only (first/last/
   min/max/hovered). The AITM matrix prints 400 rupee values; ours prints zero —
   the tooltip and the table view carry exact numbers.
4. **No ALL-CAPS letterspaced micro-labels as decoration.** Caps are reserved for
   one role: 11px section eyebrows. Everything else is sentence case.
5. **No gradient buttons, no glassmorphism, no glow, no drop shadows deeper than
   `0 1px 2px rgba(11,11,11,.06)`.** Depth comes from hairline borders and surface
   steps, like paper.
6. **No aviation cosplay** ("FLIGHT CONTROL PANEL", "cockpit", "command center").
   Section names are the statistical nouns: Overview, Routes, PRISM, Nowcast,
   Competition, Public, Trust.
7. **No default Plotly/ECharts chrome** — toolbox off, our own export menu.
8. **No invented scores.** Every number on screen must be traceable: hover reveals
   `source → computation → evidence hash`. If we can't source it, it doesn't ship.

---

## 2. Identity & chrome

- **Masthead:** left — "APIx · Airfare Price Index" wordmark in ink; right —
  "एयर-सांख्यिकी / Air-Sankhyiki" (Devanagari first, the eSankhyiki convention).
  Under the masthead runs a **2px tricolor keyline** (saffron `#FF9933` / white /
  green `#128807`) — the india.gov.in signature. This is the ONLY place the
  tricolor appears; it never colors data.
- **Accent (chrome only):** navy `#1B3B8B` (Ashoka-blue family) for active nav,
  links, focus rings, primary buttons. Never used as a series color (it would
  collide with series-1 blue).
- **Status bar** (top right): `Data as of 01 Sep 2026 05:30 IST · 341 quotes ·
  ledger ✓ verified` — freshness + provenance always visible, the govt trust cue.
- **Typography:** system sans (`system-ui, "Segoe UI", sans-serif`); Devanagari
  falls back to "Noto Sans Devanagari". Hero figures ≥48px regular weight (not
  bold — big numbers carry themselves). `tabular-nums` on all table columns, axis
  ticks, and KPI deltas. No serif, no display face, no letter-spaced caps titles.
- **Surfaces:** page plane `#f9f9f7`, cards/chart surface `#fcfcfb`, hairline
  border `rgba(11,11,11,.10)`, radius 8px. Dark mode: `#0d0d0d` / `#1a1a19` /
  `rgba(255,255,255,.10)` — a *selected* theme (own palette steps), not a filter
  inversion. This is deliberately papers-and-ink, maximally distant from AITM's
  cream/khaki.

## 3. Data palette (validated — do not eyeball edits)

Uses the pre-validated brand-neutral reference set (both modes pass adjacent-pair
CVD ΔE ≥ 8, normal-vision ≥ 15, against exactly these surfaces). If any hex ever
changes, re-run `validate_palette.js` before merging.

| Role | Light | Dark | Use |
|---|---|---|---|
| series-1 blue | `#2a78d6` | `#3987e5` | APIx headline line, primary series |
| series-2 orange | `#eb6834` | `#d95926` | comparison series (official CPI overlay) |
| series-3 aqua | `#1baf7a` | `#199e70` | third series (filing/rationing splits) |
| series-4 yellow | `#eda100` | `#c98500` | 4th (direct labels become mandatory) |
| de-emphasis gray | `#c3c2b7` | `#52514e` | context series in emphasis charts |
| sequential (magnitude) | blue ramp `#cde2fb→#0d366b` | same ramp, dark-stepped | heatmap fares, arc weights |
| diverging (change) | blue `#2a78d6` ↔ gray mid `#f0efec`/`#383835` ↔ red `#e34948` | — | % change vs base, MoM deltas |
| status good/warn/serious/critical | `#0ca30c` `#fab219` `#ec835a` `#d03b3b` | same | anomaly severity ONLY, always icon+label |

Rules that follow from the method:
- **Carriers get fixed slot assignments** (6E=1, AI=2, SG=3, QP=4, IX=fold or
  facet) — identity follows the entity forever; filtering never repaints survivors.
- Scatter/bubble/map forms cap at **3 categorical series**; beyond that, facet.
- One y-axis per chart, always. Index vs ATF price = two stacked panels sharing
  an x-axis, never dual axis.
- Status colors never encode a series; series colors never encode severity.

## 4. Layout system

- **App shell:** slim left rail (72px collapsed / 220px expanded) with the 7
  sections; content max-width 1320px; 12-col grid, 16px gutters, 24px card padding.
- **Filter row** (one row, directly above charts, never floating): date-range
  preset list (Today / 7d / 30d / 90d / MTD / custom), route combobox, carrier
  combobox, lead-time bucket segmented control (T+1 · T+3 · T+7 · T+15 · T+30),
  base toggle (2012 ⇄ 2024). Filters apply to the whole page; active filters show
  as dismissible chips.
- **KPI tile spec** (the only place numbers get big): label (13px secondary) →
  value (32px, tabular) → delta chip (▲/▼ + %, `--ink-secondary` text with a 8px
  colored dot, NOT fully-colored text) → 48×160px sparkline (series-1, no axes).
  Max 5 tiles per row.
- **Every chart card** carries the same header anatomy: title (15px medium) ·
  subtitle stating *exactly* what is plotted incl. units and filters · right-side
  menu: `CSV · XLSX · PNG · API` — the API item copies the literal
  `api.air-sankhyiki.in` call that reproduces the chart (the "this chart IS the
  API" demo trick) · a `ⓘ methodology` popover citing the formula section.

## 5. Pages (component-level)

### 5.1 Overview — the 30-second story
1. **Hero figure:** today's APIx (e.g. `97.99`) + MoM/YoY deltas + "what this
   means" one-liner in plain language + Hindi subtitle.
2. **KPI row:** CPI-airfare nowcast (with ±band) · Filing component · Rationing
   component · Routes covered `12/80` · Quotes today.
3. **Headline chart:** daily APIx line (series-1) with 90% confidence band
   (12%-alpha fill), official monthly CPI airfare item as step-line (series-2),
   crosshair tooltip, range brush beneath. Rebase control top-right.
4. **Movers strip:** top 5 rising / falling routes as compact rows (route ·
   sparkline · Δ%) — a table, not a chart.

### 5.2 Routes — the signature visuals
1. **Route × lead-time matrix** (the PS-mandated heatmap): rows = basket routes
   (sorted by DGCA weight, weight shown as a right-rail gray bar), cols = lead
   buckets. **Two color modes, user-toggled:** fare level (sequential blue) ⇄
   change vs base (diverging, gray midpoint). No cell text; hover = full tooltip
   (median fare, n quotes, Δ, evidence link); click = drill-down. `Table view`
   toggle renders the same grid as an accessible sortable table.
2. **India arc map** (ECharts geo + `lines`, official Survey-of-India-correct
   boundary GeoJSON — wrong India maps are disqualifying in a govt room): arcs
   origin→dest, width = passenger weight (3 steps), color = diverging Δ; airport
   nodes sized by traffic. Side panel lists top movers; clicking an arc opens the
   same drill-down. **This replaces AITM's Leaflet map — no third-party tiles, no
   Esri attribution, fully offline-capable (govt deployment argument).**
3. **Route drill-down** (route page or slide-over): elasticity curve f(τ) with
   "cheapest window" annotation, fare-component stacked bar (base/YQ/UDF/GST —
   EMT split), carrier presence timeline, quote-count/quality footer.

### 5.3 PRISM — teach the IP interactively
1. **Fare-ladder explainer** (custom SVG, the 90-second judge moment): vertical
   rungs = RBD price points from real Akasa data; animate scenario A (all rungs
   shift up = *filing event* → CPI) vs scenario B (the lowest returned fare
   moves to a higher existing rung = *availability-pressure heuristic*). Two buttons, one
   sentence of narration each. Diverging colors: filing = red arm, rationing =
   blue arm, consistent everywhere PRISM appears.
2. **Decomposition chart:** APIx line with filing index and availability-pressure
   index
   beneath as small multiples (same x-axis, one y-axis each — never stacked into
   a dual-axis).
3. **Event log table:** timestamp · route · carrier · event type chip ·
   magnitude · evidence hash link (opens ledger proof).

### 5.4 Nowcast
1. Nowcast fan chart (point line + widening band) vs official CPI airfare item
   dots fetched live from api.mospi.gov.in; annotation on publication days.
2. Backtest card: MAE / hit-rate of band coverage, honest error table.

### 5.5 Competition (PLAN §3.6)
1. **HHI × PRISM scatter:** x = route HHI (computed from observed carrier seat/
   flight share), y = filing-component 30-day change; quadrant guides at
   HHI 1500/2500 (DOJ thresholds, cited). **Emphasis form:** all routes gray,
   flagged quadrant (high-HHI + filing-led rises) in series-1; ≤3 hues total.
   Click → route drill-down with the PRISM event log pre-filtered. Subtitle
   states the one-liner: *"concentration is only a problem when it's exercised —
   this chart shows where it is."*
2. **Carrier profiles:** one card per carrier — only source-supported metrics
   (filing frequency, T+1/T+45 ratio, booking-curve steepness, RBD ladder depth)
   with provenance popovers. No radar chart (unverifiable-axes smell);
   a compact dot-plot per metric with the fleet median as reference tick.
3. **ATF pass-through simulator:** slider ATF ±x% → projected APIx path (dashed,
   with band) vs baseline; pass-through coefficient shown WITH its standard error
   and the regression's n — the honesty is the feature.

### 5.6 Public — Fair-Fare Checker
Single centered card, consumer language, Hindi/English toggle: route + date +
paid price → percentile strip (a meter, not a gauge), verdict sentence, "book
now vs wait" from f(τ) with the caveat line. Shareable URL. This page is the
public-good screenshot for slide 5.

### 5.7 Trust — the page no other team will have
1. Compliance matrix (source × robots/ToS verdict × tier × last-checked) —
   including the sources we REFUSED (SpiceJet live) and why.
2. Collection health: per-source success-rate calendar heatmap (sequential),
   quote volumes, freshness.
3. **Ledger verifier:** paste any published index value → walks the hash chain →
   green `verified` with the raw evidence reference. Live on stage.
4. Bulletin archive: auto-generated monthly PDF press notes (MoSPI press-release
   format) + `Download CSV/API` for every table.

## 6. Interaction defaults

- Crosshair + shared tooltip on all time-series; per-mark tooltip on bars/cells/
  arcs; hit targets ≥ 24px even for thin marks.
- Tooltip anatomy: bold value (tabular) → series rows with 8px swatch dots →
  muted footer (`n=46 quotes · 05:30 IST · hash 3fa2…`).
- Every filter change updates the URL (deep-linkable state — judges can bookmark
  a finding); back button works.
- Loading = skeleton shapes of the actual chart geometry, never spinners.
- Empty/error states name the cause honestly ("SpiceJet excluded: bot-management
  refusal — see Trust") — turning gaps into the compliance story.

## 7. Accessibility & govt-readiness (GIGW nods)

- WCAG AA: focus-visible rings (2px navy), full keyboard nav, `prefers-reduced-
  motion` kills all animation including the PRISM explainer (falls back to
  before/after frames).
- Every chart has a `Table view` toggle (also the CVD/print/forced-colors
  fallback); texture fills (45°/135° lines) available via an accessibility
  setting for filled marks.
- Bilingual: masthead, section names, Fair-Fare Checker, and the Overview
  one-liner in Hindi + English (full i18n scaffold, `hi`/`en` locales).
- Dark mode via `data-theme` toggle + OS default; both palettes are selected
  steps, validated per mode.

## 8. Build notes

- Next.js App Router + Tailwind (tokens above as CSS custom properties in
  `globals.css`, referenced by role — no raw hex in components).
- ECharts via a single `<Chart>` wrapper that injects: palette roles, tooltip
  formatter, export menu, API-link, table-view toggle, theme switching. No
  component instantiates ECharts directly — grammar consistency by construction.
- Component inventory (build order): `AppShell` → `KpiTile` → `ChartCard` →
  `IndexLine` (band + rebase) → `RouteMatrix` → `IndiaArcMap` → `PrismLadder` →
  `HHIScatter` → `FairFareCard` → `LedgerVerifier` → `BulletinList`.
- Screenshot-test the 7 pages in both themes before the demo; check every chart
  against the anti-slop rules in §1 as a PR checklist.
