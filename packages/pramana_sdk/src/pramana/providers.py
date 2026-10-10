"""Official SerpApi SDK transport, bounded search budget and safe errors."""

import asyncio
from collections.abc import Callable

import serpapi

from .errors import PramanaError


class SerpApiGateway:
    def __init__(
        self, api_key: str, max_searches: int = 8, search: Callable[[dict], dict] | None = None
    ):
        self.api_key = api_key
        self.max_searches = max_searches
        self.searches_used = 0
        self._lock = asyncio.Lock()
        self._search = search

    async def search(self, params: dict) -> dict:
        if not self.api_key and self._search is None:
            raise PramanaError("MISSING_SERPAPI_KEY", "Set SERPAPI_KEY on the local API server")
        async with self._lock:
            if self.searches_used >= self.max_searches:
                raise PramanaError("SEARCH_BUDGET_EXCEEDED", "This run reached its search budget")
            self.searches_used += 1
        try:
            search = self._search or serpapi.Client(api_key=self.api_key, timeout=35).search
            result = dict(await asyncio.to_thread(search, params))
        except Exception as exc:  # noqa: BLE001 -- sanitize third-party transport exceptions
            status = getattr(exc, "status_code", None)
            code = "PROVIDER_RATE_LIMIT" if status == 429 else "PROVIDER_UNAVAILABLE"
            raise PramanaError(code, "SerpApi request failed; retry later") from None
        if result.get("error"):
            raise PramanaError("PROVIDER_ERROR", "SerpApi returned an error for this query")
        return result
