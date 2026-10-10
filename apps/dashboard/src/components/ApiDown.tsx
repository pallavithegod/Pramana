import { API_BASE } from "@/lib/api";

/** Honest failure state (DESIGN.md §6): name the cause, say how to fix it. */
export default function ApiDown({ error }: { error: string }) {
  return (
    <div className="card mx-auto mt-16 max-w-xl p-6">
      <h2 className="text-[15px] font-medium">API not reachable</h2>
      <p className="mt-2 text-[13px]" style={{ color: "var(--ink-secondary)" }}>
        The dashboard reads live data from the Air-Sankhyiki API at{" "}
        <code className="tnum">{API_BASE}</code> and could not reach it.
      </p>
      <p className="mt-2 text-[13px]" style={{ color: "var(--ink-secondary)" }}>
        Start it from the repo root:
      </p>
      <pre
        className="mt-2 rounded border p-3 text-xs"
        style={{ borderColor: "var(--hairline)", background: "var(--page)" }}
      >
        uv run --project apps/api uvicorn api.main:app --host 127.0.0.1 --port 8001
      </pre>
      <p className="mt-3 text-[11px]" style={{ color: "var(--ink-muted)" }}>
        {error}
      </p>
    </div>
  );
}
