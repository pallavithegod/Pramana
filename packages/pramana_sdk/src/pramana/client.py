"""Reusable, injectable multi-engine measurement client."""

import asyncio
import hashlib
import json
import re
from datetime import UTC, date, datetime
from typing import Literal
from uuid import uuid4

from . import normalize
from .errors import PramanaError
from .providers import SerpApiGateway
from .store import SignalStore


class PramanaClient:
    def __init__(self, gateway: SerpApiGateway, store: SignalStore):
        self.gateway = gateway
        self.store = store
        self.results: dict[str, dict] = {}
        self.decisions: list[dict] = []

    async def _query(self, params: dict, parser, domain: str) -> dict:
        data = await self.gateway.search(params)
        items = parser(data, params)[:20]
        timestamp = datetime.now(UTC).isoformat()
        if domain != "news":
            await asyncio.to_thread(self.store.record, items, timestamp)
        series = []
        for item in items:
            if item.get("value") is not None:
                points = await asyncio.to_thread(self.store.history, item["product_id"])
                series.append(
                    {
                        "product_id": item["product_id"],
                        "title": item["title"],
                        "currency": item["currency"],
                        "points": points,
                    }
                )
        rid = "result_" + uuid4().hex
        result = {
            "result_id": rid,
            "status": "ok" if items else "empty",
            "domain": domain,
            "engine": params["engine"],
            "observed_at": timestamp,
            "items": items,
            "series": series,
            "provider_search_id": data.get("search_metadata", {}).get("id"),
            "payload_sha256": hashlib.sha256(
                json.dumps(data, sort_keys=True, default=str).encode()
            ).hexdigest(),
            "next_page_token": data.get("serpapi_pagination", {}).get("next_page_token"),
            "warnings": ["A fresh comparable time series needs repeated captures"]
            if series and all(len(s["points"]) < 3 for s in series)
            else [],
        }
        self.results[rid] = result
        return result

    @staticmethod
    def _date(value: str) -> str:
        return date.fromisoformat(value).isoformat()

    @staticmethod
    def _query_text(value: str) -> str:
        if not value.strip() or len(value) > 300:
            raise ValueError("Query must contain 1–300 characters")
        return value.strip()

    async def get_flight_fares(self, origin: str, destination: str, departure_date: str) -> dict:
        origin, destination = origin.upper(), destination.upper()
        if not all(re.fullmatch(r"[A-Z]{3}", v) for v in [origin, destination]):
            raise ValueError("Use three-letter IATA airport codes")
        if origin == destination:
            raise ValueError("Origin and destination must differ")
        return await self._query(
            {
                "engine": "google_flights",
                "departure_id": origin,
                "arrival_id": destination,
                "outbound_date": self._date(departure_date),
                "type": 2,
                "travel_class": 1,
                "adults": 1,
                "stops": 1,
                "currency": "INR",
                "gl": "in",
                "hl": "en",
            },
            normalize.flights,
            "mobility",
        )

    async def get_hotel_rates(
        self, location: str, check_in: str, check_out: str, adults: int = 1
    ) -> dict:
        check_in, check_out = self._date(check_in), self._date(check_out)
        if check_out <= check_in or not 1 <= adults <= 6:
            raise ValueError("Checkout must follow check-in; adults must be 1–6")
        return await self._query(
            {
                "engine": "google_hotels",
                "q": self._query_text(location),
                "check_in_date": check_in,
                "check_out_date": check_out,
                "adults": adults,
                "currency": "INR",
                "gl": "in",
                "hl": "en",
            },
            normalize.hotels,
            "mobility",
        )

    async def get_retail_prices(
        self, query: str, source: Literal["shopping", "amazon", "both"] = "both"
    ) -> dict:
        query = self._query_text(query)
        if source not in {"shopping", "amazon", "both"}:
            raise ValueError("Source must be shopping, amazon or both")
        results = []
        # Sequential dispatch ensures partial results survive exhaustion of a two-engine budget.
        for engine in ["shopping", "amazon"] if source == "both" else [source]:
            try:
                if engine == "shopping":
                    result = await self._query(
                        {"engine": "google_shopping", "q": query, "gl": "in", "hl": "en"},
                        normalize.shopping,
                        "retail",
                    )
                else:
                    result = await self._query(
                        {"engine": "amazon", "k": query, "amazon_domain": "amazon.in"},
                        normalize.amazon,
                        "retail",
                    )
                results.append(result)
            except PramanaError as exc:
                if not results:
                    raise
                results.append(exc.as_dict())
        rid = "result_" + uuid4().hex
        combined = {
            "result_id": rid,
            "domain": "retail",
            "query": query,
            "status": "partial"
            if any(r["status"] == "error" for r in results)
            else ("ok" if any(r["items"] for r in results) else "empty"),
            "engines": results,
            "items": [i for r in results for i in r.get("items", [])],
            "series": [s for r in results for s in r.get("series", [])],
        }
        self.results[rid] = combined
        return combined

    async def get_labor_salaries(
        self, query: str, location: str, next_page_token: str | None = None
    ) -> dict:
        params = {
            "engine": "google_jobs",
            "q": self._query_text(query),
            "location": self._query_text(location),
            "gl": "in",
            "hl": "en",
        }
        if next_page_token:
            if len(next_page_token) > 2048:
                raise ValueError("Pagination token too long")
            params["next_page_token"] = next_page_token
        return await self._query(params, normalize.jobs, "labor")

    async def get_market_context(self, query: str) -> dict:
        return await self._query(
            {"engine": "google_news", "q": self._query_text(query), "gl": "in", "hl": "en"},
            normalize.news,
            "news",
        )
