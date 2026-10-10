"""Complete evidence dependencies when a local model tries to finish too early."""

from uuid import uuid4

from langchain.agents.middleware import after_model
from langchain_core.messages import AIMessage

from .client import PramanaClient


def evidence_workflow(client: PramanaClient, trace: list[dict], max_calls: int):
    attempted: set[str] = set()

    @after_model(can_jump_to=["tools"])
    def complete_price_analysis(state, runtime):
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or last.tool_calls:
            return None
        if sum(e["type"] == "tool.started" for e in trace) >= max_calls:
            return None
        # Retail aggregates already include their constituent engine results.
        children = {
            r["result_id"]
            for value in client.results.values()
            for r in value.get("engines", [])
            if "result_id" in r
        }
        prices = [
            (rid, value)
            for rid, value in client.results.items()
            if rid not in children
            and value.get("series")
            and value.get("domain") in {"retail", "mobility"}
        ]
        for rid, _ in prices:
            if "filter_" + rid not in client.results and rid not in attempted:
                attempted.add(rid)
                return dispatch(last, "run_prism_filter", {"raw_price_data": {"result_id": rid}})
        if prices and not any(e.get("tool") == "get_market_context" for e in trace):
            query = " ".join(
                str(i.get("title", "")) for _, value in prices for i in value.get("items", [])[:2]
            )[:220]
            return dispatch(
                last, "get_market_context", {"query": query + " India market price news"}
            )
        return None

    return complete_price_analysis


def dispatch(last: AIMessage, name: str, args: dict) -> dict:
    # Replace the unfinished final message rather than showing it as a report.
    message = AIMessage(
        id=last.id,
        content="",
        tool_calls=[{"name": name, "args": args, "id": "workflow_" + uuid4().hex}],
    )
    return {"messages": [message], "jump_to": "tools"}
