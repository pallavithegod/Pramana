"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Chart from "@/components/Chart";
import ChartCard from "@/components/ChartCard";
import ApiDown from "@/components/ApiDown";
import { api, type LedgerStatus, type SourceHealthRow } from "@/lib/api";
import { baseOption, type ChartTheme } from "@/lib/theme";

/** Verdicts pinned in services/collectors/src/collectors/policy.py (browser-verified
 * 31 Aug 2026). This table IS the compliance story — including what we refused. */
const COMPLIANCE = [
  { source: "Akasa Air (airline)", verdict: "Collected — live daily", detail: "robots.txt has no Disallow; site-minted token reused, never forged", tone: "good" },
  { source: "SerpApi Google Flights", verdict: "Collected — licensed API", detail: "commercial licence covers redistribution for research", tone: "good" },
  { source: "SpiceJet (airline)", verdict: "REFUSED — bot management", detail: "robots-clean, but token endpoint 403s automated browsers (Cloudflare). We treat that refusal as binding, like robots.txt — no fingerprint evasion. Parser ready for licensed/file feeds.", tone: "warning" },
  { source: "EaseMyTrip (OTA)", verdict: "Parser ready — file ingestion", detail: "listing path disallowed by robots; non-listing funnel governed per-URL. Richest fare split (base/YQ/RBD) from captures.", tone: "warning" },
  { source: "DGCA tariff sheets (Rule 135(2))", verdict: "Tier-2 reference — not yet joined", detail: "candidate external-validation source for PRISM filing events; not part of the current computed output", tone: "warning" },
  { source: "MakeMyTrip / Goibibo / IndiGo", verdict: "NOT collected", detail: "robots.txt disallows fare-search paths — documented adapters only, never run", tone: "critical" },
];

export default function TrustPage() {
  const [health, setHealth] = useState<SourceHealthRow[] | null>(null);
  const [ledger, setLedger] = useState<LedgerStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.sourceHealth().then((h) => setHealth(h.data)).catch((e) => setErr(String(e)));
    api.ledgerStatus().then((l) => setLedger(l.data[0] ?? null)).catch(() => setLedger(null));
  }, []);

  const days = useMemo(
    () => Array.from(new Set((health ?? []).map((h) => h.date))).sort(),
    [health],
  );
  const sources = useMemo(
    () => Array.from(new Set((health ?? []).map((h) => h.source))).sort(),
    [health],
  );

  const buildVolumes = useCallback(
    (t: ChartTheme) => {
      const base = baseOption(t);
      return {
        ...base,
        legend: {
          top: 0,
          textStyle: { color: t.inkSecondary, fontSize: 11 },
          itemWidth: 12,
          itemHeight: 8,
        },
        xAxis: { ...base.xAxis, type: "category" as const, data: days },
        yAxis: { ...base.yAxis, type: "value" as const },
        tooltip: { ...base.tooltip, trigger: "axis" as const },
        series: sources.map((s, i) => ({
          name: s,
          type: "bar" as const,
          stack: "quotes",
          barWidth: 26,
          itemStyle: { color: t.series[i % t.series.length], borderColor: t.surface, borderWidth: 2 },
          data: days.map(
            (d) => (health ?? []).find((h) => h.source === s && h.date === d)?.quotes ?? 0,
          ),
        })),
      };
    },
    [health, days, sources],
  );

  if (err) return <ApiDown error={err} />;

  return (
    <div className="space-y-5">
      <section className="card p-6">
        <div className="eyebrow">Trust · provenance & compliance</div>
        <p className="mt-2 max-w-3xl text-[13px]" style={{ color: "var(--ink-secondary)" }}>
          An index for official statistics is only as good as the auditability of its
          collection. Every source below carries a verdict verified in a real browser and
          pinned in code — a transient robots.txt failure can never silently unlock a
          disallowed target. The sources we <b>refused</b> are listed with the same
          prominence as the ones we use.
        </p>
      </section>

      <section className="card p-5">
        <h2 className="text-[15px] font-medium">Compliance matrix</h2>
        <table className="mt-3 w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px]" style={{ color: "var(--ink-muted)" }}>
              <th className="py-1 font-medium">Source</th>
              <th className="py-1 font-medium">Verdict</th>
              <th className="py-1 font-medium">Basis</th>
            </tr>
          </thead>
          <tbody>
            {COMPLIANCE.map((r) => (
              <tr key={r.source} className="border-t align-top" style={{ borderColor: "var(--hairline)" }}>
                <td className="py-2.5 pr-3 font-medium">{r.source}</td>
                <td className="py-2.5 pr-3 whitespace-nowrap">
                  <span
                    className="mr-1.5 inline-block h-2 w-2 rounded-full"
                    style={{ background: `var(--status-${r.tone})` }}
                    aria-hidden
                  />
                  {r.verdict}
                </td>
                <td className="py-2.5" style={{ color: "var(--ink-secondary)" }}>
                  {r.detail}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <ChartCard
        title="Collection volumes by source"
        subtitle="Persisted fare quotes per collection day (deduplicated by quote fingerprint)"
        apiPath="/api/apix/getSourceHealth"
      >
        {health ? <Chart build={buildVolumes} height={260} /> : <div className="h-52 animate-pulse" />}
      </ChartCard>

      <section className="card p-5">
        <h2 className="text-[15px] font-medium">Evidence ledger</h2>
        <p className="mt-2 max-w-3xl text-[13px]" style={{ color: "var(--ink-secondary)" }}>
          Every raw response is archived <i>before</i> parsing
          (<code>data/raw/&lt;source&gt;/&lt;date&gt;/</code>) and every stored quote keeps a{" "}
          <code>raw_ref</code> to its exact source file. A hash chain seals the archive:
          each entry binds a file&apos;s SHA-256 to the previous entry, so any edit or
          deletion after sealing breaks the chain arithmetic. Verified live on request:
        </p>
        {ledger ? (
          <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-[13px]">
            <span className="flex items-center gap-1.5">
              <span
                aria-hidden
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: ledger.intact ? "var(--status-good)" : "var(--status-critical)" }}
              />
              {ledger.intact ? "Chain intact" : "CHAIN BROKEN"}
            </span>
            <span className="tnum" style={{ color: "var(--ink-secondary)" }}>
              {ledger.entries.toLocaleString("en-IN")} evidence files sealed
            </span>
            <span className="tnum text-[11px]" style={{ color: "var(--ink-muted)" }}>
              head {ledger.head?.slice(0, 16)}… · sealed {ledger.last_sealed_at}
            </span>
          </div>
        ) : (
          <p className="mt-3 text-[12px]" style={{ color: "var(--ink-muted)" }}>
            Ledger status unavailable.
          </p>
        )}
      </section>
    </div>
  );
}
