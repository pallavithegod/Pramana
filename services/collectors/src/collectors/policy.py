"""Compliance policy engine — an adapter runs ONLY if this module clears it.

Rules (see docs/compliance-matrix): honor robots.txt, honest User-Agent,
per-host rate limits, off-peak collection. Verdicts for the big portals were
manually verified in browsers on 31 Aug 2026 and are pinned here so a transient
robots.txt fetch failure can never silently unlock a disallowed target.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

import httpx
from protego import Protego

DEFAULT_UA = os.environ.get(
    "COLLECTOR_USER_AGENT",
    "AirSankhyiki-Research-Bot/0.1 (SIH26056 academic project)",
)

# Exact authenticated vendor API endpoints are not crawler targets. They are
# allowlisted separately from website robots verdicts so this exception cannot
# weaken the policy applied to airline/OTA pages or other paths on the host.
LICENSED_API_ENDPOINTS: frozenset[tuple[str, str]] = frozenset(
    {
        ("serpapi.com", "/search.json"),
    }
)

# Manually verified verdicts (31 Aug 2026). True = fare-search path robots-clean.
PINNED_VERDICTS: dict[str, bool] = {
    "www.akasaair.com": True,        # robots.txt has no Disallow at all
    "www.spicejet.com": True,        # only /api/v1 disallowed; search pages clean
    # easemytrip.com intentionally NOT pinned: only /flight-search/listing* is
    # disallowed — the per-URL robots check below governs path by path.
    "www.yatra.com": True,           # domestic funnel robots-clean (affiliate dirs blocked)
    "www.airindia.com": True,        # funnel robots-clean (/bin/, loyalty blocked)
    "www.makemytrip.com": False,     # Disallow: /flight/search*, /air/*
    "www.goibibo.com": False,        # Disallow: /flights/*?*
    "www.goindigo.in": False,        # Disallow: /search.html, /book*
}


@dataclass
class HostBudget:
    min_interval_s: float = 8.0     # >= 5-10s/host per ONS/StatCan statistical-agency model
    _last_hit: float = 0.0

    async def wait(self) -> None:
        delta = time.monotonic() - self._last_hit
        if delta < self.min_interval_s:
            await asyncio.sleep(self.min_interval_s - delta)
        self._last_hit = time.monotonic()


class PolicyEngine:
    def __init__(self) -> None:
        self._budgets: dict[str, HostBudget] = {}
        self._robots_cache: dict[str, Protego] = {}

    def budget(self, host: str) -> HostBudget:
        return self._budgets.setdefault(host, HostBudget())

    async def allowed(self, url: str, ua: str = DEFAULT_UA) -> bool:
        parsed = httpx.URL(url)
        host = parsed.host
        if parsed.scheme == "https" and (host, parsed.path) in LICENSED_API_ENDPOINTS:
            return True
        if host in PINNED_VERDICTS and not PINNED_VERDICTS[host]:
            return False
        robots = await self._robots(host)
        if robots is None:
            # No robots.txt reachable: fall back to pinned verdict, default deny
            return PINNED_VERDICTS.get(host, False)
        return robots.can_fetch(url, ua)

    async def _robots(self, host: str) -> Protego | None:
        if host in self._robots_cache:
            return self._robots_cache[host]
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"https://{host}/robots.txt", headers={"User-Agent": DEFAULT_UA})
            if r.status_code == 200:
                self._robots_cache[host] = Protego.parse(r.text)
                return self._robots_cache[host]
        except httpx.HTTPError:
            pass
        return None
