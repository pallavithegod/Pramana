"""SpiceJet adapter (Tier 1 direct) — Navitaire dotREZ lowfare parser, file-only.

Schema (captured 31 Aug 2026): `POST /api/v2/search/lowfare` with JSON body
{pax, codes:{currency}, origin, destination, centerDate} returns a ~7-day strip
of route-min fares around centerDate. `includeTaxesAndFees=true` ⇒ each
lowestFareAmount.fareAmount is ALL-IN and taxesAndFeesAmount carries the split.

LIVE FETCH DEFERRED — OPERATOR ANTI-AUTOMATION SIGNAL (verified 1 Sep 2026):
the SPA mints its dotREZ JWT via `POST /api/v1/token`, and that endpoint returns
403 Forbidden to every automated browser we drove — headless Chromium, Patchright
stealth, and a persistent real-Chrome profile warmed over three reloads (page
renders, token still 403). The jar carries `__cf_bm` and no `_abck`: this is
Cloudflare Bot Management, i.e. the operator is explicitly refusing automated
clients on the credential path. Defeating that fingerprint check is evasion of a
stated access control, so we do not attempt it — the same standard by which we
honour robots.txt. In the active MVP, SG offered fares are observed through the
licensed SerpAPI panel. File-only parser fixtures remain test inputs; DGCA
tariff publications are only a prospective external-validation reference.

Ingestion path:
  collect --adapter spicejet --from-file <lowfare-response.json>
"""

from __future__ import annotations

import json
from datetime import date, datetime

from ..base import BaseCollector
from ..models import Cabin, FareQuote, SourceTier

HOME_URL = "https://www.spicejet.com/"
LOWFARE_URL = "https://www.spicejet.com/api/v2/search/lowfare"


def parse_lowfare_response(
    payload: str | dict, raw_ref: str | None = None
) -> list[FareQuote]:
    data = payload if isinstance(payload, dict) else json.loads(payload)
    body = data.get("data", data)
    inclusive = bool(body.get("includeTaxesAndFees", True))
    quotes: list[FareQuote] = []
    for m in body.get("lowFareDateMarkets", []):
        lfa = m.get("lowestFareAmount")
        if not lfa or lfa.get("fareAmount") is None:
            continue
        fare = float(lfa["fareAmount"])
        taxes = float(lfa.get("taxesAndFeesAmount") or 0.0)
        total = fare if inclusive else fare + taxes
        base = round(total - taxes, 2) if taxes else None
        quotes.append(
            FareQuote(
                carrier="SG",
                flight_no=None,
                origin=m["origin"],
                dest=m["destination"],
                departure_date=datetime.fromisoformat(m["departureDate"]).date(),
                cabin=Cabin.ECONOMY,
                nonstop=True,  # route-min strip; SG metro trunks are nonstop-served
                fare_family="CAL_MIN",
                total_fare=total,
                base_fare=base,
                taxes_fees=taxes or None,
                components=(
                    {"FareLessTaxes": base, "TaxesAndFees": taxes} if base is not None else None
                ),
                source="spicejet",
                source_tier=SourceTier.T1_DIRECT,
                raw_ref=raw_ref,
            )
        )
    return quotes


class SpiceJetCollector(BaseCollector):
    name = "spicejet"
    tier = SourceTier.T1_DIRECT

    async def collect(self, origin: str, dest: str, departure_date: date) -> list[FareQuote]:
        raise RuntimeError(
            "spicejet live fetch deferred: POST /api/v1/token returns 403 to automated "
            "browsers (Cloudflare Bot Management — an explicit operator refusal we honour). "
            "Use: collect --adapter spicejet --from-file <lowfare-response.json>; SG fares "
            "are otherwise covered by serpapi, the easemytrip capture, and DGCA tariff sheets."
        )

    def collect_from_file(self, path: str) -> list[FareQuote]:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
        start = min(i for i in (text.find("{"), text.find("[")) if i >= 0)
        raw_ref = self.archive(text, "from_file")
        return parse_lowfare_response(text[start:], raw_ref=raw_ref)
