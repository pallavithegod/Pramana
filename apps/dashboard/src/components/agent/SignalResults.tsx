import type { Report } from "@/lib/chat";
import SignalChart from "./SignalChart";
import EvidencePanel from "./EvidencePanel";
export default function SignalResults({ report }: {
    report: Report;
}) {
    const signals = report.measurements.flatMap(m => m.series ?? []).filter(s => s.status);
    const sources = report.citations.filter(url => /^https?:\/\//.test(url));
    return <div className="signal-results"><div className="report-meta">{report.status} · {report.searches_used} searches · {report.tool_calls} tool calls</div>
 {!!signals.length && <details open><summary>Price signal coverage ({signals.length})</summary><div className="signal-grid">{signals.map((s, i) => <div className="signal" key={i}><strong>{s.title ?? s.product_id}</strong><p>{s.smoothed_baseline != null ? `${s.currency} ${s.smoothed_baseline.toFixed(2)} baseline estimate` : "Insufficient comparable history"}</p><small>{s.n_observations} observations{s.innovation_z != null ? ` · innovation z ${s.innovation_z.toFixed(2)}` : ""}</small><SignalChart signal={s} /></div>)}</div></details>}
 <EvidencePanel report={report} />
 {!!sources.length && <details><summary>Sources ({sources.length})</summary>{sources.map(url => <a className="source" href={url} key={url} target="_blank" rel="noreferrer">{url}</a>)}</details>}</div>;
}
