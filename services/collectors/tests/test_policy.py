"""Network-free compliance-policy regression tests."""

from __future__ import annotations

import asyncio

from collectors.policy import PolicyEngine
from protego import Protego


def test_exact_authenticated_serpapi_endpoint_is_licensed_not_crawled(monkeypatch):
    policy = PolicyEngine()

    async def robots_must_not_be_fetched(_host):
        raise AssertionError("licensed API endpoint must not fetch crawler directives")

    monkeypatch.setattr(policy, "_robots", robots_must_not_be_fetched)

    assert asyncio.run(policy.allowed("https://serpapi.com/search.json")) is True


def test_serpapi_allowlist_does_not_cover_other_paths(monkeypatch):
    policy = PolicyEngine()
    robots = Protego.parse("User-agent: *\nDisallow: /searches/\n")

    async def fixed_robots(_host):
        return robots

    monkeypatch.setattr(policy, "_robots", fixed_robots)

    assert asyncio.run(policy.allowed("https://serpapi.com/searches/private")) is False


def test_serpapi_allowlist_requires_https(monkeypatch):
    policy = PolicyEngine()
    robots = Protego.parse("User-agent: *\nDisallow: /\n")

    async def fixed_robots(_host):
        return robots

    monkeypatch.setattr(policy, "_robots", fixed_robots)

    assert asyncio.run(policy.allowed("http://serpapi.com/search.json")) is False
