"use client";
import { useState } from "react";
import type { Report } from "@/lib/chat";
function download(report: Report) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${report.run_id}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export default function EvidencePanel({ report }: {
    report: Report;
}) {
    const [busy, setBusy] = useState(false), [result, setResult] = useState("");
    async function replay() {
        if (busy)
            return;
        setBusy(true);
        setResult("");
        try {
            const response = await fetch(`/api/chat/reports/${encodeURIComponent(report.run_id)}/replay`);
            const body = await response.json();
            if (!response.ok)
                throw new Error(body.detail?.message ?? body.detail?.code ?? "Replay unavailable");
            if (body.status === "verified")
                setResult(`${body.filters.length} filters and ${body.decisions.length} decisions reproduced. No searches or model inference used.`);
            else
                setResult(body.status === "integrity_mismatch" ? "Saved evidence fingerprint does not match. Replay was stopped." : "Recomputed numerical outputs differ from the capture. Inspect the exported evidence and runtime versions.");
        }
        catch (error) {
            setResult(error instanceof Error ? error.message : "Replay failed");
        }
        finally {
            setBusy(false);
        }
    }
    return <div className="evidence-panel">{report.investigations?.map(plan => <details className="investigation" key={plan.decision_id} open><summary>Investigation decision</summary>
    <p className="decision-title">{plan.selected?.title ?? "No eligible signal"}</p><p>{plan.reason}</p>
    <div className="decision-metrics"><span>{plan.selected?.relative_uncertainty != null ? `${(100 * plan.selected.relative_uncertainty).toFixed(2)}% relative uncertainty` : "Coverage gap · no estimate"}</span><span>{plan.searches_remaining} searches available at decision</span></div>
    {plan.next_search && <p className="decision-query">Next query: {plan.next_search.query}</p>}
    <details><summary>Compare candidate priorities ({plan.ranked_candidates.length})</summary><div className="candidate-scroll"><table><thead><tr><th>Signal</th><th>Relative uncertainty</th><th>Innovation z</th><th>Priority</th></tr></thead><tbody>{plan.ranked_candidates.map(c => <tr key={`${c.product_id}-${c.currency}`}><td>{c.title}</td><td>{c.relative_uncertainty == null ? "Insufficient history" : `${(c.relative_uncertainty * 100).toFixed(2)}%`}</td><td>{c.innovation_z?.toFixed(2) ?? "—"}</td><td>{c.priority_score?.toFixed(4) ?? "—"}</td></tr>)}</tbody></table></div></details>
    <small>Contextual news does not reduce the price posterior variance or prove causality.</small>
  </details>)}
    <div className="evidence-actions"><button onClick={() => download(report)}>Export evidence JSON ↓</button>{report.evidence != null && <button disabled={busy} onClick={replay}>{busy ? "Recomputing…" : "Replay captured evidence ↻"}</button>}</div>
    {result && <p className="replay-result" role="status">{result}</p>}
  </div>;
}
