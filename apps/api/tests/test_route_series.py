import pandas as pd


def test_booking_curve_keeps_latest_fares_when_products_churn(monkeypatch):
    """Fare-level curves must not disappear when fixed-base matching is thin."""
    from api import main

    rows = []
    for day, flight in (("2026-09-17", "QP100"), ("2026-09-18", "QP900")):
        for lead_days in (1, 7, 15, 30, 45):
            rows.append(
                {
                    "origin": "DEL",
                    "dest": "BOM",
                    "carrier": "QP",
                    "flight_no": flight,
                    "lead_days": lead_days,
                    "total_fare": 4_000 + lead_days,
                    "base_fare": 3_000 + lead_days,
                    "rbd": "Y",
                    "seats_available": 5,
                    "source": "akasa",
                    "collected_at": f"{day}T00:20:00+05:30",
                }
            )

    monkeypatch.setattr(main, "_quotes_df", lambda route_code=None: pd.DataFrame(rows))
    result = main.get_route_series.__wrapped__(route_code="DEL-BOM")
    latest = [row for row in result["data"] if row["date"] == "2026-09-18"]

    assert {row["leadtime_code"] for row in latest} == {1, 7, 15, 30, 45}
    assert all(row["cheapest_fare"] is not None for row in latest)
    assert all(row["index"] is None for row in latest)
    assert all(row["n_matched_products"] == 0 for row in latest)
