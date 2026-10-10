"""Contract tests for SpiceJet lowfare and EaseMyTrip reprice parsers,
against REAL captures (31 Aug 2026)."""

from pathlib import Path

import pytest
from collectors.adapters.easemytrip import parse_reprice_response
from collectors.adapters.spicejet import parse_lowfare_response

FIXTURES = Path(__file__).parent / "fixtures"


# ----------------------------- SpiceJet lowfare ----------------------------- #

def sj_quotes():
    return parse_lowfare_response(
        (FIXTURES / "spicejet" / "lowfare_sample.json").read_text(
            encoding="utf-8", errors="replace"
        )
    )


def test_sj_skips_null_fare_days():
    qs = sj_quotes()
    assert len(qs) == 6  # 7 entries in strip, 1 has lowestFareAmount=null


def test_sj_all_in_total_and_tax_split():
    # includeTaxesAndFees=true in fixture → fareAmount IS the total
    q = next(x for x in sj_quotes() if x.total_fare == pytest.approx(5179.0))
    assert q.carrier == "SG" and q.origin == "DEL" and q.dest == "BOM"
    assert q.taxes_fees == pytest.approx(1559.0)
    assert q.base_fare == pytest.approx(5179.0 - 1559.0)
    assert str(q.departure_date) == "2026-09-01"


# ----------------------------- EaseMyTrip reprice ---------------------------- #

def emt_quotes():
    return parse_reprice_response(
        (FIXTURES / "easemytrip" / "reprice_sample.json").read_text(
            encoding="utf-8", errors="replace"
        )
    )


def test_emt_panel_key_and_rbd():
    qs = emt_quotes()
    assert qs, "no quotes parsed"
    q = qs[0]
    assert q.carrier == "SG" and q.flight_no == "SG802"
    assert q.origin == "DEL" and q.dest == "BOM"
    assert str(q.departure_date) == "2026-09-01"
    assert q.rbd == "I"  # fareCls — the PRISM rung, via an OTA
    assert q.fare_family == "SpiceSaver"


def test_emt_component_split_with_charge_codes():
    q = emt_quotes()[0]
    assert q.total_fare == pytest.approx(6408.0)
    assert q.base_fare == pytest.approx(4863.0)
    assert q.taxes_fees == pytest.approx(6408.0 - 4863.0)
    assert q.components["YQ"] == pytest.approx(599.0)   # fuel surcharge — EMT-only visibility
    assert q.components["UDF"] == pytest.approx(152.0)
    assert q.components["ASF"] == pytest.approx(236.0)
