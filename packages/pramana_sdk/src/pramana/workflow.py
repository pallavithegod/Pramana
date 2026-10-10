"""Complete evidence dependencies when a local model tries to finish too early."""

from uuid import uuid4

from langchain.agents.middleware import after_model, before_model
from langchain_core.messages import AIMessage

from .client import PramanaClient


def evidence_workflow(client: PramanaClient, trace: list[dict], max_calls: int):
    attempted: set[str] = set()

    @before_model(can_jump_to=["tools"])
    def link_evidence_steps(state, runtime):
        # Numerical dependencies do not require another expensive local inference round.
        # Reuse the guarded planner on a fresh AI message, appending a valid tool call
        # after the preceding ToolMessage instead of replacing that tool result.
        if not state["messages"] or state["messages"][-1].type != "tool":
            return None
        return complete_price_analysis({"messages": [AIMessage(content="")]}, runtime)

    def complete_price_analysis(state, runtime):
        last = state["messages"][-1]
        if not isinstance(last, AIMessage):
            return None
        if sum(e["type"] == "tool.started" for e in trace) >= max_calls:
            return None
        plans = [r for r in client.results.values() if r.get("kind") == "investigation"]
        filters = [
            r for r in client.results.values() if r.get("method") == "pramana-kalman-local-level-v1"
        ]
        news_started = any(e.get("tool") == "get_market_context" for e in trace)
        if last.tool_calls:
            # A model proposing News after PRISM must first expose its selection decision.
            if len(last.tool_calls) == 1 and last.tool_calls[0]["name"] == "get_market_context":
                if filters and not plans:
                    return dispatch(last, "plan_investigation", {})
                if plans and plans[-1].get("next_search") and not news_started:
                    last = last.model_copy(deep=True)
                    last.tool_calls[0]["args"] = {"query": plans[-1]["next_search"]["query"]}
                    return {"messages": [last]}
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
        if filters and not plans and not any(e.get("tool") == "plan_investigation" for e in trace):
            return dispatch(last, "plan_investigation", {})
        if prices and not news_started:
            if plans:
                search = plans[-1].get("next_search")
                if search:
                    return dispatch(last, search["tool"], {"query": search["query"]})
                return None
            query = " ".join(
                str(i.get("title", "")) for _, value in prices for i in value.get("items", [])[:2]
            )[:220]
            return dispatch(
                last, "get_market_context", {"query": query + " India market price news"}
            )
        return None

    return [link_evidence_steps, after_model(can_jump_to=["tools"])(complete_price_analysis)]


def dispatch(last: AIMessage, name: str, args: dict) -> dict:
    # Replace the unfinished final message rather than showing it as a report.
    message = AIMessage(
        id=last.id,
        content="",
        tool_calls=[{"name": name, "args": args, "id": "workflow_" + uuid4().hex}],
    )
    return {"messages": [message], "jump_to": "tools"}
