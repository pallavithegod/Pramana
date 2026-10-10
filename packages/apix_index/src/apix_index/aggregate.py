"""Daily APIx: matched-model indices and production GEKS-T aggregation.

Cell = (route, lead-time bucket). Product inside a cell = (carrier, flight_no)
tracked at the same lead bucket across collection days — the "flight relative".
Price per product-day = cheapest quote (MoSPI CPI-2024 airfare spec).

The fixed-base implementation remains as a documented baseline. The production
path uses rolling GEKS-T with mean splice and BCWFI-style weights.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pandas as pd

from .multilateral import GEKS_WINDOW_DAYS, rolling_geks

LEAD_BUCKETS = np.array([1, 7, 15, 30, 45])


def lead_bucket(lead_days: pd.Series) -> pd.Series:
    """Snap observed days-to-departure to the nearest advance window."""
    idx = np.abs(lead_days.to_numpy()[:, None] - LEAD_BUCKETS[None, :]).argmin(axis=1)
    return pd.Series(LEAD_BUCKETS[idx], index=lead_days.index)


def prepare(quotes: pd.DataFrame) -> pd.DataFrame:
    """quotes: raw rows (origin, dest, carrier, flight_no, lead_days, total_fare,
    collected_at). Returns one price per (day, cell, product): the cheapest quote."""
    df = quotes.copy()
    df["day"] = pd.to_datetime(df["collected_at"], format="ISO8601").dt.date
    df["route"] = df["origin"] + "-" + df["dest"]
    df["bucket"] = lead_bucket(df["lead_days"])
    df["product_id"] = df["carrier"] + "|" + df["flight_no"].fillna("NA")
    return (
        df.groupby(["day", "route", "bucket", "product_id"], as_index=False)["total_fare"]
        .min()
        .rename(columns={"total_fare": "price"})
    )


def cell_indices(prices: pd.DataFrame) -> pd.DataFrame:
    """Fixed-base matched Jevons per (route, bucket): P(day) vs that cell's first day.
    Only products present on BOTH days enter (matched model)."""
    out = []
    for (route, bucket), cell in prices.groupby(["route", "bucket"]):
        base_day = cell["day"].min()
        base = cell[cell["day"] == base_day].set_index("product_id")["price"]
        for day, snap in cell.groupby("day"):
            cur = snap.set_index("product_id")["price"]
            common = base.index.intersection(cur.index)
            if common.empty:
                continue
            rel = np.log(cur[common] / base[common])
            out.append(
                {
                    "day": day, "route": route, "bucket": int(bucket),
                    "index": float(np.exp(rel.mean()) * 100.0),
                    "n_matched": len(common),
                }
            )
    return pd.DataFrame(out)


def compute_apix(
    quotes: pd.DataFrame, route_weights: dict[str, float] | None = None
) -> pd.DataFrame:
    """Headline daily APIx (base 100 = first collection day).

    route_weights: {"DEL-BOM": 0.0414, ...} from DGCA traffic (basket file);
    None → equal route weights. Lead buckets equally weighted in the MVP.
    """
    prices = prepare(quotes)
    cells = cell_indices(prices)
    if cells.empty:
        return pd.DataFrame(columns=["day", "apix", "n_cells", "n_matched"])

    if route_weights:
        cells["w"] = cells["route"].map(route_weights).fillna(0.0)
    else:
        cells["w"] = 1.0

    def agg(day_cells: pd.DataFrame) -> pd.Series:
        w = day_cells["w"].to_numpy()
        if w.sum() <= 0:
            w = np.ones(len(day_cells))
        w = w / w.sum()
        return pd.Series(
            {
                "apix": float(np.exp(np.sum(w * np.log(day_cells["index"] / 100.0))) * 100.0),
                "n_cells": len(day_cells),
                "n_matched": int(day_cells["n_matched"].sum()),
            }
        )

    daily = cells.groupby("day").apply(agg, include_groups=False).reset_index()
    daily["inflation_dod"] = daily["apix"].pct_change().mul(100).round(4)
    return daily


# --------------------------------------------------------------------------- #
# v2 engine: quality gates → per-cell rolling GEKS-Törnqvist → BCWFI weights
# --------------------------------------------------------------------------- #

# BCWFI provisional booking-density weights f(τ) per lead bucket (PLAN §3.2).
# These expert-supported MVP values emphasize near windows but are not estimated
# transaction shares. They require calibration against representative booking
# data before official use. Sums to 1.
BOOKING_DENSITY: dict[int, float] = {1: 0.35, 7: 0.25, 15: 0.18, 30: 0.13, 45: 0.09}


def compute_apix_v2(
    quotes: pd.DataFrame,
    route_weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Headline daily APIx, v2 (2 Sep 2026 upgrade).

    Fixes the product-churn artifact of v1 (fixed-base matched cells jumped when
    a source's product mix changed): each (route × lead-bucket) cell now runs a
    rolling-window GEKS-Törnqvist (see multilateral.py) — day pairs connect
    through every link day, so products entering/leaving reweight smoothly and
    the series is drift-free and revision-free (mean splice) by construction.
    Cell weights = DGCA route share × booking-density f(τ)  (= BCWFI).
    Same output shape as compute_apix.
    """
    from .gates import apply_gates
    clean, _rejected = apply_gates(quotes)
    prices = prepare(clean)
    prices = prices.rename(columns={"day": "period"})
    prices["period"] = prices["period"].astype(str)

    cell_series = []
    for (route, bucket), cell in prices.groupby(["route", "bucket"]):
        series = rolling_geks(cell, window=GEKS_WINDOW_DAYS)
        n_by_day = cell.groupby("period")["product_id"].nunique()
        for period, level in series.items():
            if np.isfinite(level):
                cell_series.append(
                    {
                        "day": period,
                        "route": route,
                        "bucket": int(bucket),
                        "index": level,
                        "n_matched": int(n_by_day.get(period, 0)),
                    }
                )
    cells = pd.DataFrame(cell_series)
    if cells.empty:
        return pd.DataFrame(columns=["day", "apix", "n_cells", "n_matched", "inflation_dod"])

    rw = (
        cells["route"].map(route_weights).fillna(0.0)
        if route_weights
        else pd.Series(1.0, index=cells.index)
    )
    cells["w"] = rw * cells["bucket"].map(BOOKING_DENSITY).fillna(0.0)

    # CHAINED aggregation (8 Sep 2026, replaces weighted geomean of LEVELS):
    # the headline compounds each day's weighted mean of cell LOG-CHANGES, over
    # cells observed on both the current and the previous day. A cell entering
    # the basket contributes nothing on its first day and only its real
    # movements afterwards — so expanding the route basket (or a source
    # appearing/vanishing) can never print a fake level jump. This is the
    # standard NSO treatment for introducing new items into a fixed-weight
    # index. The level-based aggregate jumped +3.2% mechanically in a top-12 →
    # top-20 dry run; under chaining the seam is invisible.
    cells["logix"] = np.log(cells["index"])
    wide_ix = cells.pivot_table(index="day", columns=["route", "bucket"], values="logix")
    wide_w = cells.pivot_table(index="day", columns=["route", "bucket"], values="w")
    wide_n = cells.pivot_table(index="day", columns=["route", "bucket"], values="n_matched")
    days = sorted(wide_ix.index)

    rows = []
    level = 100.0
    first = days[0]
    rows.append(
        {
            "day": first,
            "apix": 100.0,
            "n_cells": int(wide_ix.loc[first].notna().sum()),
            "n_matched": int(wide_n.loc[first].fillna(0).sum()),
        }
    )
    for prev, cur in pairwise(days):
        dlog = wide_ix.loc[cur] - wide_ix.loc[prev]  # NaN unless cell has BOTH days
        live = dlog.notna()
        if live.any():
            w = wide_w.loc[cur].where(live).fillna(0.0).to_numpy()
            if w.sum() <= 0:
                w = live.to_numpy(dtype=float)
            w = w / w.sum()
            level *= float(np.exp(np.nansum(w * dlog.to_numpy())))
        rows.append(
            {
                "day": cur,
                "apix": round(level, 4),
                "n_cells": int(live.sum()),
                "n_matched": int(wide_n.loc[cur].fillna(0).sum()),
            }
        )
    daily = pd.DataFrame(rows)
    daily["apix"] = daily["apix"].round(2)
    daily["inflation_dod"] = daily["apix"].pct_change().mul(100).round(4)
    return daily
