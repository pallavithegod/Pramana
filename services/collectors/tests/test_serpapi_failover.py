"""Credential-safe, network-free tests for SerpAPI failover behavior."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx
import pytest
from collectors import serpapi_quota
from collectors.adapters import serpapi_gf
from collectors.adapters.serpapi_gf import SerpApiCollector, configured_api_keys


class _NoWaitBudget:
    async def wait(self):
        return None


class _AllowedPolicy:
    async def allowed(self, _url):
        return True

    def budget(self, _host):
        return _NoWaitBudget()


class _Response:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = "{}"

    def json(self):
        return self._payload


class _Client:
    def __init__(self, outcomes, calls):
        self._outcomes = outcomes
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, _url, params):
        self._calls.append(params["api_key"])
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _install_client(monkeypatch, outcomes, calls):
    monkeypatch.setattr(
        serpapi_gf.httpx,
        "AsyncClient",
        lambda **_kwargs: _Client(outcomes, calls),
    )


def _collector(monkeypatch, keys: str = "primary,fallback") -> SerpApiCollector:
    monkeypatch.setenv("SERPAPI_KEYS", keys)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    collector = SerpApiCollector(_AllowedPolicy())
    collector.archive = lambda _payload, _label: "data/raw/test.raw"
    return collector


def test_configured_keys_prefers_list_and_keeps_legacy_fallback():
    keys = configured_api_keys(
        {"SERPAPI_KEYS": " first, second,first ", "SERPAPI_KEY": "legacy"}
    )
    assert keys == ["first", "second", "legacy"]


def test_primary_key_success_does_not_rotate(monkeypatch):
    calls = []
    collector = _collector(monkeypatch)
    _install_client(monkeypatch, [_Response(200, {})], calls)

    quotes = asyncio.run(collector.collect("DEL", "BOM", date(2026, 9, 20)))

    assert quotes == []
    assert calls == ["primary"]


def test_429_rotates_once_to_authorized_fallback(monkeypatch):
    calls = []
    archived = []
    collector = _collector(monkeypatch)
    collector.archive = lambda payload, label: archived.append((payload, label)) or "ok.raw"
    _install_client(
        monkeypatch,
        [_Response(429, {"error": "rate limit"}), _Response(200, {})],
        calls,
    )

    asyncio.run(collector.collect("DEL", "BOM", date(2026, 9, 20)))

    assert calls == ["primary", "fallback"]
    assert len(archived) == 1
    assert collector._exhausted_keys == {"primary"}


def test_all_keys_exhausted_without_secret_in_error(monkeypatch):
    calls = []
    collector = _collector(monkeypatch, "secret-one,secret-two")
    _install_client(
        monkeypatch,
        [
            _Response(429, {"error": "quota exceeded"}),
            _Response(200, {"error": "Your account has run out of searches."}),
        ],
        calls,
    )

    with pytest.raises(RuntimeError) as caught:
        asyncio.run(collector.collect("DEL", "BOM", date(2026, 9, 20)))

    message = str(caught.value)
    assert "all 2 configured" in message
    assert "secret-one" not in message
    assert "secret-two" not in message


def test_missing_configuration_fails_before_request(monkeypatch):
    monkeypatch.delenv("SERPAPI_KEYS", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    collector = SerpApiCollector(_AllowedPolicy())

    with pytest.raises(RuntimeError, match="credentials missing"):
        asyncio.run(collector.collect("DEL", "BOM", date(2026, 9, 20)))


def test_transport_failure_redacts_key_and_does_not_rotate(monkeypatch):
    calls = []
    collector = _collector(monkeypatch, "never-print-this,fallback")
    request = httpx.Request(
        "GET", "https://serpapi.com/search.json?api_key=never-print-this"
    )
    _install_client(monkeypatch, [httpx.ConnectError("network down", request=request)], calls)

    with pytest.raises(RuntimeError) as caught:
        asyncio.run(collector.collect("DEL", "BOM", date(2026, 9, 20)))

    assert "never-print-this" not in str(caught.value)
    assert calls == ["never-print-this"]


def test_quota_preflight_sums_only_reachable_accounts(monkeypatch):
    calls = []
    outcomes = [
        _Response(200, {"total_searches_left": 60}),
        _Response(503, {}),
        _Response(200, {"total_searches_left": 45}),
    ]
    monkeypatch.setattr(
        serpapi_quota.httpx,
        "AsyncClient",
        lambda **_kwargs: _Client(outcomes, calls),
    )

    total, checked = asyncio.run(
        serpapi_quota.searches_left(["first", "unreachable", "third"])
    )

    assert total == 105
    assert checked == 2
    assert calls == ["first", "unreachable", "third"]
