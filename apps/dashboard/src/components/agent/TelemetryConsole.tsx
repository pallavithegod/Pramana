import type { AgentEvent } from "@/lib/chat";
const labels: Record<string, string> = { get_flight_fares: "Fetching SerpApi Google Flights", get_hotel_rates: "Fetching SerpApi Google Hotels", get_retail_prices: "Fetching Shopping / Amazon prices", get_labor_salaries: "Fetching SerpApi Google Jobs", get_market_context: "Searching SerpApi Google News", run_prism_filter: "Running PRISM Kalman filter", plan_investigation: "Ranking price uncertainty / innovations" };
export default function TelemetryConsole({ events, running }: {
    events: AgentEvent[];
    running: boolean;
}) {
    const visible = events.filter(e => e.type !== "heartbeat");
    return <aside className="telemetry"><div className="console-header"><span>◉ TELEMETRY CONSOLE</span><span className={running ? "live" : ""}>{running ? "LIVE" : "IDLE"}</span></div><p className="console-hint">Tool execution · streamed from the local agent</p><div className="trace" role="log" aria-label="Tool telemetry" aria-live="polite">
 {!visible.length && <div className="trace-empty">Awaiting a research prompt.<br />Your tool calls will appear here.</div>}
 {visible.map((event, index) => <div className="trace-event" key={index}><time>{event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "--:--:--"}</time><div><strong>{event.type === "tool.started" ? labels[event.tool ?? ""] ?? event.tool : event.type === "tool.completed" ? `${event.tool} → ${event.status}` : event.type === "investigation.planned" ? "Next investigation selected" : event.type}</strong><p>{event.type === "tool.completed" ? `${event.count ?? 0} results · ${event.duration_ms} ms · ${event.searches_used} searches` : event.decision ? `${event.decision.selected?.title ?? "No candidate"} · ${event.decision.reason}` : event.error?.message ?? event.model ?? ""}</p></div></div>)}
 </div><div className="console-footer">OLLAMA + SERPAPI + PRISM<span>local inference</span></div></aside>;
}
