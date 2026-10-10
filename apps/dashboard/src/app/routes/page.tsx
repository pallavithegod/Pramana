"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Chart from "@/components/Chart";
import ChartCard from "@/components/ChartCard";
import ApiDown from "@/components/ApiDown";
import { api, inr, pct, type HeatmapCell, type RouteSeriesRow } from "@/lib/api";
import { baseOption, type ChartTheme } from "@/lib/theme";

const BUCKETS = [1, 7, 15, 30, 45];

export default function Page() {
  // useSearchParams needs a Suspense boundary under static prerender
  return (
    <Suspense fallback={<div className="card mt-8 h-64 animate-pulse" />}>
      <RoutesPage />
    </Suspense>
  );
}

function RoutesPage() {
  const [cells, setCells] = useState<HeatmapCell[] | null>(null);
  const [mode, setMode] = useState<"change" | "fare">("change");
  const [route, setRoute] = useState<string | null>(null);
  const [series, setSeries] = useState<RouteSeriesRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  // topbar search deep-links here as /routes?route=XXX-YYY; reacts to every
  // new search, including while already on this page
  const wanted = useSearchParams().get("route")?.toUpperCase() ?? null;

  useEffect(() => {
    api
      .heatmap()
      .then((h) => setCells(h.data))
      .catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    if (!cells) return;
    const rs = new Set(cells.map((c) => c.route));
    if (wanted && rs.has(wanted)) setRoute(wanted);
    else if (!route && rs.size) setRoute(rs.has("DEL-BOM") ? "DEL-BOM" : [...rs].sort()[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cells, wanted]);

  useEffect(() => {
    if (!route) return;
    api
      .routeSeries(route)
      .then((r) => setSeries(r.data))
      .catch(() => setSeries([]));
  }, [route]);

  const routes = useMemo(
    () => Array.from(new Set((cells ?? []).map((c) => c.route))).sort(),
    [cells],
  );

  // dot-plot rows sorted by the active measure — most movement / costliest first
  const sortedRoutes = useMemo(() => {
    const val = (c: HeatmapCell) => (mode === "change" ? c.change_pct : (c.latest_fare ?? 0));
    const byRoute = new Map<string, number[]>();
    for (const c of cells ?? []) {
      byRoute.set(c.route, [...(byRoute.get(c.route) ?? []), val(c)]);
    }
    return [...byRoute.entries()]
      .map(([r, vs]) => [r, vs.reduce((a, b) => a + b, 0) / vs.length] as const)
      .sort((a, b) => a[1] - b[1]) // ascending: biggest risers end up at the TOP of the y axis
      .map(([r]) => r);
  }, [cells, mode]);

  const buildDotPlot = useCallback(
    (t: ChartTheme) => {
      const base = baseOption(t);
      const cellValue = (c: HeatmapCell) =>
        mode === "change" ? c.change_pct : c.latest_fare;

      // min→max spread per route, drawn as a floating 2px bar (transparent base
      // + visible remainder, stacked) so the eye can scan each row's range
      const spans = sortedRoutes.map((r) => {
        const vs = (cells ?? [])
          .filter((c) => c.route === r)
          .map(cellValue)
          .filter((v): v is number => v != null);
        return vs.length ? ([Math.min(...vs), Math.max(...vs)] as const) : null;
      });

      const dotSeries = BUCKETS.map((b, i) => ({
        name: `T+${b}`,
        type: "scatter" as const,
        symbolSize: 11,
        z: 3,
        itemStyle: { color: t.ordinal[i], borderColor: t.surface, borderWidth: 1.5 },
        data: (cells ?? [])
          .filter((c) => c.leadtime_code === b && cellValue(c) != null)
          .map((c) => ({
            value: [cellValue(c), sortedRoutes.indexOf(c.route)],
            cell: c,
          })),
      }));

      return {
        ...base,
        grid: { left: 84, right: 24, top: 34, bottom: 30 },
        legend: {
          top: 0,
          left: 84,
          icon: "circle",
          itemWidth: 9,
          itemHeight: 9,
          itemGap: 14,
          data: BUCKETS.map((b) => `T+${b}`),
          textStyle: { color: t.inkSecondary, fontSize: 11 },
        },
        xAxis: {
          ...base.xAxis,
          type: "value" as const,
          scale: true,
          axisLabel: {
            color: t.inkMuted,
            fontSize: 11,
            formatter: (v: number) =>
              mode === "change" ? `${v}%` : `₹${(v / 1000).toFixed(0)}k`,
          },
          splitLine: { lineStyle: { color: t.grid, type: "dashed" as const } },
        },
        yAxis: {
          ...base.yAxis,
          type: "category" as const,
          data: sortedRoutes,
          axisLabel: { color: t.inkSecondary, fontSize: 11 },
          splitLine: { show: false },
          axisTick: { show: false },
        },
        tooltip: {
          ...base.tooltip,
          formatter: (p: { data?: { cell?: HeatmapCell } }) => {
            const c = p.data?.cell;
            if (!c) return "";
            return (
              `<b>${c.route}</b> · T+${c.leadtime_code}<br/>` +
              `Change vs base: <b>${pct(c.change_pct)}</b><br/>` +
              `Cheapest fare: ${inr(c.latest_fare)}<br/>` +
              `<span style="color:${t.inkMuted}">n=${c.n_matched_products} matched · as of ${c.as_of}</span>`
            );
          },
        },
        series: [
          // min→max spread line per route, drawn in pixel space (a stacked-bar
          // trick breaks here: ECharts stacks negative segments on the other
          // side of zero, flipping the span)
          {
            type: "custom" as const,
            silent: true,
            z: 1,
            renderItem: (
              _params: unknown,
              apiArg: {
                value: (i: number) => number;
                coord: (v: [number, number]) => [number, number];
              },
            ) => {
              const p1 = apiArg.coord([apiArg.value(0), apiArg.value(2)]);
              const p2 = apiArg.coord([apiArg.value(1), apiArg.value(2)]);
              return {
                type: "line",
                shape: { x1: p1[0], y1: p1[1], x2: p2[0], y2: p2[1] },
                style: { stroke: t.deEmphasis, lineWidth: 2.5, lineCap: "round" },
              };
            },
            data: spans
              .map((s, i) => (s && s[1] > s[0] ? [s[0], s[1], i] : null))
              .filter((d): d is [number, number, number] => d !== null),
          },
          // zero reference in change mode
          ...(mode === "change"
            ? [
                {
                  type: "scatter" as const,
                  data: [],
                  markLine: {
                    symbol: "none",
                    silent: true,
                    label: { show: false },
                    lineStyle: { color: t.baseline, width: 1.5 },
                    data: [{ xAxis: 0 }],
                  },
                },
              ]
            : []),
          ...dotSeries,
        ],
      };
    },
    [cells, sortedRoutes, mode],
  );

  const buildBookingCurve = useCallback(
    (t: ChartTheme) => {
      const base = baseOption(t);
      const latestDay = series.reduce((m, r) => (r.date > m ? r.date : m), "");
      const latest = series.filter((r) => r.date === latestDay);
      return {
        ...base,
        grid: { ...base.grid, bottom: 48 },
        xAxis: {
          ...base.xAxis,
          type: "category" as const,
          data: BUCKETS.map((b) => `T+${b}`),
          name: "days before departure",
          nameLocation: "middle" as const,
          nameGap: 26,
          nameTextStyle: { color: t.inkMuted, fontSize: 11 },
        },
        yAxis: { ...base.yAxis, type: "value" as const, scale: true },
        tooltip: { ...base.tooltip, trigger: "axis" as const },
        series: [
          {
            name: `cheapest fare (${latestDay})`,
            type: "line" as const,
            data: BUCKETS.map(
              (b) => latest.find((r) => r.leadtime_code === b)?.cheapest_fare ?? null,
            ),
            connectNulls: true,
            lineStyle: { width: 2, color: t.series[0] },
            itemStyle: { color: t.series[0] },
            symbolSize: 8,
          },
        ],
      };
    },
    [series],
  );

  if (err) return <ApiDown error={err} />;
  if (!cells) return <div className="card mt-8 h-64 animate-pulse" />;

  return (
    <div className="space-y-5">
      <ChartCard
        title="Route movement by booking window"
        subtitle={
          mode === "change"
            ? "Each dot = one booking window (darker blue = closer to departure) · position = index change vs that cell's base day · gray line spans the route's min–max across windows · matched flights only"
            : "Each dot = one booking window (darker blue = closer to departure) · position = latest observed fare · gray line spans the route's min–max across windows"
        }
        apiPath="/api/apix/getRouteHeatmap"
        right={
          <div className="flex rounded border text-[11px]" style={{ borderColor: "var(--hairline)" }}>
            {(["change", "fare"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className="px-2 py-1"
                style={{
                  background: mode === m ? "var(--accent-soft)" : "transparent",
                  color: mode === m ? "var(--ink)" : "var(--ink-secondary)",
                }}
              >
                {m === "change" ? "Δ vs base" : "Fare level"}
              </button>
            ))}
          </div>
        }
      >
        <Chart
          build={buildDotPlot}
          height={Math.max(280, sortedRoutes.length * 32 + 100)}
          onClick={(p) => {
            const d = p.data as { value?: [number, number] } | undefined;
            const yi = d?.value?.[1];
            if (yi != null) setRoute(sortedRoutes[yi]);
          }}
        />
        <p className="mt-1 text-[11px]" style={{ color: "var(--ink-muted)" }}>
          Rows sorted by average movement — biggest risers on top. Click a dot to drill
          into the route below. A window appears once it has two collection days
          (matched-model requirement).
        </p>
      </ChartCard>

      <ChartCard
        title={`Booking curve — ${route ?? ""}`}
        subtitle="Cheapest observed fare by days-to-departure, latest collection day · the lead-time elasticity view the PS asks for"
        apiPath={route ? `/api/apix/getRouteSeries?route_code=${route}` : undefined}
        right={
          <select
            value={route ?? ""}
            onChange={(e) => setRoute(e.target.value)}
            className="rounded border px-2 py-1 text-[12px]"
            style={{ borderColor: "var(--hairline)", background: "var(--surface)", color: "var(--ink)" }}
          >
            {routes.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        }
      >
        {series.length ? (
          <Chart build={buildBookingCurve} height={260} />
        ) : (
          <p className="py-10 text-center text-[12px]" style={{ color: "var(--ink-muted)" }}>
            No series yet for this route.
          </p>
        )}
      </ChartCard>
    </div>
  );
}
