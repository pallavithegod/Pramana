"""Contract tests for the Akasa/Navitaire parser against a REAL captured response
(DEL/DXN → BOM search, 31 Aug 2026). If Akasa changes their payload shape,
these tests are the tripwire."""

import asyncio
from datetime import date as dt_date
from pathlib import Path
from types import SimpleNamespace

import pytest
from collectors.adapters.akasa import parse_search_response
from collectors.models import SourceTier

FIXTURE = Path(__file__).parent / "fixtures" / "akasa" / "search_sample.json"


@pytest.fixture(scope="module")
def quotes():
    return parse_search_response(FIXTURE.read_text(encoding="utf-8", errors="replace"))


def test_parses_both_markets(quotes):
    markets = {(q.origin, q.dest) for q in quotes}
    assert ("DXN", "BOM") in markets
    assert ("DEL", "BOM") in markets


def test_panel_key_complete(quotes):
    assert all(q.carrier == "QP" for q in quotes)
    assert all(q.flight_no and q.flight_no.startswith("QP") for q in quotes)
    assert all(q.nonstop for q in quotes)


def test_component_split_is_integrity_safe(quotes):
    """base = FarePrice charge, taxes = total - base; components must sum to total."""
    with_base = [q for q in quotes if q.base_fare is not None]
    assert with_base, "no quotes carried a FarePrice component"
    for q in with_base:
        assert q.taxes_fees == pytest.approx(q.total_fare - q.base_fare, abs=0.01)
        if q.integrity_warning is None:
            assert sum(q.components.values()) == pytest.approx(q.total_fare, abs=0.01)


def test_known_fixture_fare_present(quotes):
    """The manually verified DXN-BOM quote: total 7596 = base 5916 + fees/taxes 1680."""
    match = [
        q for q in quotes
        if q.origin == "DXN" and q.total_fare == pytest.approx(7596.0) and q.rbd == "U0"
    ]
    assert match, "verified 7596/U0 DXN-BOM fare not found"
    q = match[0]
    assert q.base_fare == pytest.approx(5916.0)
    assert q.components["UDF"] == pytest.approx(578.0)
    assert q.components["DUDF"] == pytest.approx(89.0)
    assert q.components["TaxSum"] == pytest.approx(302.0)


def test_prism_signals_present(quotes):
    assert all(q.rbd for q in quotes), "classOfService (RBD) missing on some quotes"
    assert any(q.seats_available is not None for q in quotes), "availableCount not parsed"
    assert all(q.source_tier == SourceTier.T1_DIRECT for q in quotes)


def test_no_integrity_warnings_on_this_fixture(quotes):
    warned = [q for q in quotes if q.integrity_warning]
    assert not warned, f"unexpected integrity warnings: {[q.integrity_warning for q in warned[:3]]}"


# --------------------------------------------------------------------------- #
# calendar schema (61-day capture with taxesAndFees + available seats)
# --------------------------------------------------------------------------- #
from collectors.adapters.akasa import parse_calendar_response

CAL_FIXTURE = Path(__file__).parent / "fixtures" / "akasa" / "calendar_sample.json"


def test_calendar_parses_all_open_days():
    qs = parse_calendar_response(
        CAL_FIXTURE.read_text(encoding="utf-8", errors="replace"), "DEL", "BOM"
    )
    assert len(qs) >= 50  # 61 days minus soldOut/noFlights
    assert all(q.flight_no is None and q.fare_family == "CAL_MIN" for q in qs)
    assert all(q.origin == "DEL" and q.dest == "BOM" for q in qs)


def test_calendar_tax_split_when_present():
    qs = parse_calendar_response(
        CAL_FIXTURE.read_text(encoding="utf-8", errors="replace"), "DEL", "BOM"
    )
    q = next(x for x in qs if x.total_fare == pytest.approx(9249.0))
    assert q.taxes_fees == pytest.approx(1352.0)
    assert q.base_fare == pytest.approx(9249.0 - 1352.0)
    assert q.seats_available == 11


# --------------------------------------------------------------------------- #
# rich schema, live POST capture (2 Sep 2026) — the endpoint collect() now hits
# --------------------------------------------------------------------------- #
from collectors.adapters.akasa import build_search_body

LIVE_FIXTURE = Path(__file__).parent / "fixtures" / "akasa" / "rich_live_post_2026-09-02.json"


def test_live_post_capture_parses_with_rbd_and_base():
    qs = parse_search_response(LIVE_FIXTURE.read_text(encoding="utf-8", errors="replace"))
    assert len(qs) >= 10
    assert all(q.rbd for q in qs)
    assert all(q.base_fare and q.base_fare < q.total_fare for q in qs)
    assert all(q.seats_available for q in qs)
    # MACs on: DEL search may return Noida (DXN) / Navi Mumbai (NMI) legs too
    assert {"DEL-BOM"} <= {f"{q.origin}-{q.dest}" for q in qs}
    assert not any(q.integrity_warning for q in qs)


def test_build_search_body_shape():
    from datetime import date as d

    body = build_search_body("DEL", "BOM", d(2026, 9, 9))
    crit = body["criteria"][0]
    assert crit["stations"]["originStationCodes"] == ["DEL"]
    assert crit["dates"]["beginDate"] == "2026-09-09T00:00:00"
    assert body["passengers"]["types"] == [{"type": "ADT", "count": 1}]
    assert body["codes"]["currencyCode"] == "INR"


def test_build_search_body_station_alias():
    # Akasa serves Goa at Mopa (GOX); GOI in the body 400s (8 Sep 2026)
    from datetime import date as d

    body = build_search_body("GOI", "DEL", d(2026, 9, 15))
    assert body["criteria"][0]["stations"]["originStationCodes"] == ["GOX"]
    assert body["criteria"][0]["stations"]["destinationStationCodes"] == ["DEL"]


# --------------------------------------------------------------------------- #
# live request resilience (no network calls)
# --------------------------------------------------------------------------- #


class _NoWaitBudget:
    async def wait(self):
        return None


class _NoWaitPolicy:
    def budget(self, _host):
        return _NoWaitBudget()


def test_search_retries_transient_dns_failure(monkeypatch):
    from collectors.adapters import akasa as module
    from collectors.adapters.akasa import AkasaCollector
    from playwright.async_api import Error as PlaywrightError

    collector = AkasaCollector(_NoWaitPolicy())
    calls = 0
    response = SimpleNamespace(status=200)

    async def flaky_search(*_args):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PlaywrightError(
                "getaddrinfo ENOTFOUND prod-bl.qp.akasaair.com\n"
                "authorization: secret-site-token"
            )
        return response

    async def no_sleep(_seconds):
        return None

    collector._token = "secret-site-token"
    monkeypatch.setattr(collector, "_search", flaky_search)
    monkeypatch.setattr(module.asyncio, "sleep", no_sleep)

    result = asyncio.run(
        collector._search_with_retry("BLR", "BOM", dt_date(2026, 9, 28))
    )

    assert result is response
    assert calls == 2


def test_search_exhaustion_redacts_authorization(monkeypatch):
    from collectors.adapters import akasa as module
    from collectors.adapters.akasa import AkasaCollector
    from playwright.async_api import Error as PlaywrightError

    collector = AkasaCollector(_NoWaitPolicy())

    async def failed_search(*_args):
        raise PlaywrightError(
            "getaddrinfo ENOTFOUND prod-bl.qp.akasaair.com\n"
            "authorization: secret-site-token"
        )

    async def no_sleep(_seconds):
        return None

    collector._token = "secret-site-token"
    monkeypatch.setattr(collector, "_search", failed_search)
    monkeypatch.setattr(module.asyncio, "sleep", no_sleep)

    with pytest.raises(RuntimeError) as caught:
        asyncio.run(
            collector._search_with_retry("BLR", "BOM", dt_date(2026, 9, 28))
        )

    assert "after 4 attempts" in str(caught.value)
    assert "secret-site-token" not in str(caught.value)
