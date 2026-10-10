import asyncio
import json
from copy import deepcopy

import pytest
from pramana.agent import AgentRuntime
from pramana.config import Settings
from pramana.filter import run_prism_filter
from pramana.investigation import LEGACY_POLICY, fingerprint, plan_investigation
from pramana.normalize import shopping
from pramana.providers import SerpApiGateway
from pramana.replay import build_evidence, replay_evidence
from pramana.store import SignalStore
from pramana.tools import compact_tool_result
from test_agent_sdk import EarlyFinishModel, shopping_payload


class CountedModel(EarlyFinishModel):
    calls: int = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        return super()._generate(messages, stop, run_manager, **kwargs)


def signal(pid, baseline, variance, z=0):
    return {
        "product_id": pid,
        "title": pid,
        "currency": "INR",
        "status": "ok",
        "n_observations": 12,
        "smoothed_baseline": baseline,
        "posterior_variance": variance,
        "innovation_z": z,
    }


def test_priority_is_dimensionless_and_innovation_sensitive():
    candidates = [
        signal("expensive", 100000, 100),
        signal("quiet", 100, 4),
        signal("moving", 100, 4, 4),
    ]
    plan = plan_investigation([{"series": candidates}], 1)
    assert plan["selected"]["product_id"] == "moving"
    assert plan["selected"]["relative_uncertainty"] == pytest.approx(0.02)
    assert plan["selected"]["priority_score"] == pytest.approx(0.1)
    assert plan["search_cost"] == 1
    assert plan["next_search"]["query"].startswith("moving")
    # Listing order cannot change the decision.
    assert plan_investigation([{"series": list(reversed(candidates))}], 1) == plan
    scaled = deepcopy(candidates)
    for item in scaled:
        item["smoothed_baseline"] *= 100
        item["posterior_variance"] *= 10000
    assert plan_investigation([{"series": scaled}], 1)["selected"] == plan["selected"]


def test_cold_start_budget_and_duplicate_product_handling():
    gap = {
        "product_id": "gap",
        "currency": "INR",
        "title": "SSD",
        "n_observations": 1,
        "status": "insufficient_history",
    }
    assert plan_investigation([{"series": [gap]}], 1)["selected"]["priority_score"] is None
    no_budget = plan_investigation([{"series": [gap]}], 0)
    assert no_budget["next_search"] is None and no_budget["search_cost"] == 0
    assert no_budget["status"] == "partial"
    estimate = signal("gap", 100, 4)
    plan = plan_investigation([{"series": [gap, estimate, estimate]}], 1)
    assert len(plan["ranked_candidates"]) == 1
    assert plan["selected"]["coverage"] == "estimated"
    assert plan_investigation([], 10)["status"] == "empty"
    with pytest.raises(ValueError):
        plan_investigation([{"series": [signal("bad", 100, float("nan"))]}], 1)


def captured_evidence():
    raw = {
        "series": [
            {
                "product_id": "ssd",
                "currency": "INR",
                "title": "SSD 1TB",
                "points": [
                    {
                        "value": v,
                        "currency": "INR",
                        "observed_at": f"2026-10-0{i + 1}T10:00:00+00:00",
                    }
                    for i, v in enumerate([100, 101, 120, 110])
                ],
            }
        ]
    }
    filtered = {**run_prism_filter(raw), "input_result_id": "result_1"}
    plan = plan_investigation([filtered], 2)
    return build_evidence(
        {"result_1": raw, "filter_result_1": filtered},
        [
            {
                "inputs": [filtered],
                "searches_remaining": 2,
                "expected_sha256": fingerprint(plan),
                "policy": plan["policy"],
            }
        ],
    )


def test_offline_replay_verifies_filters_and_decisions_and_freezes_inputs():
    evidence = captured_evidence()
    assert replay_evidence(evidence)["status"] == "verified"
    assert replay_evidence(evidence)["network_calls"] == 0
    changed = deepcopy(evidence)
    changed["filters"][0]["input"]["series"][0]["points"][0]["value"] += 1
    assert replay_evidence(changed)["status"] == "integrity_mismatch"
    # A valid snapshot carrying old numerical expectations reports drift distinctly.
    changed["sha256"] = fingerprint({k: v for k, v in changed.items() if k != "sha256"})
    assert replay_evidence(changed)["status"] == "numerical_drift"


def test_browser_json_round_trip_keeps_numerically_equivalent_evidence_valid():
    evidence = captured_evidence()
    assert fingerprint({"price": 100.0, "x": -0.0}) == fingerprint({"price": 100, "x": 0})
    exported = json.loads(
        json.dumps(evidence),
        parse_float=lambda text: int(float(text)) if float(text).is_integer() else float(text),
    )
    assert replay_evidence(exported)["status"] == "verified"


def test_news_query_broadens_a_sku_to_sector_context_and_retains_identity():
    item = signal("retail_123", 8000, 100)
    item["title"] = "Samsung SSD PM991 PCIe NVMe 1TB MZ-VLQ1T00 000H1"
    plan = plan_investigation([{"series": [item]}], 1)
    assert plan["next_search"]["query"] == "SSD NAND flash prices India supply"
    assert plan["selected"]["product_id"] == "retail_123"
    assert plan["selected"]["title"] == item["title"]


def test_replay_preserves_legacy_query_policy_when_no_policy_field_was_saved():
    inputs = [{"series": [signal("ssd", 100, 4)]}]
    old = plan_investigation(inputs, 1, policy=LEGACY_POLICY)
    evidence = build_evidence(
        {}, [{"inputs": inputs, "searches_remaining": 1, "expected_sha256": fingerprint(old)}]
    )
    assert replay_evidence(evidence)["status"] == "verified"


def test_active_workflow_selects_one_news_query_and_replays_without_more_searches(tmp_path):
    store = SignalStore(tmp_path / "runtime.sqlite")
    item = shopping(shopping_payload(), {"q": "SSD"})[0]
    for day, value in enumerate([7950, 7990, 8050], 1):
        store.record([{**item, "value": value}], f"2026-09-{day:02d}T10:00:00+00:00")
    queries = []

    def provider(params):
        queries.append(params)
        if params["engine"] == "google_shopping":
            return shopping_payload()
        return {"news_results": [{"title": "SSD supply", "link": "https://example.com/news"}]}

    async def check():
        runtime = AgentRuntime(
            Settings(),
            store,
            model=EarlyFinishModel(),
            gateway_factory=lambda: SerpApiGateway("", search=provider),
        )
        events = [event async for event in runtime.events("Investigate SSD prices")]
        decision = next(e["decision"] for e in events if e["type"] == "investigation.planned")
        assert decision["selected"]["coverage"] == "estimated"
        assert len(queries) == 2
        assert queries[-1]["q"] == decision["next_search"]["query"]
        report = events[-1]["report"]
        assert report["status"] == "completed"
        assert replay_evidence(report["evidence"])["status"] == "verified"
        assert len(queries) == 2
        assert len(report["trace"]) > 0

    asyncio.run(check())


def test_search_budget_exhaustion_does_not_dispatch_another_query(tmp_path):
    queries = []

    def provider(params):
        queries.append(params)
        return shopping_payload()

    async def check():
        runtime = AgentRuntime(
            Settings(),
            SignalStore(tmp_path / "runtime.sqlite"),
            model=EarlyFinishModel(),
            gateway_factory=lambda: SerpApiGateway("", max_searches=1, search=provider),
        )
        events = [event async for event in runtime.events("Investigate SSD prices")]
        assert events[-1]["report"]["status"] == "partial"
        assert len(queries) == 1
        assert not any(e.get("tool") == "get_market_context" for e in events)

    asyncio.run(check())


def test_deterministic_tool_chain_requires_only_two_inference_rounds(tmp_path):
    async def check():
        model = CountedModel()
        runtime = AgentRuntime(
            Settings(),
            SignalStore(tmp_path / "runtime.sqlite"),
            model=model,
            gateway_factory=lambda: SerpApiGateway("", search=lambda _: shopping_payload()),
        )
        report = await runtime.chat("Investigate SSD prices")
        assert model.calls == 2
        assert report["tool_calls"] == 4
        assert replay_evidence(report["evidence"])["status"] == "verified"

    asyncio.run(check())


def test_model_context_projection_does_not_mutate_complete_evidence():
    data = {
        "items": [{"title": str(i)} for i in range(20)],
        "engines": [{}],
        "series": [
            {"product_id": "x", "points": [{"value": 1}]},
            {"product_id": "y", "trajectory": [{"raw": 1}]},
        ],
    }
    view = compact_tool_result(data)
    assert len(view["items"]) == 8 and view["total_items"] == 20
    assert "engines" not in view
    assert view["series"][0]["n_observations"] == 1
    assert "points" not in view["series"][0]
    assert "trajectory" not in view["series"][1]
    assert len(data["items"]) == 20 and data["series"][0]["points"]
