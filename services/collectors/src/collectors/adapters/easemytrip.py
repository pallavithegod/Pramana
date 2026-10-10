"""EaseMyTrip adapter (Tier 1 OTA) — reprice-response parser, file-ingestion only for now.

Captured 31 Aug 2026: POST flightservice-node.easemytrip.com/AirAvail_Lights/AirReprice_L
returns the RICHEST component split of any source: per-passenger `lstTxDt` with
charge codes (RCS, TRF, YQ fuel surcharge, ASF, UDF, AAT, CGST/SGST...), BscFr
(base fare), TtlFrWthMkp (total), fareCls (RBD!), and it is MULTI-CARRIER —
EMT sells IndiGo/Air India/SpiceJet, giving a legal window into carriers whose
own sites are Akamai-walled.

LIVE FETCH DEFERRED: www.easemytrip.com robots.txt disallows the listing path
(/flight-search/listing*) and the reprice POST needs a session-bound payload.
Until the compliance question on the flightservice-node host is resolved and a
listing-free request flow is captured, this adapter is --from-file only:
  collect --adapter easemytrip --from-file <reprice-response.json>
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime

from ..base import BaseCollector
from ..models import Cabin, FareQuote, SourceTier

_DT_RE = re.compile(r"[A-Za-z]{3}-(\d{2})([A-Za-z]{3})(\d{4})")  # "Tue-01Sep2026"


def _parse_emt_date(s: str) -> date:
    m = _DT_RE.search(s)
    if not m:
        raise ValueError(f"unparseable EMT date: {s!r}")
    # calendar date only — tz is irrelevant, silence DTZ007 by parsing components
    return date(int(m.group(3)), datetime.strptime(m.group(2), "%b").month, int(m.group(1)))  # noqa: DTZ007


def parse_reprice_response(payload: str | dict, raw_ref: str | None = None) -> list[FareQuote]:
    data = payload if isinstance(payload, dict) else json.loads(payload)
    quotes: list[FareQuote] = []
    for jrny in data.get("jrneys", []):
        for seg in jrny.get("segs", []):
            fare = seg.get("Fare") or {}
            bonds = seg.get("bonds", [])
            if not bonds or not bonds[0].get("Legs"):
                continue
            legs = bonds[0]["Legs"]
            if len(legs) != 1 or str(legs[0].get("stops", "0")) not in ("0", ""):
                continue  # product spec: non-stop only
            leg = legs[0]
            carrier = leg["airCode"]
            flight_no = f"{carrier}{str(leg.get('fltNum', '')).strip()}" or None
            origin = str(leg["org"]).split("|")[0]
            dest = str(leg["dest"]).split("|")[0]

            adt = next(
                (p for p in fare.get("lstPxPF", []) if p.get("PaxType") == "Adult"), None
            )
            total = float((adt or {}).get("TtlFare") or seg.get("TotalFare") or 0)
            if total <= 0:
                continue
            base = float((adt or fare).get("BscFr") or 0) or None
            components: dict[str, float] = {}
            if base is not None:
                components["BaseFare"] = base
            for tx in (adt or {}).get("lstTxDt", []) or []:
                code = tx.get("ChgCd") or tx.get("ChgeTp") or "TAX"
                components[code] = components.get(code, 0.0) + float(tx.get("Amt", 0))
            # INTEGRITY RULE: base from BscFr only; warn if breakdown doesn't sum.
            warning = None
            if components:
                csum = round(sum(components.values()), 2)
                if abs(csum - total) > 1.0:  # EMT rounds; ₹1 tolerance
                    warning = f"component sum {csum} != total {total}"
            quotes.append(
                FareQuote(
                    carrier=carrier,
                    flight_no=flight_no,
                    origin=origin,
                    dest=dest,
                    departure_date=_parse_emt_date(leg["depDT"]),
                    cabin=Cabin.ECONOMY if leg.get("cabin", "Economy") == "Economy" else Cabin.BUSINESS,
                    nonstop=True,
                    fare_family=fare.get("fareName"),
                    rbd=leg.get("fareCls") or None,
                    total_fare=total,
                    base_fare=base,
                    taxes_fees=round(total - base, 2) if base is not None else None,
                    components=components or None,
                    integrity_warning=warning,
                    source="easemytrip",
                    source_tier=SourceTier.T1_DIRECT,
                    raw_ref=raw_ref,
                )
            )
    return quotes


class EaseMyTripCollector(BaseCollector):
    name = "easemytrip"
    tier = SourceTier.T1_DIRECT

    async def collect(self, origin: str, dest: str, departure_date: date) -> list[FareQuote]:
        raise RuntimeError(
            "easemytrip live fetch deferred (robots on listing path + session-bound "
            "reprice payload). Use: collect --adapter easemytrip --from-file <response.json>"
        )

    def collect_from_file(self, path: str) -> list[FareQuote]:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
        start = min(i for i in (text.find("{"), text.find("[")) if i >= 0)
        raw_ref = self.archive(text, "from_file")
        return parse_reprice_response(text[start:], raw_ref=raw_ref)
