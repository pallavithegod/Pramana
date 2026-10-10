"""LangChain @tool bindings with per-run budgets, provenance and telemetry."""

import json
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Literal

from langchain.tools import tool

from .client import PramanaClient
from .errors import PramanaError
from .filter import run_prism_filter as filter_signal
from .investigation import fingerprint
from .investigation import plan_investigation as plan_signal

EventSink = Callable[[dict], Awaitable[None]]


def compact_tool_result(result: dict) -> dict:
    """Keep full evidence server-side and bounded summaries in the model's context."""
    view = {k: v for k, v in result.items() if k not in {"engines", "series", "items"}}
    if "items" in result:
        view["items"] = result["items"][:8]
        view["total_items"] = len(result["items"])
    if "series" in result:
        view["series"] = [
            {
                **{k: v for k, v in item.items() if k not in {"points", "trajectory"}},
                **({"n_observations": len(item["points"])} if "points" in item else {}),
            }
            for item in result["series"][:8]
        ]
        view["total_series"] = len(result["series"])
    if "ranked_candidates" in view:
        view["ranked_candidates"] = view["ranked_candidates"][:8]
        view["total_candidates"] = len(result["ranked_candidates"])
    if any(len(result.get(key, [])) > 8 for key in ["items", "series", "ranked_candidates"]):
        view["context_note"] = "First 8 shown; full evidence is retained in the saved report."
    return view


def create_tools(
    client: PramanaClient, emit: EventSink | None = None, max_tool_calls: int = 16
) -> list:
    """Create named tools sharing a run-local client; standalone SDK consumers can inject it."""
    calls = 0

    async def invoke(name: str, action: Callable[[], Awaitable[dict]]) -> dict:
        nonlocal calls
        calls += 1
        started = monotonic()
        if emit:
            await emit({"type": "tool.started", "tool": name, "call": calls})
        try:
            if calls > max_tool_calls:
                raise PramanaError("TOOL_BUDGET_EXCEEDED", "This run reached its tool-call limit")
            result = await action()
        except PramanaError as exc:
            result = exc.as_dict()
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            result = PramanaError("INVALID_TOOL_INPUT", "Use the documented input schema").as_dict()
        if emit:
            await emit(
                {
                    "type": "tool.completed",
                    "tool": name,
                    "call": calls,
                    "status": result["status"],
                    "duration_ms": round((monotonic() - started) * 1000),
                    "result_id": result.get("result_id"),
                    "count": len(
                        result.get(
                            "items", result.get("series", result.get("ranked_candidates", []))
                        )
                    ),
                    "searches_used": client.gateway.searches_used,
                    "error": result.get("error"),
                }
            )
        return compact_tool_result(result)

    @tool
    async def get_flight_fares(origin: str, destination: str, departure_date: str) -> dict:
        """Fetch INR nonstop economy fares. Use IATA codes and YYYY-MM-DD departure date."""
        return await invoke(
            "get_flight_fares", lambda: client.get_flight_fares(origin, destination, departure_date)
        )

    @tool
    async def get_hotel_rates(
        location: str, check_in: str, check_out: str, adults: int = 1
    ) -> dict:
        """Fetch Google Hotels nightly INR rates. Dates are YYYY-MM-DD; room terms vary."""
        return await invoke(
            "get_hotel_rates", lambda: client.get_hotel_rates(location, check_in, check_out, adults)
        )

    @tool
    async def get_retail_prices(
        query: str, source: Literal["shopping", "amazon", "both"] = "both"
    ) -> dict:
        """Fetch exact-spec goods via Google Shopping/Amazon India; both costs two searches."""
        return await invoke("get_retail_prices", lambda: client.get_retail_prices(query, source))

    @tool
    async def get_labor_salaries(
        query: str, location: str, next_page_token: str | None = None
    ) -> dict:
        """Fetch Google Jobs postings and optional advertised salaries; never infer missing pay."""
        return await invoke(
            "get_labor_salaries",
            lambda: client.get_labor_salaries(query, location, next_page_token),
        )

    @tool
    async def get_market_context(query: str) -> dict:
        """Fetch dated Google News sources to investigate plausible drivers; not causal proof."""
        return await invoke("get_market_context", lambda: client.get_market_context(query))

    @tool
    async def plan_investigation() -> dict:
        """Choose one bounded follow-up news search using trusted PRISM outputs.

        Call after run_prism_filter. Returns ranked uncertainty/innovation scores,
        the selected signal and a next_search query, or an explicit coverage gap.
        It consumes no search credits. News cannot reduce the price posterior variance.
        """

        async def action() -> dict:
            inputs = [
                r
                for r in client.results.values()
                if r.get("method") == "pramana-kalman-local-level-v1"
            ]
            if not inputs:
                raise PramanaError("FILTER_REQUIRED", "Run PRISM on a fetched price result first")
            remaining = max(0, client.gateway.max_searches - client.gateway.searches_used)
            result = plan_signal(inputs, remaining)
            client.decisions.append(
                {
                    "inputs": inputs,
                    "searches_remaining": remaining,
                    "expected_sha256": fingerprint(result),
                    "policy": result["policy"],
                }
            )
            result = {
                **result,
                "result_id": "plan_" + result["decision_id"],
                "kind": "investigation",
            }
            client.results[result["result_id"]] = result
            if emit:
                await emit({"type": "investigation.planned", "decision": result})
            return result

        return await invoke("plan_investigation", action)

    @tool
    async def run_prism_filter(raw_price_data: dict) -> dict:
        """Filter a prior price tool's JSON. Pass {"result_id":"result_..."} from that output.

        The server loads its trusted comparable history. Do not invent observations.
        Returns per-product baseline estimates or explicit insufficient_history.
        """

        async def action() -> dict:
            rid = raw_price_data.get("result_id")
            if rid not in client.results:
                raise PramanaError(
                    "UNKNOWN_PRICE_RESULT", "Fetch prices first and pass its result_id"
                )
            result = filter_signal(client.results[rid])
            result["input_result_id"] = rid
            client.results["filter_" + rid] = result
            return result

        return await invoke("run_prism_filter", action)

    return [
        get_flight_fares,
        get_hotel_rates,
        get_retail_prices,
        get_labor_salaries,
        get_market_context,
        run_prism_filter,
        plan_investigation,
    ]
