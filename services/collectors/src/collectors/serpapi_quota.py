"""Credential-safe SerpAPI quota preflight for the nightly scheduler."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from .adapters.serpapi_gf import configured_api_keys

ACCOUNT_URL = "https://serpapi.com/account.json"
REPO_ROOT = Path(__file__).resolve().parents[4]


async def searches_left(keys: list[str]) -> tuple[int, int]:
    """Return (total searches left, accounts successfully checked)."""
    total = 0
    checked = 0
    async with httpx.AsyncClient(timeout=20) as client:
        for api_key in keys:
            try:
                response = await client.get(ACCOUNT_URL, params={"api_key": api_key})
            except httpx.RequestError:
                continue
            if response.status_code != 200:
                continue
            try:
                remaining = int(response.json().get("total_searches_left", 0))
            except (TypeError, ValueError):
                continue
            checked += 1
            total += max(remaining, 0)
    return total, checked


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    keys = configured_api_keys()
    if not keys:
        print("SerpAPI quota check failed: no credentials configured", file=sys.stderr)
        raise SystemExit(2)
    total, checked = asyncio.run(searches_left(keys))
    if checked == 0:
        print("SerpAPI quota check failed: no account endpoint was reachable", file=sys.stderr)
        raise SystemExit(3)
    print(total)


if __name__ == "__main__":
    main()
