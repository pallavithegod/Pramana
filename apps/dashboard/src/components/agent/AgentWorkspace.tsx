"use client";
import { useEffect, useRef, useState } from "react";
import { streamChat, type AgentEvent } from "@/lib/chat";
import ChatPanel, { type ChatEntry } from "./ChatPanel";
import TelemetryConsole from "./TelemetryConsole";
export default function AgentWorkspace() {
    const [entries, setEntries] = useState<ChatEntry[]>([]), [events, setEvents] = useState<AgentEvent[]>([]);
    const [value, setValue] = useState(""), [running, setRunning] = useState(false), [error, setError] = useState("");
    const [model, setModel] = useState("Checking local model…"), [ready, setReady] = useState(false);
    const controller = useRef<AbortController | null>(null);
    useEffect(() => { const check = new AbortController(); fetch("/api/chat/status", { signal: check.signal }).then(r => { if (!r.ok)
        throw new Error(); return r.json(); }).then(s => { setModel(`${s.model} · ${s.ollama}${s.serpapi === "key_missing" ? " · SerpApi key missing" : ""}`); setReady(s.ollama === "ready" && s.serpapi === "configured"); }).catch(e => { if (e.name !== "AbortError")
        setModel("Backend offline · start FastAPI"); }); return () => { check.abort(); controller.current?.abort(); }; }, []);
    async function send() {
        if (controller.current || !value.trim())
            return;
        const message = value.trim(), history = entries.map(({ role, content }) => ({ role, content }));
        setEntries(previous => [...previous, { role: "user", content: message }]);
        setValue("");
        setEvents([]);
        setError("");
        setRunning(true);
        const abort = new AbortController();
        controller.current = abort;
        try {
            await streamChat(message, history, abort.signal, event => {
                setEvents(previous => [...previous, event]);
                if (event.type === "run.completed" && event.report) {
                    const report = event.report;
                    setEntries(previous => [...previous, { role: "assistant", content: report.answer, report }]);
                }
                if (event.type === "run.failed")
                    setError(event.error?.message ?? "Agent execution failed");
            });
        }
        catch (e) {
            setError(abort.signal.aborted ? "Run stopped." : e instanceof Error ? e.message : "Connection failed");
        }
        finally {
            controller.current = null;
            setRunning(false);
        }
    }
    return <div className="workspace"><header className="workspace-header"><div className="brand"><span className="brand-mark">p.</span><strong>Pramāna</strong><span className="workspace-tag">Agent Workspace</span></div><div className="model-status"><i className={ready ? "ready" : ""}/>{model}</div></header><div className="workspace-body"><ChatPanel entries={entries} value={value} setValue={setValue} send={send} cancel={() => controller.current?.abort()} running={running} error={error}/><TelemetryConsole events={events} running={running}/></div></div>;
}
