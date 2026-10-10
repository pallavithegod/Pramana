"""Akasa Air adapter (Tier 1 direct) — Playwright-driven, two Navitaire schemas.

WHY PLAYWRIGHT (decision 31 Aug 2026): the `authorization` header on
prod-bl.qp.akasaair.com is an opaque encrypted blob minted by the site's own JS
(POST /api/ibe/token/generateToken fires on page load). Reverse-engineering it
would break silently on every rotation — fatal for a never-miss-a-day pipeline.
Instead we load akasaair.com once per run, capture the token the app mints for
itself, and reuse it via the same browser context. No UI automation, no forged
auth, ONS-style "behave like a visitor" compliance (robots.txt: no disallows).

Two response schemas, both parsed here:
1. RICH (LIVE since 2 Sep 2026): POST /api/ibe/availability/search with a JSON
   criteria body → journeysAvailableByMarket/faresAvailable — per-flight,
   per-RBD with seat counts and full component split (PRISM panel + rungs).
   Endpoint + payload captured 2 Sep by driving a real search on the site;
   replay verified with a homepage-minted token (HTTP 200, parses clean).
2. CALENDAR (LEGACY — endpoint died 1 Sep 2026): GET /api/ibe/availability/v2/
   search returns {"data":[]} for every query, including the site's own homepage
   widget calls (verified 2 Sep). Parser kept for the archived 31 Aug–1 Sep
   captures; the POST lowFare replacement also served empty on capture day.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime

from playwright.async_api import Error as PlaywrightError

from ..base import BaseCollector
from ..models import Cabin, FareQuote, SourceTier

HOME_URL = "https://www.akasaair.com/"
SEARCH_API = "https://prod-bl.qp.akasaair.com/api/ibe/availability/search"

# The API occasionally has a short-lived DNS/network failure during the
# roughly 200-request nightly sweep. Keep retries bounded so a sustained
# upstream outage cannot stall every request for minutes.
TRANSIENT_RETRY_DELAYS = (2, 5, 10)
TRANSIENT_ERROR_MARKERS = (
    "enotfound",
    "eai_again",
    "econnreset",
    "econnrefused",
    "etimedout",
    "socket hang up",
    "connection closed",
    "connection reset",
    "network changed",
)

ADT = "ADT"

# Akasa's network uses different airports than the basket's primary IATA for
# some cities: Goa = Mopa (GOX), not Dabolim (GOI). An unknown station in the
# search body returns HTTP 400 (seen 8 Sep 2026 when GOI-DEL/GOI-BOM joined the
# basket). We alias the REQUEST only; parsed quotes keep the actual station
# codes the airline returns.
STATION_ALIAS = {"GOI": "GOX"}


def build_search_body(origin: str, dest: str, departure_date: date) -> dict:
    """Criteria body as the site sends it (captured 2 Sep 2026). MACs on: DEL
    also returns Noida (DXN), BOM also Navi Mumbai (NMI) — extra real quotes;
    each FareQuote carries its actual origin/dest so the basket join stays clean."""
    return {
        "criteria": [
            {
                "stations": {
                    "originStationCodes": [STATION_ALIAS.get(origin, origin)],
                    "destinationStationCodes": [STATION_ALIAS.get(dest, dest)],
                    "searchDestinationMacs": True,
                    "searchOriginMacs": True,
                },
                "dates": {"beginDate": f"{departure_date.isoformat()}T00:00:00"},
                "filters": {
                    "compressionType": 1,
                    "maxConnections": 8,
                    "productClasses": ["NB", "LB", "EC", "AV"],
                    "fareTypes": ["NB", "LB", "R", "V"],
                },
            }
        ],
        "passengers": {"types": [{"type": ADT, "count": 1}], "residentCountry": ""},
        "codes": {"currencyCode": "INR", "promotionCode": ""},
        "offerCode": None,
        "numberOfFaresPerJourney": 10,
        "taxesAndFees": 1,
    }


# --------------------------------------------------------------------------- #
# parsers (pure, fixture-testable)
# --------------------------------------------------------------------------- #

def _adt_fare(fare_entry: dict) -> dict | None:
    for pf in fare_entry.get("passengerFares", []):
        if pf.get("passengerType") == ADT:
            return pf
    return None


def parse_search_response(payload: str | dict, raw_ref: str | None = None) -> list[FareQuote]:
    """Auto-detects schema: RICH journey payload or CALENDAR list payload."""
    data = payload if isinstance(payload, dict) else json.loads(payload)
    body = data.get("data", data)
    if isinstance(body, list):
        raise TypeError(
            "calendar-schema payload: use parse_calendar_response(payload, origin, dest)"
        )
    return _parse_rich(body, raw_ref)


def parse_calendar_response(
    payload: str | dict, origin: str, dest: str, raw_ref: str | None = None
) -> list[FareQuote]:
    """CALENDAR schema → one route-level min-fare quote per departure date.
    flight_no/rbd stay None (no flight resolution); when the variant carries
    taxesAndFees, base = price − taxesAndFees (the only decomposition this
    granularity permits; full component split comes from the RICH schema)."""
    data = payload if isinstance(payload, dict) else json.loads(payload)
    body = data.get("data", data)
    entries = body.get("lowFares", body) if isinstance(body, dict) else body
    quotes: list[FareQuote] = []
    for e in entries:
        if e.get("noFlights") or e.get("soldOut") or not e.get("price"):
            continue
        taxes = e.get("taxesAndFees")
        total = float(e["price"])
        quotes.append(
            FareQuote(
                carrier="QP",
                flight_no=None,
                origin=origin,
                dest=dest,
                departure_date=datetime.fromisoformat(e["date"]).date(),
                cabin=Cabin.ECONOMY,
                nonstop=True,  # route-min fare; Akasa metros are nonstop-served
                fare_family="CAL_MIN",
                total_fare=total,
                base_fare=round(total - float(taxes), 2) if taxes is not None else None,
                taxes_fees=float(taxes) if taxes is not None else None,
                components=(
                    {"FareLessTaxes": round(total - float(taxes), 2), "TaxesAndFees": float(taxes)}
                    if taxes is not None
                    else None
                ),
                seats_available=e.get("available"),
                source="akasa",
                source_tier=SourceTier.T1_DIRECT,
                raw_ref=raw_ref,
            )
        )
    return quotes


def _parse_rich(body: dict, raw_ref: str | None) -> list[FareQuote]:
    fare_map: dict[str, dict] = {
        item["key"]: item["value"] for item in body.get("faresAvailable", [])
    }
    quotes: list[FareQuote] = []
    for result in body.get("results", []):
        for trip in result.get("trips", []):
            for market in trip.get("journeysAvailableByMarket", []):
                for journey in market.get("value", []):
                    if journey.get("stops", 0) != 0:
                        continue  # product spec: non-stop only
                    seg = journey["segments"][0]
                    ident = seg["identifier"]
                    carrier = ident["carrierCode"]
                    flight_no = f"{carrier}{ident['identifier']}"
                    desig = journey["designator"]
                    dep_date = datetime.fromisoformat(desig["departure"]).date()

                    for jfare in journey.get("fares", []):
                        entry = fare_map.get(jfare.get("fareAvailabilityKey"))
                        if not entry:
                            continue
                        seats = None
                        details = jfare.get("details") or []
                        if details and details[0].get("availableCount") is not None:
                            seats = int(details[0]["availableCount"])

                        for fare in entry.get("fares", []):
                            pf = _adt_fare(fare)
                            if pf is None:
                                continue
                            total = float(pf["fareAmount"])
                            components: dict[str, float] = {}
                            base = None
                            for ch in pf.get("serviceCharges", []):
                                code = ch.get("code") or ch.get("detail") or ch.get("type")
                                components[code] = components.get(code, 0.0) + float(ch["amount"])
                                if ch.get("type") == "FarePrice":
                                    base = (base or 0.0) + float(ch["amount"])
                            # INTEGRITY RULE: base comes ONLY from the FarePrice
                            # component — never "total minus known fees" — so a new
                            # fee code can't corrupt base; it just flags a warning.
                            warning = None
                            csum = round(sum(components.values()), 2)
                            if abs(csum - total) > 0.01:
                                warning = f"component sum {csum} != fareAmount {total}"
                            quotes.append(
                                FareQuote(
                                    carrier=carrier,
                                    flight_no=flight_no,
                                    origin=desig["origin"],
                                    dest=desig["destination"],
                                    departure_date=dep_date,
                                    cabin=Cabin.ECONOMY,
                                    nonstop=True,
                                    fare_family=fare.get("productClass"),
                                    rbd=fare.get("classOfService"),
                                    total_fare=total,
                                    base_fare=base,
                                    taxes_fees=round(total - base, 2) if base is not None else None,
                                    components=components,
                                    seats_available=seats,
                                    integrity_warning=warning,
                                    source="akasa",
                                    source_tier=SourceTier.T1_DIRECT,
                                    raw_ref=raw_ref,
                                )
                            )
    return quotes


# --------------------------------------------------------------------------- #
# live collector
# --------------------------------------------------------------------------- #

class AkasaCollector(BaseCollector):
    name = "akasa"
    tier = SourceTier.T1_DIRECT

    def __init__(self, policy) -> None:
        super().__init__(policy)
        self._pw = None
        self._browser = None
        self._context = None
        self._token: str | None = None

    async def _session(self):
        """One browser + one site-minted token per run."""
        if self._token:
            return
        if not await self.policy.allowed(HOME_URL):
            raise PermissionError("policy engine denied akasaair.com")
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            viewport={"width": 1366, "height": 900}
        )
        await self._mint_token()

    async def _mint_token(self) -> None:
        """Load the homepage on the existing browser and capture the token the
        site mints for itself. Called at session start AND on 401 mid-run: the
        token's lifetime (~45 min) is shorter than a 20-route sweep (seen 10
        Sep 2026 — the last route's windows 401'd)."""
        self._token = None
        page = await self._context.new_page()
        token_found = asyncio.Event()

        def grab(req):
            if "prod-bl.qp.akasaair.com" in req.url and not self._token:
                auth = req.headers.get("authorization")
                if auth:
                    self._token = auth
                    token_found.set()

        page.on("request", grab)
        await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
        try:
            await asyncio.wait_for(token_found.wait(), timeout=20)
        except TimeoutError as e:
            raise RuntimeError("akasa: no authorization header observed on page load") from e
        await page.close()

    async def _search(self, origin: str, dest: str, departure_date: date):
        return await self._context.request.post(
            SEARCH_API,
            data=json.dumps(build_search_body(origin, dest, departure_date)),
            headers={
                "authorization": self._token,
                "content-type": "application/json",
                "accept": "application/json, text/plain, */*",
                "origin": "https://www.akasaair.com",
                "referer": "https://www.akasaair.com/",
            },
        )

    def _safe_request_error(self, error: Exception) -> str:
        """Keep Playwright's diagnostics but remove the authorization token."""
        message = str(error)
        if self._token:
            message = message.replace(self._token, "[REDACTED]")
        return message

    async def _search_with_retry(self, origin: str, dest: str, departure_date: date):
        """Retry transient network failures and refresh one expired token."""
        token_refreshed = False
        attempts = len(TRANSIENT_RETRY_DELAYS) + 1
        for attempt in range(attempts):
            await self.policy.budget("prod-bl.qp.akasaair.com").wait()
            try:
                resp = await self._search(origin, dest, departure_date)
            except PlaywrightError as error:
                safe_error = self._safe_request_error(error)
                transient = any(
                    marker in safe_error.lower() for marker in TRANSIENT_ERROR_MARKERS
                )
                if transient and attempt < attempts - 1:
                    await asyncio.sleep(TRANSIENT_RETRY_DELAYS[attempt])
                    continue
                if transient:
                    raise RuntimeError(
                        f"akasa transport error after {attempts} attempts "
                        f"for {origin}-{dest} {departure_date}: upstream DNS/network failure"
                    ) from None
                raise RuntimeError(f"akasa request failed: {safe_error}") from None

            if resp.status == 401 and not token_refreshed:
                await self._mint_token()
                token_refreshed = True
                continue
            if resp.status in {429, 502, 503, 504} and attempt < attempts - 1:
                await asyncio.sleep(TRANSIENT_RETRY_DELAYS[attempt])
                continue
            return resp

        raise RuntimeError("akasa request retry loop ended unexpectedly")

    async def collect(self, origin: str, dest: str, departure_date: date) -> list[FareQuote]:
        await self._session()
        resp = await self._search_with_retry(origin, dest, departure_date)
        if resp.status != 200:
            raise RuntimeError(f"akasa rich search HTTP {resp.status}")
        text = await resp.text()
        raw_ref = self.archive(text, f"rich_{origin}-{dest}_{departure_date.isoformat()}")
        return parse_search_response(text, raw_ref=raw_ref)

    def collect_from_file(self, path: str) -> list[FareQuote]:
        """Ingest a manually captured response (rich or calendar schema)."""
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
        start = min(i for i in (text.find("{"), text.find("[")) if i >= 0)
        raw_ref = self.archive(text, "from_file")
        try:
            return parse_search_response(text[start:], raw_ref=raw_ref)
        except TypeError:
            raise TypeError(
                "calendar-schema file: pass origin/dest via "
                "parse_calendar_response — or name the file cal_<ORG>-<DST>*.json"
            ) from None

    async def aclose(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._token = None
