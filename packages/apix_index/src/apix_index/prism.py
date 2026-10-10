"""PRISM v1 — Price–Rationing Index Separation Method (PLAN §3.0, the headline IP).

Inputs are RBD-level quotes (carrier, flight_no, departure_date, rbd, base_fare,
total_fare, seats, collection day) — the Akasa rich feed, live since 2 Sep 2026.

Definitions (v1, deterministic and testable):
  RUNG VALUE  v(day, carrier, route, rbd) = median base fare of that booking
              class across the carrier's flights on the route that day.
  FILING EVENT   rung values shift fleet-wide: median |Δ ln v| across RBDs
                 matched between consecutive days exceeds TOL_FILING.
                 → pure price change → CPI component.
  RUNG HEURISTIC a flight's cheapest returned rung moves UP the ladder while
                 matched rung values are stable (≤ TOL_FILING).
                 → availability-pressure proxy for RBI research.

Decomposition:  market index = what the marginal buyer pays (cheapest available
                                per flight, matched across days)
                filing index = matched-RBD index of rung values
                availability pressure index = market / filing × 100 (rung heuristic)
"""

from __future__ import annotations

import json
from itertools import pairwise

import numpy as np
import pandas as pd

TOL_FILING = 0.01  # 1% median rung shift = a filing event
# Ignore paise/rounding and small tax arithmetic noise; material airport fee
# changes are much larger than this threshold.
EXTERNAL_FEE_TOLERANCE_INR = 10.0
EXTERNAL_FEE_CODES = frozenset(
    {"UDF", "DUDF", "ASF", "CUTE", "GST", "CGST", "SGST", "IGST", "TAXSUM", "AAT"}
)


def _external_fee_amount(components: object) -> float:
    """Sum only returned statutory/airport components; never infer missing codes."""
    if isinstance(components, str):
        try:
            components = json.loads(components)
        except (TypeError, ValueError):
            return 0.0
    if not isinstance(components, dict):
        return 0.0
    return float(
        sum(
            amount
            for code, amount in components.items()
            if str(code).upper() in EXTERNAL_FEE_CODES and isinstance(amount, int | float)
        )
    )


def _external_fee_panel(quotes: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "day",
        "carrier",
        "route",
        "flight_no",
        "departure_date",
        "rbd",
        "external_fee",
    ]
    if "components" not in quotes.columns:
        return pd.DataFrame(columns=columns)
    df = quotes.dropna(subset=["rbd", "flight_no", "departure_date"]).copy()
    df["day"] = df["collected_at"].str[:10]
    df["route"] = df["origin"] + "-" + df["dest"]
    df["external_fee"] = df["components"].map(_external_fee_amount)
    keys = ["day", "carrier", "route", "flight_no", "departure_date", "rbd"]
    return df.groupby(keys, as_index=False)["external_fee"].median()


def _external_fee_shift(
    fees: pd.DataFrame, carrier: str, route: str, prev: str, cur: str
) -> tuple[bool, float, float, int]:
    """Detect a systematic fee move on matched flight/date/RBD products."""
    subset = fees[(fees["carrier"] == carrier) & (fees["route"] == route)]
    keys = ["flight_no", "departure_date", "rbd"]
    matched = subset[subset["day"] == prev][keys + ["external_fee"]].merge(
        subset[subset["day"] == cur][keys + ["external_fee"]],
        on=keys,
        suffixes=("_prev", "_cur"),
    )
    if matched.empty:
        return False, 0.0, 0.0, 0
    delta = matched["external_fee_cur"] - matched["external_fee_prev"]
    median_delta = float(delta.median())
    same_direction_share = float(
        (delta * np.sign(median_delta) > EXTERNAL_FEE_TOLERANCE_INR).mean()
    )
    previous = matched.loc[matched["external_fee_prev"] > 0, "external_fee_prev"]
    current = matched.loc[previous.index, "external_fee_cur"]
    pct = float(np.median(current / previous - 1) * 100) if not previous.empty else 0.0
    changed = (
        abs(median_delta) > EXTERNAL_FEE_TOLERANCE_INR and same_direction_share >= 0.5
    )
    return changed, pct, median_delta, len(matched)


def rung_table(quotes: pd.DataFrame) -> pd.DataFrame:
    """Per (day, carrier, route, rbd): the rung value. Requires rbd + base_fare."""
    df = quotes.dropna(subset=["rbd", "base_fare"]).copy()
    df["day"] = df["collected_at"].str[:10]
    df["route"] = df["origin"] + "-" + df["dest"]
    return (
        df.groupby(["day", "carrier", "route", "rbd"], as_index=False)["base_fare"]
        .median()
        .rename(columns={"base_fare": "rung_value"})
    )


def cheapest_available(quotes: pd.DataFrame) -> pd.DataFrame:
    """Per (day, flight-leg): the cheapest open rung — what the marginal buyer pays."""
    df = quotes.dropna(subset=["rbd"]).copy()
    df["day"] = df["collected_at"].str[:10]
    df["route"] = df["origin"] + "-" + df["dest"]
    idx = df.groupby(["day", "carrier", "route", "flight_no", "departure_date"])[
        "total_fare"
    ].idxmin()
    return df.loc[
        idx, ["day", "carrier", "route", "flight_no", "departure_date", "rbd", "total_fare"]
    ].rename(columns={"rbd": "active_rbd", "total_fare": "paid_price"})


def classify_days(quotes: pd.DataFrame) -> pd.DataFrame:
    """Day-over-day event log per (carrier, route)."""
    rungs = rung_table(quotes)
    active = cheapest_available(quotes)
    fees = _external_fee_panel(quotes)
    events: list[dict] = []
    for (carrier, route), g in rungs.groupby(["carrier", "route"]):
        days = sorted(g["day"].unique())
        for prev, cur in pairwise(days):
            a = g[g["day"] == prev].set_index("rbd")["rung_value"]
            b = g[g["day"] == cur].set_index("rbd")["rung_value"]
            common = a.index.intersection(b.index)
            filing_shift = (
                float(np.median(np.log(b[common] / a[common]))) if len(common) else np.nan
            )
            is_filing = np.isfinite(filing_shift) and abs(filing_shift) > TOL_FILING

            # rationing: same flight's active rung climbed while ladder stable
            act = active[(active["carrier"] == carrier) & (active["route"] == route)]
            key = ["flight_no", "departure_date"]
            merged = act[act["day"] == prev][key + ["active_rbd", "paid_price"]].merge(
                act[act["day"] == cur][key + ["active_rbd", "paid_price"]],
                on=key,
                suffixes=("_prev", "_cur"),
            )
            climbed = merged[
                (merged["active_rbd_prev"] != merged["active_rbd_cur"])
                & (merged["paid_price_cur"] > merged["paid_price_prev"])
            ]
            fee_changed, fee_pct, fee_inr, fee_evidence = _external_fee_shift(
                fees, carrier, route, prev, cur
            )
            if is_filing:
                events.append(
                    {
                        "day": cur, "carrier": carrier, "route": route,
                        "event": "FILING",
                        "magnitude_pct": round(float(np.expm1(filing_shift)) * 100, 2),
                        "n_evidence": len(common),
                    }
                )
            elif fee_changed:
                events.append(
                    {
                        "day": cur,
                        "carrier": carrier,
                        "route": route,
                        "event": "EXTERNAL_FEE_CHANGE",
                        "magnitude_pct": round(fee_pct, 2),
                        "fee_change_inr": round(fee_inr, 2),
                        "n_evidence": fee_evidence,
                    }
                )
            for _, r in climbed.iterrows():
                if not is_filing and not fee_changed:
                    events.append(
                        {
                            "day": cur, "carrier": carrier, "route": route,
                            "event": "AVAILABILITY_PRESSURE_PROXY",
                            "magnitude_pct": round(
                                (r["paid_price_cur"] / r["paid_price_prev"] - 1) * 100, 2
                            ),
                            "n_evidence": 1,
                            "flight_no": r["flight_no"],
                            "rbd_from": r["active_rbd_prev"],
                            "rbd_to": r["active_rbd_cur"],
                        }
                    )
    return pd.DataFrame(events)


def decompose(quotes: pd.DataFrame) -> pd.DataFrame:
    """Daily filing, market, and availability-pressure indices (base 100).

    filing = chained matched-RBD Jevons on rung values;
    market = chained matched-flight Jevons on cheapest-available price;
    availability pressure = market / filing × 100. This is a rung heuristic,
    not a physical cabin-utilization measure. Returned statutory/airport component changes are
    flagged so the residual is not described as pure demand pressure.
    """
    rungs = rung_table(quotes)
    active = cheapest_available(quotes)

    def chained(df: pd.DataFrame, key_cols: list[str], val: str) -> pd.Series:
        days = sorted(df["day"].unique())
        level, out = 100.0, {}
        if days:
            out[days[0]] = 100.0
        for prev, cur in pairwise(days):
            a = df[df["day"] == prev].set_index(key_cols)[val]
            b = df[df["day"] == cur].set_index(key_cols)[val]
            common = a.index.intersection(b.index)
            rel = float(np.exp(np.mean(np.log(b[common] / a[common])))) if len(common) else 1.0
            level *= rel
            out[cur] = round(level, 2)
        return pd.Series(out)

    filing = chained(rungs, ["carrier", "route", "rbd"], "rung_value")
    market = chained(active, ["carrier", "route", "flight_no", "departure_date"], "paid_price")
    out = pd.DataFrame({"filing_index": filing, "market_index": market}).dropna()
    out["availability_pressure_index"] = (
        out["market_index"] / out["filing_index"] * 100
    ).round(2)
    events = classify_days(quotes)
    fee_days = (
        set(events.loc[events["event"] == "EXTERNAL_FEE_CHANGE", "day"])
        if not events.empty
        else set()
    )
    out["external_fee_change"] = out.index.to_series().isin(fee_days)
    out["availability_status"] = np.where(
        out["external_fee_change"],
        "EXTERNAL_FEE_MOVEMENT_PRESENT",
        "AVAILABILITY_PRESSURE_PROXY",
    )
    return out.rename_axis("day").reset_index()
