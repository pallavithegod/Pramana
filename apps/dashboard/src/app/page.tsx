"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import Chart from "@/components/Chart";
import ApiDown from "@/components/ApiDown";
import {
  IconActivity,
  IconCalendar,
  IconChevronDown,
  IconDatabase,
  IconDownload,
  IconLayers,
  IconRoute,
} from "@/components/Icons";
import {
  api,
  apiUrl,
  inr,
  prefetchDashboard,
  type HeatmapCell,
  type IndexRow,
  type NowcastRow,
  type SourceHealthRow,
} from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { baseOption, type ChartTheme } from "@/lib/theme";

/* ---------------------------------------------------------------- helpers */

function fmtDate(d: string) {
  return new Date(d + "T00:00:00").toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function monthLabel(month: string) {
  return new Date(`${month}-01T00:00:00`).toLocaleDateString("en-IN", {
    month: "long",
    year: "numeric",
  });
}

function previousMonth(month: string) {
  const date = new Date(`${month}-01T00:00:00Z`);
  date.setUTCMonth(date.getUTCMonth() - 1);
  return date.toISOString().slice(0, 7);
}

function calendarDaysInMonth(month: string) {
  const [year, monthNumber] = month.split("-").map(Number);
  return new Date(Date.UTC(year, monthNumber, 0)).getUTCDate();
}

function DeltaPill({ value, suffix = "%" }: { value: number | null | undefined; suffix?: string }) {
  if (value == null) return <span className="pill pill-flat">—</span>;
  if (Math.abs(value) < 0.05) return <span className="pill pill-flat">— 0.0{suffix}</span>;
  const up = value >= 0;
  return (
    <span className={`pill ${up ? "pill-up" : "pill-down"}`}>
      {up ? "▲" : "▼"} {Math.abs(value).toFixed(1)}
      {suffix}
    </span>
  );
}

function StatCard({
  label,
  value,
  delta,
  compare,
  icon,
  bubbleBg,
  bubbleFg,
}: {
  label: string;
  value: string;
  delta?: number | null;
  compare?: string;
  icon: React.ReactNode;
  bubbleBg: string;
  bubbleFg: string;
}) {
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between">
        <span className="text-[13px] font-medium" style={{ color: "var(--ink-secondary)" }}>
          {label}
        </span>
        <span className="icon-bubble" style={{ background: bubbleBg, color: bubbleFg }}>
          {icon}
        </span>
      </div>
      <div className="mt-1.5 flex items-center gap-2.5">
        <span className="tnum text-[26px] font-bold leading-8 tracking-tight">{value}</span>
        {delta !== undefined && <DeltaPill value={delta} />}
      </div>
      {compare && (
        <div className="mt-0.5 text-[11.5px]" style={{ color: "var(--ink-muted)" }}>
          {compare}
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- page */

export default function Overview() {
  const [rows, setRows] = useState<IndexRow[] | null>(null);
  const [cells, setCells] = useState<HeatmapCell[]>([]);
  const [health, setHealth] = useState<SourceHealthRow[]>([]);
  const [nc, setNc] = useState<NowcastRow | null>(null);
  const [windowSel, setWindowSel] = useState<number | 0>(0); // 0 = all windows
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.heatmap(), api.sourceHealth(), api.nowcast()])
      .then(([h, s, n]) => {
        setCells(h.data);
        setHealth(s.data);
        setNc(n.data[0] ?? null);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    api
      .index(windowSel || undefined)
      .then((i) => setRows(i.data))
      .catch((e) => setErr(String(e)));
  }, [windowSel]);

  useEffect(() => {
    if (rows === null || cells.length === 0) return;
    const defaultRoute = cells.some((cell) => cell.route === "DEL-BOM")
      ? "DEL-BOM"
      : cells[0].route;
    const timer = window.setTimeout(() => {
      void prefetchDashboard(defaultRoute);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [cells, rows]);

  const latest = rows?.[rows.length - 1];
  const prev = rows && rows.length > 1 ? rows[rows.length - 2] : null;
  const lastDay = latest?.date ?? "";
  const today = useMemo(() => health.filter((h) => h.date === lastDay), [health, lastDay]);
  const prevDay = useMemo(
    () => health.filter((h) => h.date === (prev?.date ?? "")),
    [health, prev],
  );
  const quotesToday = today.reduce((a, b) => a + b.quotes, 0);
  const quotesPrev = prevDay.reduce((a, b) => a + b.quotes, 0);
  const routesToday = today.length ? Math.max(...today.map((h) => h.routes)) : 0;
  const routesPrev = prevDay.length ? Math.max(...prevDay.map((h) => h.routes)) : 0;
  const currentMonth = latest?.date.slice(0, 7) ?? "";
  const referenceMonth = currentMonth ? previousMonth(currentMonth) : "";
  const currentMonthRows = useMemo(
    () => (rows ?? []).filter((row) => row.date.startsWith(currentMonth)),
    [rows, currentMonth],
  );
  const referenceMonthRows = useMemo(
    () => (rows ?? []).filter((row) => row.date.startsWith(referenceMonth)),
    [rows, referenceMonth],
  );
  const currentMonthAverage = currentMonthRows.length
    ? currentMonthRows.reduce((sum, row) => sum + row.index, 0) / currentMonthRows.length
    : null;
  const referenceMonthAverage = referenceMonthRows.length
    ? referenceMonthRows.reduce((sum, row) => sum + row.index, 0) / referenceMonthRows.length
    : null;
  const monthVsReference = currentMonthAverage != null && referenceMonthAverage != null
    ? ((currentMonthAverage / referenceMonthAverage) - 1) * 100
    : null;
  const referenceDaysExpected = referenceMonth ? calendarDaysInMonth(referenceMonth) : 0;
  const referenceComplete = referenceMonthRows.length === referenceDaysExpected;

  const days = useMemo(() => Array.from(new Set(health.map((h) => h.date))).sort(), [health]);
  const byDay = useMemo(
    () => days.map((d) => health.filter((h) => h.date === d).reduce((a, b) => a + b.quotes, 0)),
    [days, health],
  );

  const movers = useMemo(
    () =>
      [...cells]
        .filter((c) => Math.abs(c.change_pct) > 0.01)
        .sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct))
        .slice(0, 7),
    [cells],
  );

  /* ---- charts ---- */

  const buildIndexChart = useCallback(
    (t: ChartTheme) => {
      const base = baseOption(t);
      const currentMonthStart = rows!.findIndex((row) => row.date.startsWith(currentMonth));
      return {
        ...base,
        grid: { left: 42, right: 12, top: 14, bottom: 26 },
        xAxis: {
          ...base.xAxis,
          type: "category" as const,
          boundaryGap: false,
          data: rows!.map((r) => fmtDate(r.date).slice(0, 6)),
        },
        yAxis: {
          ...base.yAxis,
          type: "value" as const,
          scale: true,
          splitLine: { lineStyle: { color: t.grid, type: "dashed" as const } },
        },
        tooltip: { ...base.tooltip, trigger: "axis" as const },
        series: [
          {
            name: "Completed daily APIx",
            type: "line" as const,
            data: rows!.map((row) => (row.date.startsWith(currentMonth) ? null : row.index)),
            connectNulls: false,
            lineStyle: { width: 2.5, color: t.series[0] },
            itemStyle: { color: t.series[0] },
            symbol: "circle",
            symbolSize: 7,
            markLine: {
              symbol: "none",
              label: {
                formatter: "base 100",
                position: "insideEndTop" as const,
                color: t.inkMuted,
                fontSize: 10,
              },
              lineStyle: { color: t.baseline, type: "dashed" as const, width: 1 },
              data: [{ yAxis: 100 }],
            },
            markPoint: currentMonthStart > 0
              ? {
                  symbol: "circle",
                  symbolSize: 9,
                  itemStyle: { color: t.series[0], borderColor: t.surface, borderWidth: 2 },
                  label: {
                    show: true,
                    formatter: `${monthLabel(referenceMonth)} close`,
                    position: "top" as const,
                    color: t.inkSecondary,
                    fontSize: 10,
                  },
                  data: [{ coord: [currentMonthStart - 1, rows![currentMonthStart - 1].index] }],
                }
              : undefined,
          },
          {
            name: `${monthLabel(currentMonth)} observed APIx`,
            type: "line" as const,
            data: rows!.map((row, index) =>
              index >= Math.max(0, currentMonthStart - 1) ? row.index : null,
            ),
            connectNulls: false,
            lineStyle: { width: 2.5, type: "dashed" as const, color: t.series[3] },
            itemStyle: { color: t.series[3] },
            symbol: "circle",
            symbolSize: 7,
          },
        ],
      };
    },
    [rows, currentMonth, referenceMonth],
  );

  const buildCollectionBars = useCallback(
    (t: ChartTheme) => {
      const base = baseOption(t);
      const cadenceStart = days.find((day) => day.endsWith("-08-31")) ?? days[0];
      const cadenceStartTime = cadenceStart
        ? Date.parse(`${cadenceStart}T00:00:00Z`)
        : Number.NaN;
      const visibleDays = days.filter((day) => {
        const elapsedDays = Math.round(
          (Date.parse(`${day}T00:00:00Z`) - cadenceStartTime) / 86_400_000,
        );
        return elapsedDays >= 0 && elapsedDays % 3 === 0;
      });
      const latestDay = days.at(-1);
      if (latestDay && !visibleDays.includes(latestDay)) visibleDays.push(latestDay);
      const totalsByDay = new Map(days.map((day, idx) => [day, byDay[idx]]));
      const visibleTotals = visibleDays.map((day) => totalsByDay.get(day) ?? 0);
      const latestIdx = visibleTotals.length - 1;
      return {
        ...base,
        grid: { left: 0, right: 0, top: 34, bottom: 32, containLabel: false },
        xAxis: {
          ...base.xAxis,
          type: "category" as const,
          data: visibleDays.map((day, idx) => {
            const date = new Date(`${day}T00:00:00Z`);
            const dayLabel = String(date.getUTCDate()).padStart(2, "0");
            const monthLabel = date.toLocaleDateString("en-GB", {
              month: "short",
              timeZone: "UTC",
            });
            const previousMonth = idx > 0 ? visibleDays[idx - 1].slice(5, 7) : null;
            return idx === 0 || day.slice(5, 7) !== previousMonth
              ? `${dayLabel}\n${monthLabel}`
              : dayLabel;
          }),
          axisLabel: {
            color: t.inkMuted,
            fontSize: 10,
            interval: 0,
            formatter: (value: string) => value,
          },
        },
        yAxis: { ...base.yAxis, type: "value" as const, show: false },
        tooltip: {
          ...base.tooltip,
          trigger: "item" as const,
          formatter: (item: { dataIndex: number }) => {
            const idx = item.dataIndex ?? 0;
            return `<b>${fmtDate(visibleDays[idx])}</b><br/>${visibleTotals[idx].toLocaleString("en-IN")} quotes`;
          },
        },
        series: [
          {
            name: "Quotes collected",
            type: "bar" as const,
            barMaxWidth: 18,
            data: visibleTotals.map((value, idx) => ({
              value,
              itemStyle: {
                color: idx === latestIdx ? t.series[0] : t.deEmphasis,
                borderRadius: [5, 5, 0, 0],
              },
              label: idx === latestIdx
                ? {
                    show: true,
                    position: "top" as const,
                    formatter: value.toLocaleString("en-IN"),
                    color: t.ink,
                    fontWeight: 600 as const,
                    fontSize: 10,
                  }
                : { show: false },
            })),
          },
        ],
      };
    },
    [days, byDay],
  );

  const nowcastReady = nc?.status === "OK" && nc.nowcast_index != null;
  const observedMonthDays = nc?.n_days_observed ?? nc?.days_observed ?? 0;
  const daysInMonth = nc?.days_in_month ?? 30;
  const readinessPct = Math.min(
    100,
    Math.round(((nc?.days_observed ?? 0) / (nc?.days_required ?? 14)) * 100),
  );
  const monthCoveragePct = Math.min(
    100,
    Math.round((observedMonthDays / daysInMonth) * 100),
  );
  const gaugePct = nowcastReady ? monthCoveragePct : readinessPct;
  const nowcastBand = nc?.band_low != null && nc?.band_high != null
    ? `95% model band ${nc.band_low.toFixed(2)}-${nc.band_high.toFixed(2)}`
    : "Kalman estimate is live";

  const buildGauge = useCallback(
    (t: ChartTheme) => ({
      backgroundColor: "transparent",
      series: [
        {
          type: "gauge" as const,
          startAngle: 210,
          endAngle: -30,
          min: 0,
          max: 100,
          radius: "100%",
          center: ["50%", "60%"],
          pointer: { show: false },
          progress: {
            show: true,
            roundCap: true,
            width: 13,
            itemStyle: { color: t.series[2] },
          },
          axisLine: { roundCap: true, lineStyle: { width: 13, color: [[1, t.grid]] } },
          splitLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
          detail: {
            offsetCenter: [0, -4],
            formatter: nowcastReady ? Number(nc?.nowcast_index).toFixed(2) : "{value}%",
            color: t.ink,
            fontSize: 30,
            fontWeight: 700 as const,
            fontFamily: "system-ui",
          },
          title: {
            show: true,
            offsetCenter: [0, 28],
            color: t.inkMuted,
            fontSize: 10,
            fontWeight: 600 as const,
          },
          data: [{ value: gaugePct, name: nowcastReady ? "MONTH COVERAGE" : "READINESS" }],
        },
      ],
    }),
    [gaugePct, nc?.nowcast_index, nowcastReady],
  );

  /* ---- render ---- */

  if (err) return <ApiDown error={err} />;
  if (!rows || !latest) return <div className="card mt-8 h-64 animate-pulse" />;

  const exportCsv = () => {
    const header = "date,index,inflation_dod_pct,n_cells,n_matched_products,status";
    // ="…" keeps Excel from parsing the date and rendering ##### in the
    // default-width column; other tools read the ISO string inside the quotes
    const lines = rows.map(
      (r) =>
        `="${r.date}",${r.index},${r.inflation ?? ""},${r.n_cells},${r.n_matched_products},${r.status}`,
    );
    const blob = new Blob(["﻿" + header + "\n" + lines.join("\n")], {
      type: "text/csv;charset=utf-8",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `apix_index_${windowSel ? `T+${windowSel}_` : ""}${lastDay}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="space-y-5">
      {/* title row */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-[22px] font-bold tracking-tight">Overview</h1>
        <span className="btn-ghost cursor-default">
          <IconCalendar size={15} />
          <span className="tnum">
            {fmtDate(rows[0].date)} – {fmtDate(lastDay)}
          </span>
        </span>
        <span className="btn-ghost relative" style={{ padding: 0 }}>
          <select
            value={windowSel}
            onChange={(e) => setWindowSel(Number(e.target.value))}
            className="appearance-none bg-transparent py-2 pl-3.5 pr-8 text-[13px] font-medium outline-none"
            style={{ color: "var(--ink)" }}
            aria-label="Booking-window scope for the index"
          >
            <option value={0}>Daily · all windows</option>
            {[1, 7, 15, 30, 45].map((w) => (
              <option key={w} value={w}>
                Daily · T+{w} only
              </option>
            ))}
          </select>
          <span className="pointer-events-none absolute right-2.5" style={{ color: "var(--ink-muted)" }}>
            <IconChevronDown size={14} />
          </span>
        </span>
        <button
          className="btn-api"
          onClick={async () => {
            const copiedNow = await copyText(
              apiUrl(
                `/api/apix/getAPIxIndex${windowSel ? `?leadtime_code=${windowSel}` : ""}`,
              ),
            );
            if (copiedNow) {
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }
          }}
          title="Copy the API call behind this page"
        >
          {copied ? "✓ Copied" : "API"}
        </button>
        <button className="btn-primary" onClick={exportCsv}>
          <IconDownload size={15} /> Export
        </button>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard
          label={`${monthLabel(currentMonth)} APIx · early`}
          value={currentMonthAverage?.toFixed(2) ?? latest.index.toFixed(2)}
          delta={monthVsReference}
          compare={referenceMonthAverage != null
            ? `vs. ${monthLabel(referenceMonth)} final ${referenceMonthAverage.toFixed(2)}`
            : `latest daily APIx: ${latest.index.toFixed(2)}`}
          icon={<IconActivity size={15} />}
          bubbleBg="var(--accent-soft)"
          bubbleFg="var(--accent)"
        />
        <StatCard
          label="Quotes Collected"
          value={quotesToday.toLocaleString("en-IN")}
          delta={quotesPrev ? ((quotesToday - quotesPrev) / quotesPrev) * 100 : null}
          compare={`vs. ${quotesPrev.toLocaleString("en-IN")} previous day`}
          icon={<IconDatabase size={15} />}
          bubbleBg="var(--pill-up-bg)"
          bubbleFg="var(--pill-up-fg)"
        />
        <StatCard
          label="Routes Covered"
          value={String(routesToday)}
          delta={routesPrev ? ((routesToday - routesPrev) / routesPrev) * 100 : null}
          compare={`vs. ${routesPrev} previous day`}
          icon={<IconRoute size={15} />}
          bubbleBg="#fdf1e7"
          bubbleFg="var(--series-2)"
        />
        <StatCard
          label="Matched Products"
          value={String(latest.n_matched_products)}
          compare="same flight tracked across days"
          icon={<IconLayers size={15} />}
          bubbleBg="var(--accent-soft)"
          bubbleFg="var(--accent)"
        />
      </div>

      {/* main grid */}
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        {/* index card */}
        <section className="card p-5">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-[15px] font-semibold">Daily Airfare Price Index</h2>
              <div className="mt-2 flex items-center gap-3">
                <span className="tnum text-[34px] font-bold leading-9 tracking-tight">
                  {latest.index.toFixed(2)}
                </span>
                <DeltaPill value={latest.inflation} />
                <span className="text-[12px]" style={{ color: "var(--ink-muted)" }}>
                  vs. previous day
                </span>
              </div>
            </div>
            <span className="text-[11.5px]" style={{ color: "var(--ink-muted)" }}>
              GEKS-Törnqvist · DGCA + booking-curve weights · base 100 = 31 Aug ·{" "}
              {windowSel ? `T+${windowSel} window only` : "all booking windows"}
            </span>
          </div>
          {referenceMonthAverage != null && (
            <div
              className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-[11.5px]"
              style={{ borderColor: "var(--hairline)", background: "var(--surface-2)", color: "var(--ink-secondary)" }}
            >
              <span>
                <b style={{ color: "var(--ink)" }}>{monthLabel(referenceMonth)} monthly reference:</b>{" "}
                APIx {referenceMonthAverage.toFixed(2)}
              </span>
              <span className="tnum">
                {referenceComplete
                  ? `${referenceMonthRows.length}/${referenceDaysExpected} daily observations complete`
                  : `${referenceMonthRows.length}/${referenceDaysExpected} daily observations`}
              </span>
            </div>
          )}
          <Chart build={buildIndexChart} height={250} />

          <div
            className="mt-3 rounded-xl border px-4 py-3 text-[11.5px] leading-5"
            style={{ borderColor: "var(--hairline)", color: "var(--ink-secondary)" }}
          >
            <b style={{ color: "var(--ink)" }}>
              Basket expansion from 12 to 20 DGCA routes and parser transition:
            </b>{" "}
            <span className="tnum">2 Sep</span> — parser transition to rich per-flight
            RBD observations; <span className="tnum">8 Sep</span> — basket expansion.
            Early-prototype movements, including 12 Sep,
            may also include collection-composition effects. Historical values are
            shown as observed and have not been rewritten.
          </div>

          {/* sources strip */}
          <div
            className="mt-3 rounded-xl border p-4"
            style={{ borderColor: "var(--hairline)", background: "var(--surface-2)" }}
          >
            <div className="mb-3 text-[13px] font-semibold">Sources · today</div>
            <div className="grid grid-cols-3 gap-4">
              {(["akasa", "serpapi"] as const).map((s, i) => {
                const n = today.find((h) => h.source === s)?.quotes ?? 0;
                const share = quotesToday ? (n / quotesToday) * 100 : 0;
                const color = i === 0 ? "var(--series-1)" : "var(--series-3)";
                return (
                  <div key={s}>
                    <div className="flex items-baseline gap-1.5">
                      <span className="tnum text-[17px] font-bold">{n.toLocaleString("en-IN")}</span>
                      <span className="text-[11px]" style={{ color: "var(--ink-muted)" }}>
                        {s === "akasa" ? "Akasa · airline-direct" : "SerpApi · licensed"}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 rounded-full" style={{ background: "var(--grid)" }}>
                      <div
                        className="h-1.5 rounded-full"
                        style={{ width: `${share}%`, background: color }}
                      />
                    </div>
                  </div>
                );
              })}
              <div>
                <div className="flex items-baseline gap-1.5">
                  <span className="tnum text-[17px] font-bold">
                    {(today.find((h) => h.source === "akasa")?.quotes ?? 0).toLocaleString("en-IN")}
                  </span>
                  <span className="text-[11px]" style={{ color: "var(--ink-muted)" }}>
                    with RBD + seats (PRISM)
                  </span>
                </div>
                <div className="mt-2 h-1.5 rounded-full" style={{ background: "var(--grid)" }}>
                  <div
                    className="h-1.5 rounded-full"
                    style={{
                      width: `${quotesToday ? ((today.find((h) => h.source === "akasa")?.quotes ?? 0) / quotesToday) * 100 : 0}%`,
                      background: "var(--series-2)",
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* right column */}
        <div className="space-y-4">
          <Link
            href="/nowcast"
            className="card block cursor-pointer p-5 text-center transition-transform duration-200 hover:-translate-y-0.5"
            aria-label="Open Kalman nowcast details"
          >
            <div className="flex items-center justify-between text-left">
              <h2 className="text-[15px] font-semibold">
                {nowcastReady ? `${monthLabel(nc?.month ?? currentMonth)} early Kalman nowcast` : "Nowcast Readiness"}
              </h2>
              <span className="text-[11px] font-semibold" style={{ color: "var(--accent)" }}>
                Open model &rarr;
              </span>
            </div>
            <Chart build={buildGauge} height={170} />
            <p className="-mt-2 text-[12px]" style={{ color: "var(--ink-secondary)" }}>
              {nowcastReady
                ? `${nowcastBand} | ${observedMonthDays}/${daysInMonth} days observed (${monthCoveragePct}% coverage)`
                : `${nc?.days_observed ?? 0} of ${nc?.days_required ?? 14} panel days for the Kalman CPI nowcast`}
            </p>
          </Link>

          <section className="card p-5">
            <h2 className="text-[15px] font-semibold">Collection by Day</h2>
            <p className="mt-0.5 text-[11px]" style={{ color: "var(--ink-muted)" }}>
              Three-day cadence from 31 Aug | latest day included
            </p>
            <Chart build={buildCollectionBars} height={180} />
          </section>
        </div>
      </div>

      {/* movers table */}
      <section className="card p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold">Top Moving Route Cells</h2>
          <Link href="/routes" className="text-[12.5px] font-medium" style={{ color: "var(--accent)" }}>
            View all routes →
          </Link>
        </div>
        <table className="mt-3 w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wide" style={{ color: "var(--ink-muted)" }}>
              <th className="py-2 font-medium">Route</th>
              <th className="py-2 font-medium">Window</th>
              <th className="py-2 text-right font-medium">Change vs base</th>
              <th className="py-2 text-right font-medium">Cheapest fare</th>
              <th className="py-2 text-right font-medium">Products</th>
              <th className="py-2 text-right font-medium">As of</th>
            </tr>
          </thead>
          <tbody>
            {movers.map((r) => (
              <tr key={`${r.route}-${r.leadtime_code}`} className="border-t" style={{ borderColor: "var(--hairline)" }}>
                <td className="py-2.5 font-semibold">{r.route}</td>
                <td className="py-2.5" style={{ color: "var(--ink-secondary)" }}>
                  T+{r.leadtime_code}
                </td>
                <td className="py-2.5 text-right">
                  <DeltaPill value={r.change_pct} />
                </td>
                <td className="tnum py-2.5 text-right">{inr(r.latest_fare)}</td>
                <td className="tnum py-2.5 text-right" style={{ color: "var(--ink-secondary)" }}>
                  {r.n_matched_products}
                </td>
                <td className="tnum py-2.5 text-right" style={{ color: "var(--ink-muted)" }}>
                  {r.as_of}
                </td>
              </tr>
            ))}
            {movers.length === 0 && (
              <tr>
                <td colSpan={6} className="py-4 text-[12px]" style={{ color: "var(--ink-muted)" }}>
                  Appears after two collection days per cell (matched-model requirement).
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
