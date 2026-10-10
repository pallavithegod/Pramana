"use client";
import { useEffect, useRef, useState } from "react";
import { streamChat, type AgentEvent, type Report } from "@/lib/chat";
import ChatPanel, { type ChatEntry } from "./ChatPanel";
import EvidencePanel from "./EvidencePanel";
import SignalResults from "./SignalResults";
import TelemetryConsole from "./TelemetryConsole";

type View = "workspace" | "signals" | "evidence";
const snapshotKey = "pramana.latest-report.v1";
const views: { id: View; label: string; number: string }[] = [
  { id: "workspace", label: "Agent Workspace", number: "01" },
  { id: "signals", label: "PRISM Signal Studio", number: "02" },
  { id: "evidence", label: "Evidence Replay Vault", number: "03" },
];

export default function AgentWorkspace() {
  const [entries, setEntries] = useState<ChatEntry[]>([]), [events, setEvents] = useState<AgentEvent[]>([]);
  const [value, setValue] = useState(""), [running, setRunning] = useState(false), [error, setError] = useState("");
  const [model, setModel] = useState("Checking local model…"), [ready, setReady] = useState(false);
  const [view, setView] = useState<View>("workspace"), [snapshot, setSnapshot] = useState<Report | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    try {
      const cached = localStorage.getItem(snapshotKey);
      if (cached) setSnapshot(JSON.parse(cached) as Report);
    } catch { localStorage.removeItem(snapshotKey); }
    const check = new AbortController();
    fetch("/api/chat/status", { signal: check.signal }).then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(s => { setModel(`${s.model} · ${s.ollama}${s.serpapi === "key_missing" ? " · SerpApi key missing" : ""}`); setReady(s.ollama === "ready" && s.serpapi === "configured"); })
      .catch(e => { if (e.name !== "AbortError") setModel("Backend offline · start FastAPI"); });
    return () => { check.abort(); controller.current?.abort(); };
  }, []);

  async function send() {
    if (controller.current || !value.trim()) return;
    const message = value.trim(), history = entries.map(({ role, content }) => ({ role, content }));
    setEntries(previous => [...previous, { role: "user", content: message }]);
    setValue(""); setEvents([]); setError(""); setRunning(true);
    const abort = new AbortController(); controller.current = abort;
    try {
      await streamChat(message, history, abort.signal, event => {
        setEvents(previous => [...previous, event]);
        if (event.type === "run.completed" && event.report) {
          const report = event.report;
          setSnapshot(report);
          try { localStorage.setItem(snapshotKey, JSON.stringify(report)); } catch { /* Snapshot remains available in this session. */ }
          setEntries(previous => [...previous, { role: "assistant", content: report.answer, report }]);
        }
        if (event.type === "run.failed") setError(event.error?.message ?? "Agent execution failed");
      });
    } catch (e) { setError(abort.signal.aborted ? "Run stopped." : e instanceof Error ? e.message : "Connection failed"); }
    finally { controller.current = null; setRunning(false); }
  }

  const latestReport = [...entries].reverse().find(entry => entry.report)?.report ?? snapshot;
  return <div className="workspace">
    <header className="workspace-header">
      <a className="brand" href="#workspace" onClick={e => { e.preventDefault(); setView("workspace"); }} aria-label="Pramāna home">
        <span className="brand-mark">p.</span><strong>Pramāna</strong><span className="brand-divider" />
      </a>
      <nav className="top-tabs" aria-label="Main views">{views.map(item => <button key={item.id} className={`top-tab ${view === item.id ? "active" : ""}`} onClick={() => setView(item.id)} aria-current={view === item.id ? "page" : undefined}><span>{item.number}</span>{item.label}</button>)}</nav>
      <div className="model-status"><i className={ready ? "ready" : ""}/>{model}</div>
    </header>
    <section className={`view-panel ${view === "workspace" ? "view-active" : "view-inactive"}`} aria-hidden={view !== "workspace"}>
      <div className="workspace-body"><ChatPanel entries={entries} value={value} setValue={setValue} send={send} cancel={() => controller.current?.abort()} running={running} error={error}/><TelemetryConsole events={events} running={running}/></div>
    </section>
    <section className={`view-panel ${view === "signals" ? "view-active" : "view-inactive"}`} aria-hidden={view !== "signals"}>
      <main className="studio-view"><div className="view-heading"><div><div className="eyebrow">FILTERED MARKET OBSERVATIONS</div><h1>PRISM Signal Studio</h1><p>Raw observations, smoothed price baseline, and conditional uncertainty bands.</p></div><span className="view-index">SIGNAL / 02</span></div>
        {latestReport ? <SignalResults report={latestReport} snapshotMode={Boolean(error || !latestReport.measurements.some(m => m.series?.some(s => (s.trajectory?.length ?? 0) >= 3)))}/> : <div className="empty-snapshot"><span className="snapshot-badge">Snapshot unavailable</span><h2>No saved economic observations</h2><p>Run an investigation in Agent Workspace. Completed observations are saved locally for signal review and remain visible if a later run fails.</p><button onClick={() => setView("workspace")}>Open Agent Workspace</button></div>}
      </main>
    </section>
    <section className={`view-panel ${view === "evidence" ? "view-active" : "view-inactive"}`} aria-hidden={view !== "evidence"}>
      <main className="studio-view"><div className="view-heading"><div><div className="eyebrow">LOCAL PROVENANCE · OFFLINE REPLAY</div><h1>Evidence Replay Vault</h1><p>Inspect captured evidence and reproduce filter and decision outputs without network calls.</p></div><span className="view-index">EVIDENCE / 03</span></div>
        {latestReport ? <div className="vault-card"><div className="vault-meta"><span>RUN <b>{latestReport.run_id}</b></span><span>STATUS <b>{latestReport.status}</b></span><span>CAPTURE <b>{latestReport.evidence ? "AVAILABLE" : "UNAVAILABLE"}</b></span></div><EvidencePanel report={latestReport}/></div> : <div className="empty-snapshot"><span className="snapshot-badge">No evidence captured</span><h2>The vault is waiting for a run</h2><p>Run an agent investigation to capture a replayable evidence bundle, then return here to verify and export it.</p><button onClick={() => setView("workspace")}>Start an investigation</button></div>}
      </main>
    </section>
  </div>;
}
