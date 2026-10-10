"""Runner CLI: basket × advance windows × adapters → storage.

Usage:
  collect --adapter serpapi                  # full basket, all windows
  collect --adapter serpapi --routes DEL-BOM --windows 7 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .adapters import REGISTRY
from .models import IST
from .policy import PolicyEngine
from .storage import save_quotes

REPO_ROOT = Path(__file__).resolve().parents[4]
BASKET_PATH = REPO_ROOT / "data" / "route_basket.yaml"
ADVANCE_WINDOWS = [1, 7, 15, 30, 45]  # T+n days, per PS spec

# PRISM needs the SAME departure date observed on consecutive collection days
# (a flight climbing its fare ladder is only visible as a panel). With the
# sparse PS windows, dep-dates are disjoint day over day (T+7 today = Sep 10,
# T+7 tomorrow = Sep 11 → zero overlap). Dense near-term windows give every
# departure date inside the next week 7 daily observations. Applied per-adapter
# where a request is cheap (Akasa: one POST per date).
PANEL_WINDOWS: dict[str, list[int]] = {
    "akasa": [1, 2, 3, 4, 5, 6, 7, 15, 30, 45],
}


def load_basket() -> list[dict]:
    with open(BASKET_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)["routes"]


async def run(
    adapter_name: str, routes_filter: list[str], windows: list[int], dry_run: bool
) -> tuple[int, int, int]:
    policy = PolicyEngine()
    collector = REGISTRY[adapter_name](policy)
    basket = load_basket()
    if routes_filter:
        wanted = {tuple(r.split("-")) for r in routes_filter}
        basket = [r for r in basket if (r["origin"], r["dest"]) in wanted]

    total_saved = 0
    requests = 0
    failures = 0
    try:
        for route in basket:
            for t in windows:
                requests += 1
                dep = datetime.now(IST).date() + timedelta(days=t)
                try:
                    quotes = await collector.collect(route["origin"], route["dest"], dep)
                except Exception as e:  # noqa: BLE001 — one failure must not kill the day's run
                    failures += 1
                    print(f"[FAIL] {route['origin']}-{route['dest']} T+{t}: {e}", file=sys.stderr)
                    continue
                if not quotes:
                    continue
                if dry_run:
                    print(f"[DRY] {route['origin']}-{route['dest']} T+{t}: {len(quotes)} quotes")
                    for q in quotes[:3]:
                        print(f"      {q.carrier} {q.flight_no} ₹{q.total_fare:,.0f} lead={q.lead_days}d")
                else:
                    n = save_quotes(quotes)
                    total_saved += n
                    print(f"[OK]  {route['origin']}-{route['dest']} T+{t}: {len(quotes)} quotes, {n} new")
    finally:
        await collector.aclose()
    return total_saved, requests, failures


def main() -> None:
    # Windows consoles default to cp1252, which cannot encode '₹'.
    for stream in (sys.stdout, sys.stderr):
        with suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv(REPO_ROOT / ".env")
    p = argparse.ArgumentParser(description="Air-Sankhyiki fare collector")
    p.add_argument("--adapter", required=True, choices=sorted(REGISTRY))
    p.add_argument("--routes", nargs="*", default=[], help="e.g. DEL-BOM BLR-DEL (default: full basket)")
    p.add_argument(
        "--windows",
        nargs="*",
        type=int,
        default=None,
        help="advance windows; default = per-adapter PANEL_WINDOWS or the PS spec set",
    )
    p.add_argument("--dry-run", action="store_true", help="collect but don't persist")
    p.add_argument(
        "--from-file",
        help="ingest a manually captured response file instead of fetching live "
        "(adapters that support collect_from_file, e.g. akasa)",
    )
    args = p.parse_args()

    if args.from_file:
        collector = REGISTRY[args.adapter](PolicyEngine())
        quotes = collector.collect_from_file(args.from_file)
        by_market: dict[str, int] = {}
        for q in quotes:
            by_market[f"{q.origin}-{q.dest}"] = by_market.get(f"{q.origin}-{q.dest}", 0) + 1
        print(f"Parsed {len(quotes)} quotes: {by_market}")
        if args.dry_run:
            for q in quotes[:5]:
                print(
                    f"  {q.flight_no} {q.origin}-{q.dest} {q.departure_date} rbd={q.rbd} "
                    f"₹{q.total_fare:,.0f} (base ₹{q.base_fare or 0:,.0f}) seats={q.seats_available}"
                )
        else:
            print(f"{save_quotes(quotes)} new quotes persisted.")
        return

    windows = args.windows or PANEL_WINDOWS.get(args.adapter, ADVANCE_WINDOWS)
    saved, requests, failures = asyncio.run(
        run(args.adapter, args.routes, windows, args.dry_run)
    )
    result = "complete" if failures == 0 else "partial"
    print(
        f"Done ({result}). {saved} new quotes persisted; "
        f"{requests - failures}/{requests} requests succeeded, {failures} failed."
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
