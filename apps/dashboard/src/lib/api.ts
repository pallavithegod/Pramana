/** Client for the Air-Sankhyiki FastAPI (MoSPI envelope conventions). */

export const API_BASE =
  process.env.NEXT_PUBLIC_APIX_BASE ?? "http://127.0.0.1:8001";

export interface Envelope<T> {
  data: T[];
  meta_data: {
    page: number;
    totalRecords: number;
    totalPages: number;
    recordPerPage: number;
  };
  msg: string;
  statusCode: boolean;
}

export interface IndexRow {
  date: string;
  index: number;
  inflation: number | null;
  status: string;
  n_cells: number;
  n_matched_products: number;
}

export interface HeatmapCell {
  route: string;
  leadtime_code: number;
  index: number;
  change_pct: number;
  latest_fare: number | null;
  n_matched_products: number;
  as_of: string;
}

export interface RouteSeriesRow {
  date: string;
  leadtime_code: number;
  index: number | null;
  cheapest_fare: number;
  n_matched_products: number;
}

export interface LadderRung {
  rbd: string;
  flight_no: string;
  departure_date: string;
  total_fare: number;
  base_fare: number | null;
  seats_available: number | null;
  as_of: string;
}

export interface SourceHealthRow {
  source: string;
  date: string;
  quotes: number;
  routes: number;
  last_collected_at: string;
}

export interface QuoteRow {
  carrier: string;
  flight_no: string | null;
  origin: string;
  dest: string;
  departure_date: string;
  collected_at: string;
  lead_days: number;
  rbd: string | null;
  total_fare: number;
  base_fare: number | null;
  taxes_fees: number | null;
  seats_available: number | null;
  source: string;
}

export interface CompetitionRow {
  route: string;
  hhi_observed: number;
  n_carriers: number;
  top_carrier: string;
  top_share_pct: number;
  n_flights_observed: number;
  method: string;
}

export interface NowcastRow {
  status: string;
  month?: string;
  nowcast_index?: number;
  band_low?: number;
  band_high?: number;
  n_days_observed?: number;
  days_in_month?: number;
  days_observed?: number;
  days_required?: number;
}

export interface PrismDecompRow {
  day: string;
  filing_index: number;
  market_index: number;
  availability_pressure_index: number;
  external_fee_change: boolean;
  availability_status: "AVAILABILITY_PRESSURE_PROXY" | "EXTERNAL_FEE_MOVEMENT_PRESENT";
}

export interface LedgerStatus {
  entries: number;
  head: string | null;
  last_sealed_at: string | null;
  intact: boolean;
  detail: string;
}

// In-memory response cache: data changes once per nightly collection, so
// navigating between pages must not refetch (and dedupe concurrent calls —
// Overview fires four at once). A deployed snapshot is immutable, so keep the
// responses for a full judging session.
const TTL_MS = 15 * 60_000;
const memo = new Map<string, { t: number; p: Promise<Envelope<unknown>> }>();

async function get<T>(path: string): Promise<Envelope<T>> {
  const hit = memo.get(path);
  if (hit && Date.now() - hit.t < TTL_MS) return hit.p as Promise<Envelope<T>>;
  const p = fetch(`${API_BASE}${path}`, { cache: "no-store" }).then((res) => {
    if (!res.ok) {
      memo.delete(path);
      throw new Error(`${path} → HTTP ${res.status}`);
    }
    return res.json();
  });
  memo.set(path, { t: Date.now(), p });
  p.catch(() => memo.delete(path));
  return p as Promise<Envelope<T>>;
}

/** Sorted basket routes (cached) — powers the topbar search suggestions. */
export async function routeList(): Promise<string[]> {
  const h = await get<HeatmapCell>("/api/apix/getRouteHeatmap");
  return Array.from(new Set(h.data.map((c) => c.route))).sort();
}

export const api = {
  index: (leadtime?: number) =>
    get<IndexRow>(
      `/api/apix/getAPIxIndex${leadtime ? `?leadtime_code=${leadtime}` : ""}`,
    ),
  heatmap: () => get<HeatmapCell>("/api/apix/getRouteHeatmap"),
  routeSeries: (route: string) =>
    get<RouteSeriesRow>(`/api/apix/getRouteSeries?route_code=${route}`),
  fareLadder: (route: string) =>
    get<LadderRung>(`/api/apix/getFareLadder?route_code=${route}`),
  sourceHealth: () => get<SourceHealthRow>("/api/apix/getSourceHealth"),
  quotes: (route: string, limit = 1000) =>
    get<QuoteRow>(`/api/apix/getQuotes?route_code=${route}&limit=${limit}`),
  fairFarePanel: (route: string) =>
    get<QuoteRow>(`/api/apix/getFairFarePanel?route_code=${route}`),
  competition: (days = 7) =>
    get<CompetitionRow>(`/api/apix/getCompetition?days=${days}`),
  nowcast: () => get<NowcastRow>("/api/apix/getNowcast"),
  prismDecomposition: () => get<PrismDecompRow>("/api/apix/getPrismDecomposition"),
  ledgerStatus: () => get<LedgerStatus>("/api/apix/getLedgerStatus"),
};

/** Preload section data only after Overview is usable. Failures remain
 * non-blocking and are retried normally when the user opens that page. */
export function prefetchDashboard(route = "DEL-BOM") {
  return Promise.allSettled([
    api.routeSeries(route),
    api.fareLadder(route),
    api.fairFarePanel(route),
    api.competition(7),
    api.ledgerStatus(),
  ]);
}

/** The literal API call behind a chart — shown in every ChartCard ("the chart IS the API"). */
export const apiUrl = (path: string) => `${API_BASE}${path}`;

export const inr = (v: number | null | undefined) =>
  v == null
    ? "—"
    : `₹${Math.round(v).toLocaleString("en-IN")}`;

export const pct = (v: number | null | undefined, signed = true) =>
  v == null ? "—" : `${signed && v > 0 ? "+" : ""}${v.toFixed(2)}%`;
