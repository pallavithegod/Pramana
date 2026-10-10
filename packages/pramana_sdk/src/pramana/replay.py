"""Recompute captured numerical evidence without a search API or language model."""

from copy import deepcopy
from importlib.metadata import version

from .filter import run_prism_filter
from .investigation import LEGACY_POLICY, fingerprint, plan_investigation

SCHEMA = "pramana-evidence-v1"


def build_evidence(results: dict[str, dict], decisions: list[dict]) -> dict:
    filters = []
    for output in results.values():
        rid = output.get("input_result_id")
        if output.get("method") != "pramana-kalman-local-level-v1" or rid not in results:
            continue
        expected = {k: v for k, v in output.items() if k != "input_result_id"}
        filters.append(
            {
                "input_result_id": rid,
                "input": deepcopy({"series": results[rid]["series"]}),
                "expected_sha256": fingerprint(expected),
            }
        )
    evidence = {
        "schema": SCHEMA,
        "filters": filters,
        "decisions": deepcopy(decisions),
        "versions": {name: version(name) for name in ["pramana-sdk", "apix-index", "numpy"]},
    }
    evidence["sha256"] = fingerprint(evidence)
    return evidence


def replay_evidence(evidence: dict) -> dict:
    """Verify snapshot content and compare deterministic filter/planner output hashes.

    This does not replay Ollama wording, establish authenticity, or revalidate sources.
    A content hash detects edits relative to its stored value, not malicious re-signing.
    """
    if evidence.get("schema") != SCHEMA:
        raise ValueError("Unsupported or missing evidence schema")
    body = {k: v for k, v in evidence.items() if k != "sha256"}
    if fingerprint(body) != evidence.get("sha256"):
        return {
            "status": "integrity_mismatch",
            "integrity_matches": False,
            "filters": [],
            "decisions": [],
            "network_calls": 0,
        }
    filters, decisions = [], []
    for entry in evidence["filters"]:
        replayed = run_prism_filter(entry["input"])
        actual = fingerprint(replayed)
        filters.append(
            {
                "input_result_id": entry["input_result_id"],
                "matches": actual == entry["expected_sha256"],
                "actual_sha256": actual,
                "expected_sha256": entry["expected_sha256"],
                "result": replayed,
            }
        )
    for entry in evidence["decisions"]:
        replayed = plan_investigation(
            entry["inputs"], entry["searches_remaining"], policy=entry.get("policy", LEGACY_POLICY)
        )
        actual = fingerprint(replayed)
        decisions.append(
            {
                "decision_id": replayed["decision_id"],
                "matches": actual == entry["expected_sha256"],
                "result": replayed,
            }
        )
    matches = all(entry["matches"] for entry in filters + decisions)
    return {
        "status": "verified" if matches else "numerical_drift",
        "integrity_matches": True,
        "filters": filters,
        "decisions": decisions,
        "network_calls": 0,
        "captured_versions": evidence["versions"],
        "current_versions": {name: version(name) for name in evidence["versions"]},
        "scope": "Captured price filters and investigation decisions; model prose is not replayed.",
    }
