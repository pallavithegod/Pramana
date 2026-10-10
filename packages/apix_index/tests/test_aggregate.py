import numpy as np
import pandas as pd
import pytest
from apix_index.aggregate import compute_apix, lead_bucket


def make_quotes(rows):
    return pd.DataFrame(
        rows,
        columns=["origin", "dest", "carrier", "flight_no", "lead_days", "total_fare", "collected_at"],
    )


def test_lead_bucket_snapping():
    s = pd.Series([1, 3, 8, 14, 22, 40, 60])
    assert lead_bucket(s).tolist() == [1, 1, 7, 15, 15, 45, 45]


def test_two_day_index_geometric_mean():
    # Day 1: two flights at 4000 and 6000. Day 2: 4400 (+10%) and 5400 (-10%).
    rows = [
        ["DEL", "BOM", "QP", "QP1101", 7, 4000, "2026-08-30T02:00:00+05:30"],
        ["DEL", "BOM", "6E", "6E2001", 7, 6000, "2026-08-30T02:00:00+05:30"],
        ["DEL", "BOM", "QP", "QP1101", 7, 4400, "2026-08-31T02:00:00+05:30"],
        ["DEL", "BOM", "6E", "6E2001", 7, 5400, "2026-08-31T02:00:00+05:30"],
    ]
    daily = compute_apix(make_quotes(rows))
    assert len(daily) == 2
    assert daily.iloc[0]["apix"] == pytest.approx(100.0)
    expected = np.exp(0.5 * (np.log(1.1) + np.log(0.9))) * 100
    assert daily.iloc[1]["apix"] == pytest.approx(expected)


def test_unmatched_flight_excluded():
    # QP9999 exists only on day 2 → must not distort the index (new product, no base price)
    rows = [
        ["DEL", "BOM", "QP", "QP1101", 7, 4000, "2026-08-30T02:00:00+05:30"],
        ["DEL", "BOM", "QP", "QP1101", 7, 4000, "2026-08-31T02:00:00+05:30"],
        ["DEL", "BOM", "QP", "QP9999", 7, 99999, "2026-08-31T02:00:00+05:30"],
    ]
    daily = compute_apix(make_quotes(rows))
    assert daily.iloc[1]["apix"] == pytest.approx(100.0)


def test_route_weights_applied():
    # DEL-BOM +10%, BLR-DEL flat; DEL-BOM carries 3x the weight
    rows = [
        ["DEL", "BOM", "QP", "QP1101", 7, 4000, "2026-08-30T02:00:00+05:30"],
        ["BLR", "DEL", "6E", "6E2001", 7, 5000, "2026-08-30T02:00:00+05:30"],
        ["DEL", "BOM", "QP", "QP1101", 7, 4400, "2026-08-31T02:00:00+05:30"],
        ["BLR", "DEL", "6E", "6E2001", 7, 5000, "2026-08-31T02:00:00+05:30"],
    ]
    daily = compute_apix(make_quotes(rows), route_weights={"DEL-BOM": 0.75, "BLR-DEL": 0.25})
    expected = np.exp(0.75 * np.log(1.1)) * 100
    assert daily.iloc[1]["apix"] == pytest.approx(expected)


def test_cheapest_quote_per_product_wins():
    # same flight quoted twice on one day → min is the CPI-spec price
    rows = [
        ["DEL", "BOM", "QP", "QP1101", 7, 4000, "2026-08-30T02:00:00+05:30"],
        ["DEL", "BOM", "QP", "QP1101", 7, 4500, "2026-08-30T03:00:00+05:30"],
        ["DEL", "BOM", "QP", "QP1101", 7, 8000, "2026-08-31T02:00:00+05:30"],
    ]
    daily = compute_apix(make_quotes(rows))
    assert daily.iloc[1]["apix"] == pytest.approx(200.0)
