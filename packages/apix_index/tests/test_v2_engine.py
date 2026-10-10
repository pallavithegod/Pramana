"""Contract tests: gates, GEKS-T churn handling, BCWFI aggregation, PRISM, nowcast."""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest
from apix_index import aggregate
from apix_index.aggregate import compute_apix_v2
from apix_index.gates import apply_gates
from apix_index.multilateral import GEKS_WINDOW_DAYS, geks_tornqvist, rolling_geks
from apix_index.nowcast import nowcast_month
from apix_index.prism import classify_days, decompose

# --------------------------------------------------------------------------- #
# gates
# --------------------------------------------------------------------------- #

def _quotes(fares, route=("DEL", "BOM"), lead=7):
    return pd.DataFrame(
        {
            "origin": route[0], "dest": route[1], "lead_days": lead,
            "total_fare": fares,
        }
    )


def test_gates_reject_extreme_outlier_with_reason():
    clean, rejected = apply_gates(_quotes([5000, 5200, 4900, 5100, 5050, 5150, 900000]))
    assert len(rejected) == 1
    assert rejected.iloc[0]["reject_code"] == "MZ_GT_5"
    assert rejected.iloc[0]["total_fare"] == 900000
    assert len(clean) == 6


def test_gates_keep_normal_dispersion_and_thin_strata():
    fares = [4000, 4500, 5200, 6100, 7000, 9000]  # legit airfare spread
    clean, rejected = apply_gates(_quotes(fares))
    assert len(clean) == len(fares) and rejected.empty or len(rejected) == 0
    # thin stratum (n < MIN_N): never rejected
    clean2, _rejected2 = apply_gates(_quotes([5000, 90000]))
    assert len(clean2) == 2


def test_gates_nonpositive():
    _clean, rejected = apply_gates(_quotes([5000, -10, 5100, 5050, 5200]))
    assert "NONPOSITIVE" in set(rejected["reject_code"])


# --------------------------------------------------------------------------- #
# GEKS-T: transitive, and robust to product churn
# --------------------------------------------------------------------------- #

def _panel(rows):
    return pd.DataFrame(rows, columns=["period", "product_id", "price"])


def test_geks_flat_prices_flat_index():
    rows = [(d, p, 5000.0) for d in ("d1", "d2", "d3") for p in ("A", "B")]
    idx = geks_tornqvist(_panel(rows))
    assert np.allclose(idx.values, 100.0)


def test_geks_bridges_full_product_churn_through_link_day():
    # product A exists d1-d2 (price +10%), product B exists d2-d3 (price +10%).
    # No product spans d1→d3 — fixed-base matched dies; GEKS bridges via d2.
    rows = [
        ("d1", "A", 1000.0), ("d2", "A", 1100.0),
        ("d2", "B", 2000.0), ("d3", "B", 2200.0),
    ]
    idx = geks_tornqvist(_panel(rows))
    assert idx["d1"] == pytest.approx(100.0)
    assert idx["d3"] == pytest.approx(121.0, rel=1e-3)  # 1.1 × 1.1


def test_rolling_geks_mean_splice_no_revision():
    rng = np.random.default_rng(7)
    rows = []
    level = 1000.0
    for i in range(20):
        level *= 1.01
        for p in ("A", "B", "C"):
            rows.append((f"d{i:02d}", p, level * (1 + rng.normal(0, 0.001))))
    full = rolling_geks(_panel(rows), window=8)
    assert len(full) == 20
    # steady 1%/day drift must be tracked without chain drift
    assert full.iloc[-1] / full.iloc[0] == pytest.approx(1.01**19, rel=0.01)
    # published values never revised: recompute with one more day appended
    rows2 = rows + [("d20", p, level * 1.01) for p in ("A", "B", "C")]
    full2 = rolling_geks(_panel(rows2), window=8)
    assert np.allclose(full2.iloc[:20].values, full.values)


def test_compute_apix_v2_shape_and_stability():
    rows = []
    for day in ("2026-09-01", "2026-09-02", "2026-09-03"):
        for f in ("QP100", "QP200", "6E300"):
            rows.append(
                {
                    "origin": "DEL", "dest": "BOM", "carrier": f[:2], "flight_no": f,
                    "lead_days": 7, "total_fare": 5000.0,
                    "collected_at": f"{day}T01:00:00+05:30",
                }
            )
    out = compute_apix_v2(pd.DataFrame(rows), {"DEL-BOM": 1.0})
    assert list(out.columns) == ["day", "apix", "n_cells", "n_matched", "inflation_dod"]
    assert np.allclose(out["apix"], 100.0)


def test_production_apix_uses_locked_14_day_window(monkeypatch):
    observed_windows = []

    def capture_window(cell, window):
        observed_windows.append(window)
        periods = sorted(cell["period"].unique())
        return pd.Series({period: 100.0 for period in periods})

    monkeypatch.setattr(aggregate, "rolling_geks", capture_window)
    rows = [
        {
            "origin": "DEL",
            "dest": "BOM",
            "carrier": "QP",
            "flight_no": "QP100",
            "lead_days": 7,
            "total_fare": 5000.0,
            "collected_at": f"{day}T01:00:00+05:30",
        }
        for day in ("2026-09-01", "2026-09-02")
    ]

    compute_apix_v2(pd.DataFrame(rows), {"DEL-BOM": 1.0})

    assert GEKS_WINDOW_DAYS == 14
    assert observed_windows == [14]
    assert "window" not in inspect.signature(compute_apix_v2).parameters


# --------------------------------------------------------------------------- #
# PRISM
# --------------------------------------------------------------------------- #

def _rbd_quotes(day, ladder, seats_gone=0, shift=0.0, external_fee=1000.0):
    """One flight, ladder = {rbd: base}; seats_gone cheapest rungs absent."""
    rows = []
    for i, (rbd, base) in enumerate(sorted(ladder.items(), key=lambda kv: kv[1])):
        if i < seats_gone:
            continue
        b = base * (1 + shift)
        rows.append(
            {
                "carrier": "QP", "flight_no": "QP100", "origin": "DEL", "dest": "BOM",
                "departure_date": "2026-09-10", "rbd": rbd,
                "base_fare": b, "total_fare": b + external_fee,
                "components": {"FarePrice": b, "UDF": external_fee},
                "collected_at": f"{day}T01:00:00+05:30",
            }
        )
    return rows


LADDER = {"U": 3000.0, "T": 4000.0, "Q": 5500.0, "Y": 8000.0}


def test_prism_classifies_pure_rationing():
    q = pd.DataFrame(
        _rbd_quotes("2026-09-01", LADDER) + _rbd_quotes("2026-09-02", LADDER, seats_gone=1)
    )
    ev = classify_days(q)
    assert set(ev["event"]) == {"AVAILABILITY_PRESSURE_PROXY"}
    assert ev.iloc[0]["rbd_from"] == "U" and ev.iloc[0]["rbd_to"] == "T"


def test_prism_classifies_pure_filing():
    q = pd.DataFrame(
        _rbd_quotes("2026-09-01", LADDER) + _rbd_quotes("2026-09-02", LADDER, shift=0.05)
    )
    ev = classify_days(q)
    assert set(ev["event"]) == {"FILING"}
    assert ev.iloc[0]["magnitude_pct"] == pytest.approx(5.0, abs=0.2)


def test_prism_decomposition_splits_market_move():
    # Rung-pressure day: market +33% (U→T); filing stays flat.
    q = pd.DataFrame(
        _rbd_quotes("2026-09-01", LADDER) + _rbd_quotes("2026-09-02", LADDER, seats_gone=1)
    )
    d = decompose(q).set_index("day")
    assert d.loc["2026-09-02", "filing_index"] == pytest.approx(100.0)
    assert d.loc["2026-09-02", "market_index"] > 110
    assert d.loc["2026-09-02", "availability_pressure_index"] > 110
    assert d.loc["2026-09-02", "availability_status"] == "AVAILABILITY_PRESSURE_PROXY"


def test_prism_external_fee_guard_prevents_pure_demand_label():
    q = pd.DataFrame(
        _rbd_quotes("2026-09-01", LADDER, external_fee=1000)
        + _rbd_quotes("2026-09-02", LADDER, seats_gone=1, external_fee=1200)
    )

    events = classify_days(q)
    assert set(events["event"]) == {"EXTERNAL_FEE_CHANGE"}
    assert events.iloc[0]["fee_change_inr"] == pytest.approx(200.0)

    decomposition = decompose(q).set_index("day")
    assert bool(decomposition.loc["2026-09-02", "external_fee_change"]) is True
    assert (
        decomposition.loc["2026-09-02", "availability_status"]
        == "EXTERNAL_FEE_MOVEMENT_PRESENT"
    )


# --------------------------------------------------------------------------- #
# nowcast
# --------------------------------------------------------------------------- #

def test_nowcast_needs_min_days():
    daily = pd.DataFrame({"date": ["2026-09-01", "2026-09-02"], "index": [100, 101]})
    assert nowcast_month(daily) is None


def test_nowcast_tracks_level():
    rng = np.random.default_rng(3)
    dates = pd.date_range("2026-09-01", periods=20).strftime("%Y-%m-%d")
    daily = pd.DataFrame({"date": dates, "index": 105.0 + rng.normal(0, 0.8, 20)})
    nc = nowcast_month(daily)
    assert nc is not None
    assert nc["nowcast_index"] == pytest.approx(105.0, abs=1.0)
    assert nc["band_low"] < nc["nowcast_index"] < nc["band_high"]


def test_compute_apix_v2_new_route_onset_is_invisible():
    # 2 days of a stable route, then a NEW route (10x price level, huge weight)
    # appears on day 3: under chained aggregation the headline must NOT jump —
    # the newcomer contributes only from its second observed day.
    rows = []
    for day in ("2026-09-01", "2026-09-02", "2026-09-03"):
        for f in ("QP100", "QP200"):
            rows.append(
                {
                    "origin": "DEL", "dest": "BOM", "carrier": "QP", "flight_no": f,
                    "lead_days": 7, "total_fare": 5000.0,
                    "collected_at": f"{day}T01:00:00+05:30",
                }
            )
    for f in ("6E900", "6E901"):
        rows.append(
            {
                "origin": "CCU", "dest": "BOM", "carrier": "6E", "flight_no": f,
                "lead_days": 7, "total_fare": 50000.0,
                "collected_at": "2026-09-03T01:00:00+05:30",
            }
        )
    out = compute_apix_v2(pd.DataFrame(rows), {"DEL-BOM": 0.01, "CCU-BOM": 0.99})
    assert np.allclose(out["apix"], 100.0)  # no fake jump on 3 Sep
