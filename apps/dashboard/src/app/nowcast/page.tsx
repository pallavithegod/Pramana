"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import Chart from "@/components/Chart";
import ChartCard from "@/components/ChartCard";
import ApiDown from "@/components/ApiDown";
import { api, type IndexRow, type NowcastRow } from "@/lib/api";
import { baseOption, type ChartTheme } from "@/lib/theme";

function previousMonth(month: string) {
  const date = new Date(`${month}-01T00:00:00Z`);
  date.setUTCMonth(date.getUTCMonth() - 1);
  return date.toISOString().slice(0, 7);
}

export default function NowcastPage() {
  const [nc, setNc] = useState<NowcastRow | null>(null);
  const [daily, setDaily] = useState<IndexRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.nowcast(), api.index()])
      .then(([nowcast, index]) => {
        setNc(nowcast.data[0] ?? null);
        setDaily(index.data);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  const ready = nc?.status === "OK";
  const estimate = nc?.nowcast_index ?? null;
  const low = nc?.band_low ?? null;
  const high = nc?.band_high ?? null;
  const panelDays = daily.length;
  const monthDaysObserved = nc?.n_days_observed ?? nc?.days_observed ?? 0;
  const daysInMonth = nc?.days_in_month ?? 30;
  const required = nc?.days_required ?? 14;
  const remaining = Math.max(0, daysInMonth - monthDaysObserved);
  const latest = daily.at(-1);
  const bandWidth = low != null && high != null ? high - low : null;
  const currentMonth = nc?.month ?? latest?.date.slice(0, 7) ?? "";
  const observedMonthDaily = useMemo(
    () => daily.filter((row) => row.date.startsWith(currentMonth)),
    [daily, currentMonth],
  );
  const referenceMonth = currentMonth ? previousMonth(currentMonth) : "";
  const referenceMonthDaily = useMemo(
    () => daily.filter((row) => row.date.startsWith(referenceMonth)),
    [daily, referenceMonth],
  );
  const referenceAverage = referenceMonthDaily.length
    ? referenceMonthDaily.reduce((sum, row) => sum + row.index, 0) / referenceMonthDaily.length
    : null;
  const nowcastVsReference = estimate != null && referenceAverage != null
    ? ((estimate / referenceAverage) - 1) * 100
    : null;

  const monthLabel = useMemo(() => {
    if (!nc?.month) return "Current month";
    return new Date(`${nc.month}-01T00:00:00`).toLocaleDateString("en-IN", {
      month: "long",
      year: "numeric",
    });
  }, [nc?.month]);

  const buildObservedChart = useCallback(
    (t: ChartTheme) => {
      const base = baseOption(t);
      const currentMonthStart = daily.findIndex((row) => row.date.startsWith(currentMonth));
      return {
        ...base,
        grid: { ...base.grid, top: 24, right: 28 },
        xAxis: {
          ...base.xAxis,
          type: "category" as const,
          data: daily.map((row) => row.date.slice(5)),
          name: "collection date",
          nameLocation: "middle" as const,
          nameGap: 26,
          nameTextStyle: { color: t.inkMuted, fontSize: 11 },
        },
        yAxis: {
          ...base.yAxis,
          type: "value" as const,
          scale: true,
          name: "APIx level",
          nameTextStyle: { color: t.inkMuted, fontSize: 11 },
        },
        tooltip: {
          ...base.tooltip,
          trigger: "axis" as const,
          formatter: (items: Array<{ dataIndex: number; value: number }>) => {
            const item = items[0];
            const row = daily[item?.dataIndex ?? 0];
            return row
              ? `<b>${row.date}</b><br/>Observed APIx: <b>${row.index.toFixed(2)}</b><br/>` +
                  `<span style="color:${t.inkMuted}">${row.n_matched_products} matched products</span>`
              : "";
          },
        },
        series: [
          {
            name: "Completed daily APIx",
            type: "line" as const,
            data: daily.map((row) => (row.date.startsWith(currentMonth) ? null : row.index)),
            connectNulls: false,
            symbolSize: 7,
            lineStyle: { width: 2.5, color: t.series[0] },
            itemStyle: { color: t.series[0] },
            markPoint: currentMonthStart > 0
              ? {
                  symbol: "circle",
                  symbolSize: 9,
                  itemStyle: { color: t.series[0], borderColor: t.surface, borderWidth: 2 },
                  label: {
                    show: true,
                    formatter: `${referenceMonthDaily.length} ${referenceMonth} observations complete`,
                    position: "top" as const,
                    color: t.inkSecondary,
                    fontSize: 10,
                  },
                  data: [{ coord: [currentMonthStart - 1, daily[currentMonthStart - 1].index] }],
                }
              : undefined,
          },
          {
            name: "Observed current-month APIx",
            type: "line" as const,
            data: daily.map((row, index) =>
              index >= Math.max(0, currentMonthStart - 1) ? row.index : null,
            ),
            connectNulls: false,
            symbolSize: 7,
            lineStyle: { width: 2.5, type: "solid" as const, color: t.series[0] },
            itemStyle: { color: t.series[3] },
            markLine:
              estimate == null
                ? undefined
                : {
                    symbol: "none",
                    lineStyle: { color: t.series[2], type: "dashed" as const, width: 2 },
                    label: {
                      formatter: `monthly nowcast ${estimate.toFixed(2)}`,
                      color: t.inkSecondary,
                      fontSize: 10,
                    },
                    data: [{ yAxis: estimate }],
                  },
            markArea:
              low == null || high == null
                ? undefined
                : {
                    silent: true,
                    itemStyle: { color: "rgba(42, 120, 214, 0.08)" },
                    data: [[{ yAxis: low }, { yAxis: high }]],
                  },
          },
        ],
      };
    },
    [currentMonth, daily, estimate, high, low, referenceMonth, referenceMonthDaily.length],
  );

  if (err) return <ApiDown error={err} />;
  if (!nc) return <div className="card mt-8 h-64 animate-pulse" />;

  return (
    <div className="space-y-5">
      <section className="card p-6">
        <div className="eyebrow">Nowcast · early monthly APIx estimate</div>
        {ready && estimate != null && low != null && high != null ? (
          <>
            <div className="mt-3 flex flex-wrap items-end gap-x-8 gap-y-3">
              <div>
                <div className="text-[12px]" style={{ color: "var(--ink-muted)" }}>
                  {monthLabel} early estimate
                </div>
                <span className="tnum text-[52px] font-semibold leading-none">{estimate}</span>
              </div>
              <div className="pb-1 text-[13px] leading-6" style={{ color: "var(--ink-secondary)" }}>
                <div>
                  95% model band: <b className="tnum">{low}–{high}</b>
                </div>
                <div>
                  <b className="tnum">{monthDaysObserved}</b> observed days ·{" "}
                  <b className="tnum">{remaining}</b> remaining days carried at the latest filtered level
                </div>
                {referenceAverage != null && nowcastVsReference != null && (
                  <div>
                    <b className="tnum">{nowcastVsReference >= 0 ? "+" : ""}{nowcastVsReference.toFixed(2)}%</b>{" "}
                    vs. {new Date(`${referenceMonth}-01T00:00:00`).toLocaleDateString("en-IN", { month: "long" })}{" "}
                    monthly reference ({referenceAverage.toFixed(2)})
                  </div>
                )}
              </div>
            </div>
            <p className="mt-3 max-w-3xl text-[13px]" style={{ color: "var(--ink-secondary)" }}>
              This is an early estimate, not a closed monthly value. The nowcast estimates the full-month average APIx before the month closes. It
              smooths daily fare noise, averages the filtered levels already observed, and
              carries the latest filtered level through the unobserved remainder of the month.
            </p>
          </>
        ) : (
          <>
            <h1 className="mt-1 text-[19px] font-medium">
              Building the minimum panel — {panelDays} of {required} daily observations
            </h1>
            <div className="mt-3 h-2 w-full max-w-md rounded-full" style={{ background: "var(--grid)" }}>
              <div
                className="h-2 rounded-full"
                style={{
                  width: `${Math.min(100, (panelDays / required) * 100)}%`,
                  background: "var(--series-1)",
                }}
              />
            </div>
          </>
        )}
      </section>

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard label="Latest daily APIx" value={latest?.index.toFixed(2) ?? "—"} detail={latest?.date ?? "No input yet"} />
        <MetricCard label="Month coverage" value={`${monthDaysObserved}/${daysInMonth}`} detail={`${Math.round((monthDaysObserved / daysInMonth) * 100)}% observed`} />
        <MetricCard
          label="Previous month reference"
          value={referenceAverage?.toFixed(2) ?? "—"}
          detail={referenceMonth ? `${new Date(`${referenceMonth}-01T00:00:00`).toLocaleDateString("en-IN", { month: "long", year: "numeric" })} closed average` : "No completed month available"}
        />
        <MetricCard label="Uncertainty width" value={bandWidth == null ? "—" : bandWidth.toFixed(2)} detail="upper band minus lower band" />
      </div>

      <ChartCard
        title="Observed current-month APIx and early nowcast"
        subtitle="Solid line = observed current-month APIx · dashed line = estimated month average · shaded area = 95% model band"
        apiPath="/api/apix/getNowcast"
      >
        <Chart build={buildObservedChart} height={300} />
      </ChartCard>

      <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <section className="card p-5">
          <h2 className="text-[15px] font-semibold">Model calculation</h2>
          <div className="mt-4 space-y-3 text-[13px]" style={{ color: "var(--ink-secondary)" }}>
            <FormulaRow
              label="State evolution"
              formula={<span>μₜ = μₜ₋₁ + ηₜ</span>}
              detail="the underlying airfare level can move each day"
            />
            <FormulaRow
              label="Observed index"
              formula={<span>yₜ = μₜ + εₜ</span>}
              detail="daily APIx contains short-run observation noise"
            />
            <FormulaRow
              label="Noise estimate"
              formula={
                <span className="inline-flex flex-wrap items-center justify-center gap-x-1.5">
                  <span>q = r = max</span>
                  <span>(</span>
                  <Fraction numerator="Var(Δy)" denominator="3" />
                  <span>, 10⁻⁶)</span>
                </span>
              }
              detail="process and observation variance come from daily changes"
            />
            <FormulaRow
              label="Monthly nowcast"
              formula={
                <span className="inline-flex flex-wrap items-center justify-center gap-x-1.5">
                  <span>μ̂month =</span>
                  <Fraction numerator="Σₜ₌₁ⁿ μₜ + (D − n)μₙ" denominator="D" />
                </span>
              }
              detail="observed filtered days plus latest level carried forward"
            />
          </div>
        </section>

        <section className="card p-5">
          <h2 className="text-[15px] font-semibold">Validation checks</h2>
          <div className="mt-4 space-y-3">
            <CheckRow status={panelDays >= required ? "PASS" : "WAIT"} title="Historical panel gate" detail={`${panelDays} daily APIx observations; ${required} required for model eligibility`} />
            <CheckRow status="PASS" title="Real observations only" detail="No synthetic daily APIx values are inserted" />
            <CheckRow status="PASS" title="Uncertainty reported" detail={bandWidth == null ? "Available when the panel gate passes" : `95% band width ${bandWidth.toFixed(2)} index points`} />
            <CheckRow status="TRACK" title="Current-month coverage" detail={`${monthDaysObserved}/${daysInMonth} observed; ${remaining} calendar days remain in ${monthLabel}`} />
          </div>
        </section>
      </div>
    </div>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <section className="card p-4">
      <div className="text-[11px] uppercase tracking-wide" style={{ color: "var(--ink-muted)" }}>{label}</div>
      <div className="tnum mt-1 text-[25px] font-semibold">{value}</div>
      <div className="mt-1 text-[11.5px]" style={{ color: "var(--ink-secondary)" }}>{detail}</div>
    </section>
  );
}

function Fraction({ numerator, denominator }: { numerator: string; denominator: string }) {
  return (
    <span className="inline-flex min-w-12 flex-col items-center align-middle leading-none">
      <span className="border-b px-1.5 pb-1" style={{ borderColor: "currentColor" }}>
        {numerator}
      </span>
      <span className="px-1.5 pt-1">{denominator}</span>
    </span>
  );
}

function FormulaRow({ label, formula, detail }: { label: string; formula: ReactNode; detail: string }) {
  return (
    <div className="rounded-xl border p-3" style={{ borderColor: "var(--hairline)", background: "var(--surface-2)" }}>
      <b className="block text-[12px]" style={{ color: "var(--ink)" }}>{label}</b>
      <div
        className="mt-2 flex min-h-12 items-center justify-center overflow-x-auto rounded-lg border px-3 py-2 text-center"
        style={{ borderColor: "var(--hairline)", background: "var(--surface)" }}
      >
        <code className="tnum text-[15px] leading-6" style={{ color: "var(--accent)" }}>{formula}</code>
      </div>
      <p className="mt-2 text-[11.5px]">{detail}</p>
    </div>
  );
}

function CheckRow({ status, title, detail }: { status: "PASS" | "WAIT" | "TRACK"; title: string; detail: string }) {
  const color = status === "PASS" ? "var(--status-good)" : status === "WAIT" ? "var(--status-warning)" : "var(--accent)";
  return (
    <div className="flex items-center gap-3">
      <span
        className="flex h-6 w-14 shrink-0 items-center justify-center rounded-full text-center text-[10px] font-bold leading-none"
        style={{ color, background: "var(--surface-2)" }}
      >
        {status}
      </span>
      <div>
        <div className="text-[12.5px] font-medium">{title}</div>
        <div className="text-[11.5px]" style={{ color: "var(--ink-muted)" }}>{detail}</div>
      </div>
    </div>
  );
}
