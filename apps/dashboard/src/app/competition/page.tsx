"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Chart from "@/components/Chart";
import ChartCard from "@/components/ChartCard";
import ApiDown from "@/components/ApiDown";
import { api, type CompetitionRow } from "@/lib/api";
import { baseOption, type ChartTheme } from "@/lib/theme";

const CARRIER_NAMES: Record<string, string> = {
  "6E": "IndiGo",
  AI: "Air India",
  IX: "Air India Express",
  QP: "Akasa Air",
  SG: "SpiceJet",
  UK: "Vistara-legacy",
};

function band(hhi: number) {
  if (hhi < 1500) return { label: "Lower concentration", color: "var(--status-good)" };
  if (hhi < 2500) return { label: "Moderate concentration", color: "var(--status-warning)" };
  return { label: "High concentration", color: "var(--status-critical)" };
}

export default function CompetitionPage() {
  const [rows, setRows] = useState<CompetitionRow[] | null>(null);
  const [days, setDays] = useState(7);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setRows(null);
    setErr(null);
    api.competition(days).then((r) => setRows(r.data)).catch((e) => setErr(String(e)));
  }, [days]);

  const multi = useMemo(() => (rows ?? []).filter((row) => row.n_carriers > 1), [rows]);
  const sorted = useMemo(() => [...multi].sort((a, b) => b.hhi_observed - a.hhi_observed), [multi]);
  const medianHhi = useMemo(() => {
    const values = multi.map((row) => row.hhi_observed).sort((a, b) => a - b);
    if (!values.length) return 0;
    const middle = Math.floor(values.length / 2);
    return values.length % 2 ? values[middle] : Math.round((values[middle - 1] + values[middle]) / 2);
  }, [multi]);
  const highCount = multi.filter((row) => row.hhi_observed >= 2500).length;
  const flightObservations = multi.reduce((sum, row) => sum + row.n_flights_observed, 0);
  const example = sorted[0];

  const buildHHI = useCallback(
    (t: ChartTheme) => {
      const base = baseOption(t);
      return {
        ...base,
        grid: { left: 84, right: 42, top: 26, bottom: 42 },
        xAxis: {
          ...base.xAxis,
          type: "value" as const,
          max: 10000,
          name: "HHI = sum of squared observed flight shares × 10,000",
          nameLocation: "middle" as const,
          nameGap: 30,
          nameTextStyle: { color: t.inkMuted, fontSize: 11 },
        },
        yAxis: {
          ...base.yAxis,
          type: "category" as const,
          data: sorted.map((row) => row.route),
          splitLine: { show: false },
          axisLabel: { color: t.inkSecondary, fontSize: 11 },
        },
        tooltip: {
          ...base.tooltip,
          formatter: (p: { dataIndex: number }) => {
            const row = sorted[p.dataIndex];
            const level = band(row.hhi_observed);
            return (
              `<b>${row.route}</b> · HHI ${row.hhi_observed}<br/>` +
              `${level.label}<br/>${row.n_carriers} carriers · leader ` +
              `${CARRIER_NAMES[row.top_carrier] ?? row.top_carrier} (${row.top_share_pct}%)<br/>` +
              `<span style="color:${t.inkMuted}">${row.n_flights_observed} distinct flight numbers observed</span>`
            );
          },
        },
        series: [
          {
            type: "bar" as const,
            data: sorted.map((row) => ({
              value: row.hhi_observed,
              itemStyle: {
                color:
                  row.hhi_observed < 1500
                    ? t.series[2]
                    : row.hhi_observed < 2500
                      ? t.series[3]
                      : t.series[1],
                borderRadius: [0, 4, 4, 0],
              },
            })),
            barWidth: 13,
            markLine: {
              symbol: "none",
              lineStyle: { color: t.baseline, type: "dashed" as const },
              label: { color: t.inkMuted, fontSize: 10 },
              data: [
                { xAxis: 1500, label: { formatter: "1,500" } },
                { xAxis: 2500, label: { formatter: "2,500" } },
              ],
            },
          },
        ],
      };
    },
    [sorted],
  );

  if (err) return <ApiDown error={err} />;
  if (!rows) return <div className="card mt-8 h-64 animate-pulse" />;

  return (
    <div className="space-y-5">
      <section className="card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="eyebrow">Competition · observed route concentration</div>
            <h1 className="mt-1 text-[19px] font-medium">How concentrated is observed flight frequency?</h1>
            <p className="mt-2 max-w-3xl text-[13px]" style={{ color: "var(--ink-secondary)" }}>
              Each carrier&apos;s share is based on distinct flight numbers observed on a
              route. Squaring those shares gives more influence to carriers with a larger
              service presence; summing them produces the route&apos;s HHI.
            </p>
          </div>
          <label className="text-[12px]" style={{ color: "var(--ink-secondary)" }}>
            Observation window
            <select
              value={days}
              onChange={(event) => setDays(Number(event.target.value))}
              className="mt-1 block rounded-lg border px-3 py-2 text-[13px]"
              style={{ borderColor: "var(--hairline)", background: "var(--surface)", color: "var(--ink)" }}
            >
              <option value={7}>Latest 7 days</option>
              <option value={14}>Latest 14 days</option>
              <option value={30}>Latest 30 days</option>
            </select>
          </label>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <MetricCard label="Multi-carrier routes" value={`${multi.length}/${rows.length}`} detail="included in the comparison" />
        <MetricCard label="Median observed HHI" value={medianHhi.toLocaleString("en-IN")} detail={band(medianHhi).label} />
        <MetricCard label="High-concentration routes" value={String(highCount)} detail="HHI at or above 2,500" />
        <MetricCard label="Flight-number observations" value={flightObservations.toLocaleString("en-IN")} detail={`distinct within each route · ${days} days`} />
      </div>

      <ChartCard
        title="Observed-frequency HHI by route"
        subtitle={`Multi-carrier routes · SerpAPI distinct-flight-number shares · latest ${days} collection days`}
        apiPath={`/api/apix/getCompetition?days=${days}`}
      >
        {multi.length ? (
          <Chart build={buildHHI} height={Math.max(260, multi.length * 30 + 80)} />
        ) : (
          <p className="py-10 text-center text-[12px]" style={{ color: "var(--ink-muted)" }}>
            No multi-carrier routes are present in this observation window.
          </p>
        )}
      </ChartCard>

      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <section className="card p-5">
          <h2 className="text-[15px] font-semibold">How the score is calculated</h2>
          <div className="mt-4 rounded-xl border p-4" style={{ borderColor: "var(--hairline)", background: "var(--surface-2)" }}>
            <div className="tnum text-center text-[16px] font-semibold" style={{ color: "var(--accent)" }}>
              sᵢ = flightsᵢ / total route flights
            </div>
            <div className="tnum mt-2 text-center text-[18px] font-semibold">
              HHI = Σ(sᵢ²) × 10,000
            </div>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center text-[11.5px]">
            <BandCard color="var(--status-good)" range="Below 1,500" label="Lower" />
            <BandCard color="var(--status-warning)" range="1,500–2,499" label="Moderate" />
            <BandCard color="var(--status-critical)" range="2,500+" label="High" />
          </div>
          {example && (
            <p className="mt-4 text-[12px]" style={{ color: "var(--ink-secondary)" }}>
              Example: <b>{example.route}</b> has HHI <b>{example.hhi_observed.toLocaleString("en-IN")}</b>. Its leading observed carrier is <b>{CARRIER_NAMES[example.top_carrier] ?? example.top_carrier}</b> with <b>{example.top_share_pct}%</b> of distinct flight numbers in this window.
            </p>
          )}
        </section>

        <section className="card p-5">
          <h2 className="text-[15px] font-semibold">Method validation</h2>
          <div className="mt-4 space-y-3">
            <CheckRow title="Comparable source panel" detail="Only SerpAPI observations enter HHI, keeping carrier coverage consistent" />
            <CheckRow title="Deduplicated frequency unit" detail="Each carrier-flight number counts once within a route and lookback window" />
            <CheckRow title="Explicit lookback" detail={`Current calculation uses the latest ${days} collection days`} />
            <CheckRow title="Multi-carrier chart" detail={`${rows.length - multi.length} single-carrier observations excluded from the comparison chart`} />
          </div>
          <p className="mt-4 rounded-lg px-3 py-2 text-[11.5px]" style={{ color: "var(--ink-muted)", background: "var(--surface-2)" }}>
            Interpretation: this measures concentration in observed flight frequency. It is a route-screening indicator, distinct from seat capacity, passenger share or a finding about pricing conduct.
          </p>
        </section>
      </div>

      <section className="card overflow-x-auto p-5">
        <h2 className="text-[15px] font-semibold">Route detail</h2>
        <table className="mt-3 min-w-[760px] w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px]" style={{ color: "var(--ink-muted)" }}>
              <th className="py-1 font-medium">Route</th>
              <th className="py-1 text-right font-medium">HHI</th>
              <th className="py-1 font-medium" style={{ paddingLeft: 16 }}>Band</th>
              <th className="py-1 text-right font-medium">Carriers</th>
              <th className="py-1 font-medium" style={{ paddingLeft: 16 }}>Leader</th>
              <th className="py-1 text-right font-medium">Leader share</th>
              <th className="py-1 text-right font-medium">Flights</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => {
              const level = band(row.hhi_observed);
              return (
                <tr key={row.route} className="border-t" style={{ borderColor: "var(--hairline)" }}>
                  <td className="py-2.5 font-medium">{row.route}</td>
                  <td className="tnum py-2.5 text-right">{row.hhi_observed.toLocaleString("en-IN")}</td>
                  <td className="py-2.5" style={{ paddingLeft: 16, color: level.color }}>{level.label}</td>
                  <td className="tnum py-2.5 text-right">{row.n_carriers}</td>
                  <td className="py-2.5" style={{ paddingLeft: 16 }}>{CARRIER_NAMES[row.top_carrier] ?? row.top_carrier}</td>
                  <td className="tnum py-2.5 text-right">{row.top_share_pct}%</td>
                  <td className="tnum py-2.5 text-right">{row.n_flights_observed}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <section className="card p-4">
      <div className="text-[11px] uppercase tracking-wide" style={{ color: "var(--ink-muted)" }}>{label}</div>
      <div className="tnum mt-1 text-[24px] font-semibold">{value}</div>
      <div className="mt-1 text-[11.5px]" style={{ color: "var(--ink-secondary)" }}>{detail}</div>
    </section>
  );
}

function BandCard({ color, range, label }: { color: string; range: string; label: string }) {
  return (
    <div className="rounded-lg border p-2" style={{ borderColor: "var(--hairline)" }}>
      <div className="mx-auto mb-1 h-1.5 w-8 rounded-full" style={{ background: color }} />
      <div className="tnum font-medium">{range}</div>
      <div style={{ color: "var(--ink-muted)" }}>{label}</div>
    </div>
  );
}

function CheckRow({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="flex gap-3">
      <span className="mt-1 h-2 w-2 shrink-0 rounded-full" style={{ background: "var(--status-good)" }} />
      <div>
        <div className="text-[12.5px] font-medium">{title}</div>
        <div className="text-[11.5px]" style={{ color: "var(--ink-muted)" }}>{detail}</div>
      </div>
    </div>
  );
}
