"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Chart from "@/components/Chart";
import ChartCard from "@/components/ChartCard";
import ApiDown from "@/components/ApiDown";
import { api, inr, type HeatmapCell, type LadderRung } from "@/lib/api";
import { baseOption, type ChartTheme } from "@/lib/theme";

export default function PrismPage() {
  const [routes, setRoutes] = useState<string[]>([]);
  const [route, setRoute] = useState("DEL-BOM");
  const [rungs, setRungs] = useState<LadderRung[] | null>(null);
  const [scenario, setScenario] = useState<"filing" | "rationing">("rationing");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .heatmap()
      .then((h) =>
        setRoutes(Array.from(new Set(h.data.map((c: HeatmapCell) => c.route))).sort()),
      )
      .catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    api
      .fareLadder(route)
      .then((r) => setRungs(r.data))
      .catch((e) => setErr(String(e)));
  }, [route]);

  // one departure date at a time keeps the ladder legible: pick the date with
  // the most rungs on this route
  const shown = useMemo(() => {
    const all = rungs ?? [];
    const byDate = new Map<string, number>();
    for (const r of all) byDate.set(r.departure_date, (byDate.get(r.departure_date) ?? 0) + 1);
    const best = [...byDate.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
    return all.filter((r) => r.departure_date === best);
  }, [rungs]);

  const flights = useMemo(
    () => Array.from(new Set(shown.map((r) => `${r.flight_no} · ${r.departure_date}`))),
    [shown],
  );

  const buildLadder = useCallback(
    (t: ChartTheme) => {
      const base = baseOption(t);
      return {
        ...base,
        grid: { left: 64, right: 120, top: 16, bottom: 32 },
        xAxis: {
          ...base.xAxis,
          type: "category" as const,
          data: flights,
          axisLabel: { color: t.inkSecondary, fontSize: 11 },
        },
        yAxis: {
          ...base.yAxis,
          type: "value" as const,
          scale: true,
          axisLabel: {
            color: t.inkMuted,
            fontSize: 11,
            formatter: (v: number) => `₹${(v / 1000).toFixed(1)}k`,
          },
        },
        tooltip: {
          ...base.tooltip,
          formatter: (p: { dataIndex: number; seriesIndex: number }) => {
            const r = shown[p.dataIndex];
            return r
              ? `<b>${r.rbd}</b> — ${r.flight_no} (${r.departure_date})<br/>` +
                  `Total ${inr(r.total_fare)} · base ${inr(r.base_fare)}<br/>` +
                  `<span style="color:${t.inkMuted}">source-reported availableCount ${r.seats_available ?? "?"} at this rung · ${r.as_of}</span>`
              : "";
          },
        },
        series: [
          {
            name: "RBD rung (total fare)",
            type: "scatter" as const,
            symbol: "rect",
            symbolSize: [26, 5],
            data: shown.map((r) => [
              flights.indexOf(`${r.flight_no} · ${r.departure_date}`),
              r.total_fare,
            ]),
            itemStyle: { color: t.series[0] },
            label: {
              show: true,
              position: "right" as const,
              formatter: (p: { dataIndex: number }) => shown[p.dataIndex]?.rbd ?? "",
              color: t.inkSecondary,
              fontSize: 10,
            },
          },
        ],
      };
    },
    [shown, flights],
  );

  if (err) return <ApiDown error={err} />;

  return (
    <div className="space-y-5">
      <section className="card p-6">
        <div className="eyebrow">PRISM — Price–Rationing Index Separation Method</div>
        <p className="mt-2 max-w-3xl text-[13px]" style={{ color: "var(--ink-secondary)" }}>
          When a fare jumps ₹2,000, every other tracker calls it inflation. PRISM asks
          <i> which of two different things happened</i> — because only one of them belongs
          in the CPI. We can ask this because we capture the airline&apos;s own booking
          class (RBD) and returned availability per fare bucket, directly from its
          reservation system.
        </p>
        <div className="mt-4 flex gap-2">
          {(
            [
              ["rationing", "Lower fare rungs unavailable"],
              ["filing", "Airline re-priced the ladder"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setScenario(key)}
              className="rounded border px-3 py-1.5 text-[12px]"
              style={{
                borderColor: scenario === key ? "var(--accent)" : "var(--hairline)",
                background: scenario === key ? "var(--accent-soft)" : "transparent",
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <ScenarioDiagram scenario={scenario} />
      </section>

      <ChartCard
        title={`Observed fare ladder — ${route}`}
        subtitle="Each tick = one RBD price rung on one flight, latest collection day, captured live from the airline's reservation system (Akasa, tier-1 compliant)"
        apiPath={`/api/apix/getFareLadder?route_code=${route}`}
        right={
          <select
            value={route}
            onChange={(e) => setRoute(e.target.value)}
            className="rounded border px-2 py-1 text-[12px]"
            style={{ borderColor: "var(--hairline)", background: "var(--surface)", color: "var(--ink)" }}
          >
            {(routes.length ? routes : [route]).map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        }
      >
        {rungs === null ? (
          <div className="h-56 animate-pulse" />
        ) : rungs.length ? (
          <Chart build={buildLadder} height={300} />
        ) : (
          <p className="py-10 text-center text-[12px]" style={{ color: "var(--ink-muted)" }}>
            No RBD-level quotes for this route yet — rungs stream in from the tier-1
            airline adapter (Akasa live since 2 Sep 2026).
          </p>
        )}
      </ChartCard>

    </div>
  );
}

function ScenarioDiagram({ scenario }: { scenario: "filing" | "rationing" }) {
  // Illustrative rungs (labelled as such); the live chart below carries real data.
  const before = [3200, 4100, 5300, 6800, 8600];
  const rbds = ["U", "T", "Q", "V", "Y"];
  const after = scenario === "filing" ? before.map((v) => v + 900) : before;
  const soldBefore = 0;
  const soldAfter = scenario === "rationing" ? 2 : 0;
  return (
    <div className="mt-4 grid max-w-2xl grid-cols-2 gap-8">
      {[
        { title: "Yesterday", rungs: before, sold: soldBefore },
        { title: "Today", rungs: after, sold: soldAfter },
      ].map((col) => (
        <div key={col.title}>
          <div className="eyebrow mb-2">{col.title}</div>
          <div className="flex flex-col-reverse gap-1.5">
            {col.rungs.map((v, i) => {
              const sold = i < col.sold;
              const active = i === col.sold;
              return (
                <div key={i} className="flex items-center gap-2">
                  <span className="tnum w-8 text-[10px]" style={{ color: "var(--ink-muted)" }}>
                    {rbds[i]}
                  </span>
                  <div
                    className="h-3 rounded-sm transition-all duration-500"
                    style={{
                      width: `${28 + (v / 9500) * 60}%`,
                      background: sold
                        ? "var(--de-emphasis)"
                        : active
                          ? scenario === "rationing"
                            ? "var(--diverge-neg)"
                            : "var(--diverge-pos)"
                          : "var(--baseline)",
                      opacity: sold ? 0.45 : 1,
                    }}
                  />
                  <span className="tnum text-[10px]" style={{ color: "var(--ink-muted)" }}>
                    ₹{v.toLocaleString("en-IN")}
                    {sold ? " · unavailable" : active ? " ← lowest returned" : ""}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      ))}
      <p className="col-span-2 text-[12px]" style={{ color: "var(--ink-secondary)" }}>
        {scenario === "filing" ? (
          <>
            Every rung moved up ₹900 — a <b>filing event</b>. The traveller pays more because
            the airline re-priced the fare ladder. This movement is kept distinct from
            changes caused by lower rungs becoming unavailable.
          </>
        ) : (
          <>
            The filed rungs did not move, but the two lowest rungs were no longer returned.
            This <b>rung heuristic</b> is an availability-pressure signal,
            <b> kept separate from base-fare ladder movement</b>.
          </>
        )}{" "}
        <span style={{ color: "var(--ink-muted)" }}>(Illustrative diagram; live rungs below.)</span>
      </p>
    </div>
  );
}
