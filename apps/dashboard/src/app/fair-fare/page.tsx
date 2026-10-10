"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Chart from "@/components/Chart";
import ApiDown from "@/components/ApiDown";
import { api, inr, type HeatmapCell, type QuoteRow } from "@/lib/api";
import { baseOption, type ChartTheme } from "@/lib/theme";

const WINDOWS = [1, 7, 15, 30, 45];
const CARRIER_NAMES: Record<string, string> = {
  "6E": "IndiGo",
  AI: "Air India",
  IX: "Air India Express",
  QP: "Akasa Air",
  SG: "SpiceJet",
  UK: "Vistara-legacy",
};

function leadBucket(days: number) {
  return WINDOWS.reduce((best, current) =>
    Math.abs(current - days) < Math.abs(best - days) ? current : best,
  );
}

function quantile(sorted: number[], q: number) {
  if (!sorted.length) return null;
  const position = (sorted.length - 1) * q;
  const lower = Math.floor(position);
  const fraction = position - lower;
  return sorted[lower + 1] == null
    ? sorted[lower]
    : sorted[lower] + fraction * (sorted[lower + 1] - sorted[lower]);
}

export default function FairFarePage() {
  const [routes, setRoutes] = useState<string[]>([]);
  const [route, setRoute] = useState("DEL-BOM");
  const [price, setPrice] = useState("");
  const [leadWindow, setLeadWindow] = useState(0);
  const [source, setSource] = useState("all");
  const [carrier, setCarrier] = useState("all");
  const [quotes, setQuotes] = useState<QuoteRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .heatmap()
      .then((response) => {
        const available = Array.from(
          new Set(response.data.map((cell: HeatmapCell) => cell.route)),
        ).sort();
        setRoutes(available);
        if (available.length && !available.includes(route)) setRoute(available[0]);
      })
      .catch((e) => setErr(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setQuotes(null);
    setErr(null);
    api.fairFarePanel(route).then((response) => setQuotes(response.data)).catch((e) => setErr(String(e)));
  }, [route]);

  const latest = useMemo(() => {
    if (!quotes?.length) return [];
    const day = quotes.reduce(
      (current, quote) => (quote.collected_at > current ? quote.collected_at : current),
      "",
    ).slice(0, 10);
    return quotes.filter((quote) => quote.collected_at.startsWith(day));
  }, [quotes]);

  const availableSources = useMemo(
    () => Array.from(new Set(latest.map((quote) => quote.source))).sort(),
    [latest],
  );
  const availableCarriers = useMemo(
    () =>
      Array.from(
        new Set(
          latest
            .filter((quote) => source === "all" || quote.source === source)
            .map((quote) => quote.carrier),
        ),
      ).sort(),
    [latest, source],
  );

  const comparable = useMemo(
    () =>
      latest.filter(
        (quote) =>
          (leadWindow === 0 || leadBucket(quote.lead_days) === leadWindow) &&
          (source === "all" || quote.source === source) &&
          (carrier === "all" || quote.carrier === carrier),
      ),
    [carrier, latest, leadWindow, source],
  );

  const fares = useMemo(
    () => comparable.map((quote) => quote.total_fare).sort((a, b) => a - b),
    [comparable],
  );
  const p25 = quantile(fares, 0.25);
  const median = quantile(fares, 0.5);
  const p75 = quantile(fares, 0.75);
  const quotedPrice = Number(price);
  const hasQuote = Number.isFinite(quotedPrice) && quotedPrice > 0 && fares.length > 0;
  const percentile = hasQuote
    ? Math.round((fares.filter((fare) => fare <= quotedPrice).length / fares.length) * 100)
    : null;
  const difference = hasQuote && median != null ? quotedPrice - median : null;
  const differencePct = difference != null && median ? (difference / median) * 100 : null;

  const verdict =
    percentile == null
      ? null
      : percentile <= 25
        ? { title: "Strong value in this comparison set", detail: "At least three quarters of comparable observed fares are higher.", color: "var(--status-good)" }
        : percentile <= 60
          ? { title: "Within the typical observed range", detail: "Your quote sits near the middle of comparable fares.", color: "var(--accent)" }
          : percentile <= 85
            ? { title: "Above most comparable fares", detail: "Check nearby flights or booking windows before purchasing.", color: "var(--status-serious)" }
            : { title: "Near the top of the observed range", detail: "Most comparable fares in the current panel are lower.", color: "var(--status-critical)" };

  const cheapestOffers = useMemo(() => {
    const seen = new Set<string>();
    return [...comparable]
      .sort((a, b) => a.total_fare - b.total_fare)
      .filter((quote) => {
        const key = `${quote.carrier}|${quote.flight_no}|${quote.departure_date}|${quote.total_fare}|${quote.source}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, 6);
  }, [comparable]);

  const buildDistribution = useCallback(
    (t: ChartTheme) => {
      const base = baseOption(t);
      const min = fares[0] ?? 0;
      const max = fares.at(-1) ?? min;
      const binCount = Math.min(8, Math.max(4, Math.ceil(Math.sqrt(fares.length))));
      const width = Math.max(1, (max - min) / binCount);
      const counts = Array.from({ length: binCount }, () => 0);
      for (const fare of fares) {
        const index = Math.min(binCount - 1, Math.floor((fare - min) / width));
        counts[index] += 1;
      }
      const labels = counts.map((_, index) => {
        const start = min + index * width;
        const end = index === binCount - 1 ? max : start + width;
        return `₹${Math.round(start / 100) * 100}–${Math.round(end / 100) * 100}`;
      });
      const quoteBin = hasQuote && quotedPrice >= min && quotedPrice <= max
        ? Math.max(0, Math.min(binCount - 1, Math.floor((quotedPrice - min) / width)))
        : -1;
      return {
        ...base,
        grid: { left: 42, right: 20, top: 20, bottom: 58 },
        xAxis: {
          ...base.xAxis,
          type: "category" as const,
          data: labels,
          axisLabel: { color: t.inkMuted, fontSize: 10, rotate: 22 },
        },
        yAxis: {
          ...base.yAxis,
          type: "value" as const,
          minInterval: 1,
          name: "quotes",
          nameTextStyle: { color: t.inkMuted, fontSize: 10 },
        },
        tooltip: { ...base.tooltip, trigger: "axis" as const },
        series: [
          {
            name: "Comparable fares",
            type: "bar" as const,
            data: counts.map((count, index) => ({
              value: count,
              itemStyle: {
                color: index === quoteBin ? t.series[1] : t.series[0],
                borderRadius: [4, 4, 0, 0],
              },
            })),
            barMaxWidth: 48,
          },
        ],
      };
    },
    [fares, hasQuote, quotedPrice],
  );

  if (err) return <ApiDown error={err} />;

  return (
    <div className="space-y-5">
      <section className="card p-6">
        <div className="eyebrow">Fair Fare · live market comparison</div>
        <h1 className="mt-1 text-[20px] font-semibold">How does your quote compare?</h1>
        <p className="mt-1 max-w-3xl text-[13px]" style={{ color: "var(--ink-secondary)" }}>
          Build a like-for-like comparison by route, booking window, source and carrier,
          then place your quoted all-in fare inside the latest observed distribution.
        </p>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <Control label="Route">
            <select
              value={route}
              onChange={(event) => {
                setRoute(event.target.value);
                setLeadWindow(0);
                setSource("all");
                setCarrier("all");
              }}
              className="w-full rounded-lg border px-3 py-2 text-[13px]"
              style={controlStyle}
            >
              {(routes.length ? routes : [route]).map((item) => <option key={item}>{item}</option>)}
            </select>
          </Control>

          <Control label="Booking window">
            <select value={leadWindow} onChange={(event) => setLeadWindow(Number(event.target.value))} className="w-full rounded-lg border px-3 py-2 text-[13px]" style={controlStyle}>
              <option value={0}>All windows</option>
              {WINDOWS.map((window) => <option key={window} value={window}>T+{window}</option>)}
            </select>
          </Control>

          <Control label="Source">
            <select
              value={source}
              onChange={(event) => {
                setSource(event.target.value);
                setCarrier("all");
              }}
              className="w-full rounded-lg border px-3 py-2 text-[13px]"
              style={controlStyle}
            >
              <option value="all">All sources</option>
              {availableSources.map((item) => <option key={item} value={item}>{item === "serpapi" ? "SerpAPI" : "Akasa direct"}</option>)}
            </select>
          </Control>

          <Control label="Carrier">
            <select value={carrier} onChange={(event) => setCarrier(event.target.value)} className="w-full rounded-lg border px-3 py-2 text-[13px]" style={controlStyle}>
              <option value="all">All carriers</option>
              {availableCarriers.map((item) => <option key={item} value={item}>{CARRIER_NAMES[item] ?? item}</option>)}
            </select>
          </Control>

          <Control label="Your quote · ₹ all-in">
            <input
              value={price}
              onChange={(event) => setPrice(event.target.value.replace(/[^\d]/g, ""))}
              inputMode="numeric"
              placeholder="e.g. 6500"
              className="tnum w-full rounded-lg border px-3 py-2 text-[13px]"
              style={controlStyle}
            />
          </Control>
        </div>

        {fares.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[11.5px]" style={{ color: "var(--ink-muted)" }}>
            <span>Try a benchmark:</span>
            {[["25th percentile", p25], ["Median", median], ["75th percentile", p75]].map(([label, value]) => (
              <button key={String(label)} className="btn-ghost" style={{ padding: "4px 9px", fontSize: 11 }} onClick={() => value != null && setPrice(String(Math.round(Number(value))))}>
                {label} · {inr(Number(value))}
              </button>
            ))}
          </div>
        )}
      </section>

      {quotes === null ? (
        <div className="card h-64 animate-pulse" />
      ) : fares.length === 0 ? (
        <section className="card p-8 text-center">
          <h2 className="text-[15px] font-medium">No comparable fares in this filter</h2>
          <p className="mt-2 text-[12px]" style={{ color: "var(--ink-muted)" }}>Broaden the booking-window, source or carrier selection.</p>
        </section>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <MetricCard label="Lowest observed" value={inr(fares[0])} detail="bottom of comparison set" />
            <MetricCard label="Typical range" value={`${inr(p25)}–${inr(p75)}`} detail="25th to 75th percentile" />
            <MetricCard label="Median fare" value={inr(median)} detail={`${fares.length} comparable quotes`} />
            <MetricCard label="Highest observed" value={inr(fares.at(-1))} detail={`collected ${latest[0]?.collected_at.slice(0, 10)}`} />
          </div>

          {hasQuote && verdict && percentile != null && (
            <section className="card p-5">
              <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
                <div>
                  <div className="text-[11px] uppercase tracking-wide" style={{ color: "var(--ink-muted)" }}>Your quote percentile</div>
                  <div className="tnum mt-1 text-[46px] font-semibold leading-none">{percentile}<span className="text-[16px]">th</span></div>
                  <div className="mt-2 text-[12px]" style={{ color: "var(--ink-secondary)" }}>
                    {difference == null ? "" : `${difference >= 0 ? "+" : "−"}${inr(Math.abs(difference))} (${Math.abs(differencePct ?? 0).toFixed(1)}%) ${difference >= 0 ? "above" : "below"} median`}
                  </div>
                </div>
                <div className="rounded-xl border p-4" style={{ borderColor: verdict.color }}>
                  <h2 className="text-[16px] font-semibold" style={{ color: verdict.color }}>{verdict.title}</h2>
                  <p className="mt-1 text-[13px]" style={{ color: "var(--ink-secondary)" }}>{verdict.detail}</p>
                  <div className="mt-3 h-2 w-full rounded-full" style={{ background: "var(--grid)" }}>
                    <div className="h-2 rounded-full transition-all" style={{ width: `${percentile}%`, background: verdict.color }} />
                  </div>
                </div>
              </div>
            </section>
          )}

          <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
            <section className="card p-5">
              <h2 className="text-[15px] font-semibold">Observed fare distribution</h2>
              <p className="mt-1 text-[11.5px]" style={{ color: "var(--ink-muted)" }}>The orange bar contains your quote when it falls inside the observed range.</p>
              <Chart build={buildDistribution} height={270} />
            </section>

            <section className="card overflow-x-auto p-5">
              <h2 className="text-[15px] font-semibold">Lowest comparable offers observed</h2>
              <table className="mt-3 min-w-[500px] w-full text-[12px]">
                <thead>
                  <tr className="text-left text-[10.5px] uppercase tracking-wide" style={{ color: "var(--ink-muted)" }}>
                    <th className="py-1 font-medium">Carrier / flight</th>
                    <th className="py-1 font-medium">Departure</th>
                    <th className="py-1 text-right font-medium">Lead</th>
                    <th className="py-1 font-medium" style={{ paddingLeft: 12 }}>Source</th>
                    <th className="py-1 text-right font-medium">Fare</th>
                  </tr>
                </thead>
                <tbody>
                  {cheapestOffers.map((quote, index) => (
                    <tr key={`${quote.carrier}-${quote.flight_no}-${quote.departure_date}-${quote.total_fare}-${index}`} className="border-t" style={{ borderColor: "var(--hairline)" }}>
                      <td className="py-2.5 font-medium">{CARRIER_NAMES[quote.carrier] ?? quote.carrier} · {quote.flight_no ?? "—"}</td>
                      <td className="tnum py-2.5">{quote.departure_date}</td>
                      <td className="tnum py-2.5 text-right">T+{quote.lead_days}</td>
                      <td className="py-2.5" style={{ paddingLeft: 12 }}>{quote.source === "serpapi" ? "SerpAPI" : "Akasa"}</td>
                      <td className="tnum py-2.5 text-right font-semibold">{inr(quote.total_fare)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>
        </>
      )}

      <p className="text-[11px]" style={{ color: "var(--ink-muted)" }}>
        Comparison uses offers observed on {latest[0]?.collected_at.slice(0, 10) ?? "the latest collection day"}. Percentile describes position inside the selected evidence set; it is not a legal or normative determination of fairness and is not a booking recommendation.
      </p>
    </div>
  );
}

const controlStyle = {
  borderColor: "var(--hairline)",
  background: "var(--surface)",
  color: "var(--ink)",
};

function Control({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="text-[11.5px]" style={{ color: "var(--ink-secondary)" }}>{label}<div className="mt-1">{children}</div></label>;
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <section className="card p-4">
      <div className="text-[11px] uppercase tracking-wide" style={{ color: "var(--ink-muted)" }}>{label}</div>
      <div className="tnum mt-1 text-[22px] font-semibold">{value}</div>
      <div className="mt-1 text-[11.5px]" style={{ color: "var(--ink-secondary)" }}>{detail}</div>
    </section>
  );
}
