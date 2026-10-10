import type { FormEvent } from "react";
import type { Dialogue, Report } from "@/lib/chat";
import SignalResults from "./SignalResults";
export type ChatEntry = Dialogue & { report?: Report };

const presets = [
  { icon: "⚡", label: "SSD Price Shock", source: "Shopping + News", prompt: "Analyze Samsung 990 PRO 1TB SSD price volatility and investigate NAND supply drivers.", tone: "purple" },
  { icon: "✈", label: "Metro Airfare Inflation", source: "Flights + News", prompt: "Track Delhi to Bengaluru dynamic airfare volatility across October.", tone: "cyan" },
  { icon: "◈", label: "Tech Wage vs Living Cost", source: "Jobs + Hotels", prompt: "Compare Senior Engineer salaries in Bengaluru against temporary accommodation rates.", tone: "amber" },
];

export default function ChatPanel({ entries, value, setValue, send, cancel, running, error }: {
  entries: ChatEntry[]; value: string; setValue: (value: string) => void; send: () => void; cancel: () => void; running: boolean; error: string;
}) {
  function submit(event: FormEvent) { event.preventDefault(); send(); }
  return <main className="chat-panel"><div className="chat-scroll">
    {!entries.length && <div className="welcome"><div className="eyebrow"><span className="eyebrow-dot"/> LIVE ECONOMIC INTELLIGENCE</div><h1>Follow the signal.</h1><p>Investigate live prices, filter market noise, and explore the forces behind a shift.</p><div className="welcome-meta"><span>LOCAL INFERENCE</span><span>LIVE SERPAPI SOURCES</span><span>PRISM FILTER</span></div></div>}
    {entries.map((entry, index) => <article className={`message ${entry.role}`} key={index}><div className="message-label">{entry.role === "user" ? "YOU" : "PRAMĀNA"}</div><div className="message-body">{entry.content}</div>{entry.report && <SignalResults report={entry.report}/>}</article>)}
    {running && <div className="working" role="status"><i/> Agent is working. Follow tool execution in the telemetry console.</div>}{error && <div className="error" role="alert"><b>RUN INTERRUPTED</b><span>{error}</span><small>Your last completed signal snapshot remains available in PRISM Signal Studio.</small></div>}
  </div><form className="composer" onSubmit={submit}>
    <div className="composer-head"><label htmlFor="prompt">RESEARCH PROMPT</label><span>SHIFT + ENTER FOR NEW LINE</span></div>
    <div className="preset-row" aria-label="Quick benchmark scenarios">{presets.map(preset => <button type="button" key={preset.label} className={`preset-chip ${preset.tone}`} onClick={() => setValue(preset.prompt)} disabled={running}><span>{preset.icon}</span><b>{preset.label}</b><small>{preset.source}</small></button>)}</div>
    <textarea id="prompt" value={value} onChange={event => setValue(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); if (!running) send(); } }} placeholder="Ask about a product, route, city, or labor market…" maxLength={8000} disabled={running} rows={3}/>
    <div className="composer-bottom"><span><i/> Local model · live market tools</span>{running ? <button className="run-button stop-button" type="button" onClick={cancel}>Stop run <span>■</span></button> : <button className="run-button" disabled={!value.trim()} type="submit">Run investigation <span>↗</span></button>}</div>
  </form></main>;
}
