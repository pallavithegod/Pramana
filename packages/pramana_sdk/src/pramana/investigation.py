"""Deterministic uncertainty-driven allocation of one contextual search."""

import hashlib
import json
import math
import re

LEGACY_POLICY = "relative-uncertainty-innovation-v1"
POLICY = "relative-uncertainty-innovation-v2"


def fingerprint(value: object) -> str:
    def canonical(item):
        # JavaScript JSON export emits 100 for 100.0; preserve numeric equivalence
        # across a browser round-trip instead of reporting spurious corruption.
        if isinstance(item, float) and item.is_integer():
            return int(item)
        if isinstance(item, dict):
            return {key: canonical(value) for key, value in item.items()}
        if isinstance(item, (list, tuple)):
            return [canonical(value) for value in item]
        return item

    return hashlib.sha256(
        json.dumps(
            canonical(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def context_query(selected: dict, policy: str) -> str:
    title = " ".join(str(selected["title"]).split())[:220]
    if policy == LEGACY_POLICY:
        return title + " India supply demand market prices"
    # Catalog/SKU titles overconstrain News; keep product identity in the record
    # and search its sector. Sector news is context, not product-specific proof.
    if selected["product_id"].startswith("flight_"):
        return "India airfare fuel prices demand"
    if selected["product_id"].startswith("hotel_"):
        return "India hotel room rates tourism demand"
    sectors = [
        (r"\b(ssd|nvme|nand)\b|solid.state", "SSD NAND flash"),
        (r"\b(laptop|notebook)\b", "laptop"),
        (r"\b(rice|milk|coffee|wheat|sugar)\b", None),
    ]
    for pattern, sector in sectors:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return (sector or match.group().lower()) + " prices India supply"
    return " ".join(title.split()[:5])[:120] + " India market prices"


def plan_investigation(
    filtered_results: list[dict], searches_remaining: int, policy: str = POLICY
) -> dict:
    """Rank conditional relative uncertainty, emphasizing unusually large innovations.

    This explicit heuristic is not expected information gain or a causal detector.
    News can contextualize a price move; it cannot reduce the price posterior variance.
    Missing-history cases are coverage gaps, not infinitely uncertain estimates.
    """
    if policy not in {POLICY, LEGACY_POLICY}:
        raise ValueError("Unsupported investigation policy")
    if (
        isinstance(searches_remaining, bool)
        or not isinstance(searches_remaining, int)
        or searches_remaining < 0
    ):
        raise ValueError("Searches remaining must be a nonnegative integer")
    candidates = {}
    for result in filtered_results:
        for series in result.get("series", []):
            pid, currency = series["product_id"], series["currency"]
            candidate = {
                "product_id": pid,
                "currency": currency,
                "title": series.get("title") or pid,
                "input_result_id": result.get("input_result_id"),
                "n_observations": series["n_observations"],
                "relative_uncertainty": None,
                "innovation_z": None,
                "priority_score": None,
                "coverage": "insufficient_history",
            }
            if series["status"] == "ok":
                baseline = float(series["smoothed_baseline"])
                variance = float(series["posterior_variance"])
                innovation = float(series["innovation_z"])
                if not all(math.isfinite(v) for v in [baseline, variance, innovation]):
                    raise ValueError("Planner inputs must be finite")
                if baseline <= 0 or variance < 0:
                    raise ValueError("Baseline must be positive and posterior variance nonnegative")
                relative = math.sqrt(variance) / baseline
                candidate.update(
                    coverage="estimated",
                    relative_uncertainty=relative,
                    innovation_z=innovation,
                    priority_score=relative * (1 + min(abs(innovation), 10)),
                )
            # A combined retail result may reference the same product as a child result.
            key = (pid, currency)
            old = candidates.get(key)
            if old is None or (candidate["n_observations"], str(candidate["input_result_id"])) > (
                old["n_observations"],
                str(old["input_result_id"]),
            ):
                candidates[key] = candidate
    ranked = sorted(
        candidates.values(),
        key=lambda c: (
            c["coverage"] != "estimated",
            -(c["priority_score"] or 0),
            c["product_id"],
            c["currency"],
        ),
    )
    selected = ranked[0] if ranked else None
    query = None
    if selected and searches_remaining:
        query = context_query(selected, policy)
    plan = {
        "status": "ok" if query else "partial" if selected else "empty",
        "policy": policy,
        "searches_remaining": searches_remaining,
        "search_cost": 1 if query else 0,
        "ranked_candidates": ranked,
        "selected": selected,
        "next_search": {"tool": "get_market_context", "query": query} if query else None,
        "reason": "Highest conditional relative uncertainty weighted by absolute innovation."
        if selected and selected["coverage"] == "estimated"
        else "No estimable histories; contextual search only, with an explicit coverage gap."
        if selected
        else "No comparable price signals are available.",
        "limitations": [
            "A transparent prioritization heuristic, not optimal information gain.",
            "News does not change price-filter uncertainty or establish causality.",
            "Further price captures need a meaningful observation interval.",
        ],
    }
    plan["decision_id"] = fingerprint(plan)
    return plan
