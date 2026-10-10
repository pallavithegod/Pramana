"""SerpApi Google Flights adapter (Tier 1, licensed).

Verified 31 Aug 2026: returns INR totals for Indian carriers incl. LCCs, but NO
base/tax split — quotes land with base_fare/taxes_fees = None by design.
Flight numbers ARE present per leg, so these quotes feed PRISM panels.

Budget: 250 free searches/month. One search = one (route, date). The runner's
basket sizing must respect this — see data/route_basket.yaml collection notes.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import date

import httpx

from ..base import BaseCollector
from ..models import Cabin, FareQuote, SourceTier

SERPAPI_URL = "https://serpapi.com/search.json"


def configured_api_keys(environ: Mapping[str, str] | None = None) -> list[str]:
    """Return unique authorized keys without logging their values."""
    env = os.environ if environ is None else environ
    candidates = [part.strip() for part in env.get("SERPAPI_KEYS", "").split(",")]
    candidates.append(env.get("SERPAPI_KEY", "").strip())
    return list(dict.fromkeys(key for key in candidates if key))


def _quota_exhausted(status_code: int, payload: dict) -> bool:
    if status_code == 429:
        return True
    message = str(payload.get("error", "")).lower()
    return bool(message) and any(
        marker in message
        for marker in (
            "run out of searches",
            "quota exhausted",
            "quota exceeded",
            "search limit",
            "rate limit",
        )
    )


class SerpApiCollector(BaseCollector):
    name = "serpapi"
    tier = SourceTier.T1_LICENSED

    def __init__(self, policy) -> None:
        super().__init__(policy)
        self._keys = configured_api_keys()
        self._exhausted_keys: set[str] = set()

    async def collect(self, origin: str, dest: str, departure_date: date) -> list[FareQuote]:
        if not self._keys:
            raise RuntimeError("SerpAPI credentials missing; set SERPAPI_KEYS or SERPAPI_KEY")
        if not await self.policy.allowed(SERPAPI_URL):
            raise PermissionError("policy engine denied serpapi.com")

        base_params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": dest,
            "outbound_date": departure_date.isoformat(),
            "type": "2",  # one-way
            "currency": "INR",
            "gl": "in",
            "hl": "en",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            for api_key in self._keys:
                if api_key in self._exhausted_keys:
                    continue
                await self.policy.budget("serpapi.com").wait()
                try:
                    response = await client.get(
                        SERPAPI_URL, params={**base_params, "api_key": api_key}
                    )
                except httpx.RequestError:
                    # httpx errors may embed the request URL and its api_key.
                    raise RuntimeError(
                        "SerpAPI transport request failed; credentials redacted"
                    ) from None

                try:
                    data = response.json()
                except ValueError:
                    data = {}
                if _quota_exhausted(response.status_code, data):
                    self._exhausted_keys.add(api_key)
                    continue
                if response.status_code != 200:
                    raise RuntimeError(f"SerpAPI request failed with HTTP {response.status_code}")
                if data.get("error"):
                    raise RuntimeError("SerpAPI returned a non-quota provider error")

                raw_ref = self.archive(
                    response.text, f"{origin}-{dest}_{departure_date.isoformat()}"
                )
                return self._parse(data, origin, dest, departure_date, raw_ref)

        raise RuntimeError(
            f"SerpAPI quota exhausted for all {len(self._keys)} configured credential(s)"
        )

    def _parse(
        self, data: dict, origin: str, dest: str, departure_date: date, raw_ref: str
    ) -> list[FareQuote]:
        quotes: list[FareQuote] = []
        for group in ("best_flights", "other_flights"):
            for itin in data.get(group, []):
                legs = itin.get("flights", [])
                price = itin.get("price")
                if price is None:
                    continue  # sold out / price-unavailable itineraries
                nonstop = len(legs) == 1
                if not nonstop:
                    continue  # product spec: cheapest non-stop economy (CPI-2024 compatible)
                leg = legs[0]
                flight_no = (leg.get("flight_number") or "").replace(" ", "") or None
                carrier = flight_no[:2] if flight_no else "??"
                quotes.append(
                    FareQuote(
                        carrier=carrier,
                        flight_no=flight_no,
                        origin=origin,
                        dest=dest,
                        departure_date=departure_date,
                        cabin=Cabin.ECONOMY,
                        nonstop=True,
                        total_fare=float(price),
                        source=self.name,
                        source_tier=self.tier,
                        raw_ref=raw_ref,
                    )
                )
        return quotes


if __name__ == "__main__":  # manual smoke test: python -m collectors.adapters.serpapi_gf
    import asyncio
    from datetime import datetime, timedelta

    from ..models import IST
    from ..policy import PolicyEngine

    async def _smoke() -> None:
        c = SerpApiCollector(PolicyEngine())
        qs = await c.collect("DEL", "BOM", datetime.now(IST).date() + timedelta(days=7))
        print(json.dumps([json.loads(q.model_dump_json()) for q in qs[:5]], indent=2))
        print(f"... {len(qs)} nonstop quotes total")

    asyncio.run(_smoke())
