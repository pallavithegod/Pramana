export type Dialogue = {
    role: "user" | "assistant";
    content: string;
};
export type Signal = {
    product_id: string;
    title?: string;
    status: string;
    currency: string;
    n_observations: number;
    smoothed_baseline?: number;
    innovation_z?: number;
};
export type Report = {
    run_id: string;
    answer: string;
    status: string;
    searches_used: number;
    tool_calls: number;
    citations: string[];
    measurements: {
        series?: Signal[];
    }[];
};
export type AgentEvent = {
    type: string;
    tool?: string;
    status?: string;
    timestamp?: string;
    duration_ms?: number;
    count?: number;
    searches_used?: number;
    model?: string;
    error?: {
        message: string;
    };
    report?: Report;
};
export async function streamChat(message: string, history: Dialogue[], signal: AbortSignal, onEvent: (event: AgentEvent) => void) {
    const response = await fetch("/api/chat/stream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message, history: history.slice(-12) }), signal });
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail?.message ?? body.detail?.code ?? `Chat unavailable (${response.status})`);
    }
    if (!response.body)
        throw new Error("Streaming response unavailable");
    const reader = response.body.getReader(), decoder = new TextDecoder();
    let buffer = "", finished = false;
    try {
        while (true) {
            const { value, done } = await reader.read();
            buffer += decoder.decode(value, { stream: !done });
            let split;
            while ((split = buffer.indexOf("\n\n")) >= 0) {
                const frame = buffer.slice(0, split);
                buffer = buffer.slice(split + 2);
                const data = frame.split("\n").filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
                if (data) {
                    const event: AgentEvent = JSON.parse(data);
                    if (event.type === "run.completed" || event.type === "run.failed")
                        finished = true;
                    onEvent(event);
                }
            }
            if (done)
                break;
        }
        if (!finished)
            throw new Error("Connection ended before the agent finished");
    }
    finally {
        await reader.cancel().catch(() => { });
        reader.releaseLock();
    }
}
