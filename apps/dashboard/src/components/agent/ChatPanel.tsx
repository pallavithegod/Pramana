import type { FormEvent } from "react";
import type { Dialogue, Report } from "@/lib/chat";
import SignalResults from "./SignalResults";
export type ChatEntry = Dialogue & {
    report?: Report;
};
export default function ChatPanel({ entries, value, setValue, send, cancel, running, error }: {
    entries: ChatEntry[];
    value: string;
    setValue: (value: string) => void;
    send: () => void;
    cancel: () => void;
    running: boolean;
    error: string;
}) {
    function submit(event: FormEvent) { event.preventDefault(); send(); }
    return <main className="chat-panel"><div className="chat-scroll">
 {!entries.length && <div className="welcome"><div className="eyebrow">EMPIRICAL RESEARCH, ON DEMAND</div><h1>Follow the signal.</h1><p>Ask a question. Pramāna searches live markets, filters comparable price history, and investigates possible drivers.</p><div className="examples">{["Compare Shopping and Amazon prices for a Samsung 990 PRO 1TB SSD. Filter the signal and investigate recent price drivers.", "Find data engineer roles in Bengaluru and Pune. Compare advertised pay coverage and search labor-market news.", "Find nonstop DEL to BOM economy fares. Ask me for my departure date first."].map((prompt, i) => <button key={prompt} onClick={() => setValue(prompt)}><span>0{i + 1}</span>{prompt}<b>↗</b></button>)}</div><div className="capabilities">Flights · Hotels · Shopping · Jobs · News · PRISM</div></div>}
 {entries.map((entry, index) => <article className={`message ${entry.role}`} key={index}><div className="message-label">{entry.role === "user" ? "YOU" : "PRAMĀNA"}</div><div className="message-body">{entry.content}</div>{entry.report && <SignalResults report={entry.report}/>}</article>)}
 {running && <div className="working" role="status">◌ Agent is working. Follow tool execution in the console.</div>}{error && <div className="error" role="alert">{error}</div>}
 </div><form className="composer" onSubmit={submit}><label htmlFor="prompt">RESEARCH PROMPT</label><textarea id="prompt" value={value} onChange={event => setValue(event.target.value)} placeholder="What would you like to investigate? Include dates, cities and product specifications." maxLength={8000} disabled={running} rows={3}/><div className="composer-bottom"><span>Local model · live market tools</span>{running ? <button type="button" onClick={cancel}>Stop run ■</button> : <button disabled={!value.trim()} type="submit">Run research ↗</button>}</div></form></main>;
}
