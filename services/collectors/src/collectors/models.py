"""Canonical fare-quote model. The panel key is the backbone of PRISM — never weaken it."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from enum import Enum

from pydantic import BaseModel, Field, computed_field

# All business dates (departure, lead-time, collection day) are IST — Indian
# fares live on the IST calendar regardless of where the collector runs.
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


class Cabin(str, Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"


class SourceTier(str, Enum):
    T1_DIRECT = "tier1_direct"          # robots-compliant airline/OTA site
    T1_LICENSED = "tier1_licensed"      # SerpApi Google Flights
    T2_TARIFF = "tier2_tariff_sheet"    # DGCA-mandated tariff PDF
    T3_FIXTURE = "tier3_fixture"        # documented-not-run adapter (fixtures only)


class FareQuote(BaseModel):
    """One observed fare for one flight on one collection day.

    Panel identity (PRISM): (carrier, flight_no, departure_date) tracked across
    collected_date gives the booking-horizon panel. flight_no may be None for
    sources that only expose itineraries (SerpApi sometimes aggregates); such
    quotes still feed the headline index but not PRISM.
    """

    # --- panel key ---
    carrier: str = Field(description="IATA carrier code, e.g. QP, SG, 6E")
    flight_no: str | None = Field(default=None, description="e.g. QP1385; None if unavailable")
    origin: str = Field(description="IATA airport code")
    dest: str = Field(description="IATA airport code")
    departure_date: date
    collected_at: datetime = Field(default_factory=lambda: datetime.now(IST))

    # --- product spec (matches MoSPI CPI-2024 airfare item: cheapest economy, non-stop) ---
    cabin: Cabin = Cabin.ECONOMY
    nonstop: bool = True
    fare_family: str | None = None
    rbd: str | None = Field(default=None, description="booking class / classOfService — PRISM rung")

    # --- money (INR). SerpApi gives total only; direct adapters split components ---
    total_fare: float = Field(gt=0)
    base_fare: float | None = None
    taxes_fees: float | None = None
    components: dict[str, float] | None = Field(
        default=None,
        description="full charge breakdown by code, e.g. {'FarePrice': 5916, 'UDF': 578, 'TaxSum': 302}",
    )

    # --- PRISM / load signals ---
    seats_available: int | None = Field(
        default=None, description="availableCount in this fare bucket, when the source exposes it"
    )
    integrity_warning: str | None = Field(
        default=None,
        description="set when component sum ≠ total (e.g. airline introduced a new fee code)",
    )

    # --- provenance ---
    source: str = Field(description="adapter name, e.g. 'serpapi', 'akasa'")
    source_tier: SourceTier
    raw_ref: str | None = Field(
        default=None, description="path/hash of archived raw response (evidence trail)"
    )

    @computed_field
    @property
    def lead_days(self) -> int:
        """Days-to-departure at collection time (IST calendar) — the τ in BCWFI's f(τ)."""
        return (self.departure_date - self.collected_at.astimezone(IST).date()).days

    @computed_field
    @property
    def quote_fingerprint(self) -> str:
        """Dedup key: one quote per (panel key, product, collection day, source)."""
        parts = (
            f"{self.carrier}|{self.flight_no}|{self.origin}|{self.dest}"
            f"|{self.departure_date.isoformat()}|{self.cabin.value}|{self.fare_family}|{self.rbd}"
            f"|{self.collected_at.astimezone(IST).date().isoformat()}|{self.source}"
        )
        return hashlib.sha256(parts.encode()).hexdigest()[:24]
