# Agent Workspace design

Render a focused developer workspace: chat and prompt composer on the left, actual streamed tool telemetry on the right. Use a restrained slate/teal palette, clear typography, monospace execution details and no promotional compliance badges. Collapse the two columns on small screens.

AgentWorkspace owns request lifecycle, conversation history, readiness and cancellation. ChatPanel owns presentation and the composer. SignalResults displays measured coverage and source URLs. TelemetryConsole renders server events without inventing progress. Render final answer text safely as plain text; allow HTTP(S) source links only. Never expose server keys to the browser.

Use existing source CSS and components when extending the workspace. Further plots should display separate product histories and uncertainty rather than treating search rankings as time-series samples.
