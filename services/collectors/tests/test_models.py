from datetime import UTC, datetime, timedelta

from collectors.models import IST, Cabin, FareQuote, SourceTier


def ist_today():
    return datetime.now(IST).date()


def make_quote(**overrides) -> FareQuote:
    base = {
        "carrier": "QP",
        "flight_no": "QP1385",
        "origin": "DEL",
        "dest": "BOM",
        "departure_date": ist_today() + timedelta(days=7),
        "cabin": Cabin.ECONOMY,
        "total_fare": 4899.0,
        "source": "serpapi",
        "source_tier": SourceTier.T1_LICENSED,
    }
    base.update(overrides)
    return FareQuote(**base)


def test_lead_days_is_days_to_departure():
    q = make_quote()
    assert q.lead_days == 7


def test_fingerprint_stable_within_day_and_unique_across_products():
    a = make_quote()
    b = make_quote()
    assert a.quote_fingerprint == b.quote_fingerprint  # same panel key, same day → dedup
    c = make_quote(flight_no="QP1102")
    assert c.quote_fingerprint != a.quote_fingerprint


def test_fingerprint_differs_across_collection_days():
    today = make_quote()
    yesterday = make_quote(
        collected_at=datetime.now(UTC) - timedelta(days=1)
    )
    assert today.quote_fingerprint != yesterday.quote_fingerprint  # panel history preserved
