"""Engine-specific parsers. Values stay comparable only within explicit identities."""

import hashlib
import math
import re
from urllib.parse import urlsplit


def product_id(domain: str, *identity: object) -> str:
    return (
        domain + "_" + hashlib.sha256("|".join(str(v) for v in identity).encode()).hexdigest()[:24]
    )


def safe_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.username or parsed.password or "api_key" in parsed.query.lower():
        return None
    return value


def price(value: object) -> float | None:
    try:
        number = float(value)  # formatted prices are intentionally not guessed
        return number if math.isfinite(number) and number > 0 else None
    except (TypeError, ValueError):
        return None


def flights(data: dict, params: dict) -> list[dict]:
    out, seen = [], set()
    for item in data.get("best_flights", []) + data.get("other_flights", []):
        legs = item.get("flights", [])
        value = price(item.get("price"))
        if len(legs) != 1 or value is None:
            continue
        leg = legs[0]
        origin = leg.get("departure_airport", {}).get("id")
        dest = leg.get("arrival_airport", {}).get("id")
        if origin != params["departure_id"] or dest != params["arrival_id"]:
            continue
        number = leg.get("flight_number")
        cabin = leg.get("travel_class", "")
        if not number or cabin.lower() != "economy":
            continue
        pid = product_id(
            "flight", origin, dest, params["outbound_date"], number, cabin, params["currency"]
        )
        if pid in seen:
            continue
        seen.add(pid)
        out.append(
            {
                "product_id": pid,
                "title": f"{number} · {origin}–{dest}",
                "value": value,
                "currency": params["currency"],
                "unit": "one-way ticket",
                "source": "google_flights",
                "url": None,
                "specification": {
                    "departure_date": params["outbound_date"],
                    "flight_number": number,
                    "cabin": cabin,
                },
                "base_fare": None,
                "taxes_fees": None,
            }
        )
    return out


def hotels(data: dict, params: dict) -> list[dict]:
    out = []
    for item in data.get("properties", []):
        rate = item.get("rate_per_night", {})
        value = price(rate.get("extracted_lowest"))
        token = item.get("property_token")
        if value is None or not token:
            continue
        out.append(
            {
                "product_id": product_id(
                    "hotel",
                    token,
                    params["check_in_date"],
                    params["check_out_date"],
                    params["adults"],
                    params["currency"],
                ),
                "title": item.get("name", "Hotel"),
                "value": value,
                "currency": params["currency"],
                "unit": "night (displayed rate)",
                "source": "google_hotels",
                "url": safe_url(item.get("link")),
                "specification": {
                    "check_in": params["check_in_date"],
                    "check_out": params["check_out_date"],
                    "adults": params["adults"],
                },
                "warning": "Room type, cancellation and fees may differ; verify before indexing",
            }
        )
    return out


def shopping(data: dict, params: dict) -> list[dict]:
    results = list(data.get("shopping_results", []))
    for group in data.get("categorized_shopping_results", []):
        results.extend(group.get("shopping_results", []))
    out, seen = [], set()
    for item in results:
        value = price(item.get("extracted_price"))
        identifier = item.get("product_id")
        title, seller = item.get("title", ""), item.get("source", "")
        displayed = str(item.get("price", ""))
        # India market alone does not prove a result's currency.
        if value is None or not identifier or not re.search(r"₹|\bINR\b|\bRs\.?", displayed):
            continue
        pid = product_id("retail", identifier, title, seller, "INR", params["q"])
        if pid in seen:
            continue
        seen.add(pid)
        out.append(
            {
                "product_id": pid,
                "title": title,
                "seller": seller,
                "value": value,
                "currency": "INR",
                "unit": "listed pack",
                "source": "google_shopping",
                "url": safe_url(item.get("product_link") or item.get("link")),
                "warning": "Match model, pack, condition, delivery and fees; search rank is not weight",
            }
        )
    return out


def amazon(data: dict, params: dict) -> list[dict]:
    out, seen = [], set()
    for item in data.get("organic_results", []):
        amount = item.get("price", {})
        if not isinstance(amount, dict):
            continue
        value = price(amount.get("value"))
        asin = item.get("asin")
        if value is None or not asin or amount.get("currency") not in {"INR", "₹"}:
            continue
        pid = product_id("amazon", asin, item.get("title", ""), params["amazon_domain"], "INR")
        if pid in seen:
            continue
        seen.add(pid)
        out.append(
            {
                "product_id": pid,
                "title": item.get("title", "Amazon item"),
                "asin": asin,
                "value": value,
                "currency": "INR",
                "unit": "listed pack",
                "source": "amazon",
                "url": safe_url(item.get("link")),
                "warning": "Seller/variant/pack changes can invalidate comparability",
            }
        )
    return out


def jobs(data: dict, params: dict) -> list[dict]:
    out, seen = [], set()
    for item in data.get("jobs_results", []):
        jid = item.get("job_id")
        if not jid or jid in seen:
            continue
        seen.add(jid)
        detected = item.get("detected_extensions", {})
        options = item.get("apply_options", [])
        out.append(
            {
                "product_id": product_id("job", jid),
                "title": item.get("title", "Job"),
                "company": item.get("company_name"),
                "location": item.get("location"),
                "salary_text": detected.get("salary"),
                "posted_at": detected.get("posted_at"),
                "source": "google_jobs",
                "url": safe_url(options[0].get("link")) if options else None,
                "value": None,
                "warning": "Advertised salary is optional; postings are not employment totals",
            }
        )
    return out


def news(data: dict, params: dict) -> list[dict]:
    out, seen = [], set()

    def visit(items: list) -> None:
        for item in items:
            url = safe_url(item.get("link"))
            if url and url not in seen:
                seen.add(url)
                source = item.get("source", {})
                out.append(
                    {
                        "title": item.get("title", "Article"),
                        "url": url,
                        "source": source.get("name") if isinstance(source, dict) else source,
                        "published_at": item.get("iso_date") or item.get("date"),
                        "snippet": str(item.get("snippet", ""))[:600],
                    }
                )
            visit(item.get("stories", []))
            highlight = item.get("highlight")
            if isinstance(highlight, dict):
                visit([highlight])

    visit(data.get("news_results", []))
    return out
