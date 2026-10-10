import asyncio
import json

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pramana import PramanaClient, Settings, run_prism_filter
from pramana.agent import AgentRuntime
from pramana.errors import PramanaError
from pramana.normalize import amazon, flights, hotels, jobs, news, shopping
from pramana.providers import SerpApiGateway
from pramana.store import SignalStore
from pramana.tools import create_tools
from pydantic import SecretStr


def shopping_payload():
    return {
        "shopping_results": [
            {
                "product_id": "ssd-1",
                "title": "SSD 1TB",
                "source": "Shop",
                "price": "INR 8000",
                "extracted_price": 8000,
                "product_link": "https://example.com/product",
            }
        ]
    }


def test_engine_parsers_reject_unusable_measurements():
    assert shopping(shopping_payload(), {"q": "SSD"})[0]["currency"] == "INR"
    assert (
        shopping(
            {"shopping_results": [{"product_id": "x", "extracted_price": 2, "price": "$2"}]},
            {"q": "SSD"},
        )
        == []
    )
    assert (
        amazon(
            {"organic_results": [{"asin": "ABC", "price": {"value": 500, "currency": "INR"}}]},
            {"amazon_domain": "amazon.in"},
        )[0]["value"]
        == 500
    )
    assert hotels(
        {
            "properties": [
                {
                    "name": "Hotel",
                    "property_token": "token",
                    "rate_per_night": {"extracted_lowest": 1000},
                }
            ]
        },
        {
            "check_in_date": "2026-11-01",
            "check_out_date": "2026-11-02",
            "adults": 1,
            "currency": "INR",
        },
    )[0]["unit"].startswith("night")
    params = {
        "departure_id": "DEL",
        "arrival_id": "BOM",
        "outbound_date": "2026-11-01",
        "currency": "INR",
    }
    payload = {
        "best_flights": [
            {
                "price": 4000,
                "flights": [
                    {
                        "departure_airport": {"id": "DEL"},
                        "arrival_airport": {"id": "BOM"},
                        "flight_number": "AI 123",
                        "travel_class": "Economy",
                    }
                ],
            }
        ]
    }
    assert flights(payload, params)[0]["base_fare"] is None
    payload["best_flights"][0]["flights"].append({})
    assert flights(payload, params) == []
    assert (
        jobs({"jobs_results": [{"job_id": "job1", "title": "Engineer"}]}, {})[0]["salary_text"]
        is None
    )
    assert (
        news(
            {
                "news_results": [
                    {"stories": [{"title": "Event", "link": "https://example.com/news"}]}
                ]
            },
            {},
        )[0]["title"]
        == "Event"
    )


def test_filter_preserves_math_and_requires_real_comparable_history():
    points = [
        {"observed_at": f"2026-10-0{i + 1}T10:00:00+00:00", "value": price, "currency": "INR"}
        for i, price in enumerate([100, 110, 105, 300])
    ]
    data = {"series": [{"product_id": "ssd", "currency": "INR", "points": points}]}
    result = run_prism_filter(json.dumps(data))["series"][0]
    from apix_index.nowcast import local_level_filter

    mu, _ = local_level_filter([100, 110, 105, 300], q=result["q"], r=result["r"])
    assert result["smoothed_baseline"] == pytest.approx(mu[-1])
    assert 105 < result["smoothed_baseline"] < 300
    assert (
        run_prism_filter({"series": [{**data["series"][0], "points": points[:1]}]})["status"]
        == "insufficient_history"
    )
    points[-1]["currency"] = "USD"
    with pytest.raises(ValueError, match="one currency"):
        run_prism_filter(data)


def test_provider_budget_partial_results_and_secret_redaction(tmp_path):
    async def check():
        gateway = SerpApiGateway("", max_searches=1, search=lambda _: shopping_payload())
        client = PramanaClient(gateway, SignalStore(tmp_path / "runtime.sqlite"))
        result = await client.get_retail_prices("SSD", "both")
        assert result["status"] == "partial" and len(result["items"]) == 1
        assert gateway.searches_used == 1
        tools = {t.name: t for t in create_tools(client)}
        error = await tools["run_prism_filter"].ainvoke(
            {"raw_price_data": {"result_id": "invented"}}
        )
        assert error["error"]["code"] == "UNKNOWN_PRICE_RESULT"

        def fail(_):
            raise RuntimeError("sensitive api_key=secret")

        with pytest.raises(PramanaError) as caught:
            await SerpApiGateway("", search=fail).search({"engine": "google_news"})
        assert "secret" not in str(caught.value)

    asyncio.run(check())


class ScriptedToolModel(BaseChatModel):
    """Native tool-calling protocol test: real LangChain graph, fake external inference."""

    @property
    def _llm_type(self):
        return "scripted-test-model"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        replies = [m for m in messages if isinstance(m, ToolMessage)]
        if not replies:
            name, args = "get_retail_prices", {"query": "SSD", "source": "shopping"}
        elif len(replies) == 1:
            rid = json.loads(replies[-1].content)["result_id"]
            name, args = "run_prism_filter", {"raw_price_data": {"result_id": rid}}
        elif len(replies) == 2:
            name, args = "get_market_context", {"query": "SSD prices India"}
        else:
            return ChatResult(
                generations=[
                    ChatGeneration(
                        message=AIMessage(
                            content="Observed SSD price: INR 8000. History is insufficient. News is a hypothesis."
                        )
                    )
                ]
            )
        message = AIMessage(
            content="", tool_calls=[{"name": name, "args": args, "id": f"call_{len(replies)}"}]
        )
        return ChatResult(generations=[ChatGeneration(message=message)])


def test_actual_langchain_fetch_filter_news_loop_and_report_storage(tmp_path):
    def search(params):
        if params["engine"] == "google_shopping":
            return shopping_payload()
        return {"news_results": [{"title": "SSD supply", "link": "https://example.com/news"}]}

    async def check():
        store = SignalStore(tmp_path / "runtime.sqlite")
        runtime = AgentRuntime(
            Settings(serpapi_key=SecretStr("test")),
            store,
            model=ScriptedToolModel(),
            gateway_factory=lambda: SerpApiGateway("", search=search),
        )
        events = [event async for event in runtime.events("Find SSD prices, filter, and explain")]
        assert [e["tool"] for e in events if e["type"] == "tool.started"] == [
            "get_retail_prices",
            "run_prism_filter",
            "get_market_context",
        ]
        report = events[-1]["report"]
        assert report["status"] == "partial" and report["searches_used"] == 2
        assert report["tool_calls"] == 3
        assert store.report(report["run_id"]) == report
        assert "https://example.com/news" in report["citations"]

    asyncio.run(check())


def test_local_model_configuration_rejects_hosted_llms():
    with pytest.raises(ValueError, match="loopback"):
        Settings(ollama_base_url="https://example.com")


class EarlyFinishModel(ScriptedToolModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if any(isinstance(m, ToolMessage) for m in messages):
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content="Finished too early"))]
            )
        return super()._generate(messages, stop, run_manager, **kwargs)


def test_workflow_completes_dependencies_when_model_finishes_early(tmp_path):
    async def check():
        runtime = AgentRuntime(
            Settings(),
            SignalStore(tmp_path / "runtime.sqlite"),
            model=EarlyFinishModel(),
            gateway_factory=lambda: SerpApiGateway("", search=lambda _: shopping_payload()),
        )
        events = [event async for event in runtime.events("Analyze SSD price drivers")]
        assert [e["tool"] for e in events if e["type"] == "tool.started"] == [
            "get_retail_prices",
            "run_prism_filter",
            "get_market_context",
        ]
        assert events[-1]["type"] == "run.completed"

    asyncio.run(check())
