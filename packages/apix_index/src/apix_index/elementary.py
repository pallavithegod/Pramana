"""Elementary (cell-level) index formulas over matched products.

A "product" here is the stratified tuple (route, carrier, cabin, lead-time bucket)
— the elementary cell of the whole system (PLAN §3.1). MVP ships Jevons and
Törnqvist bilaterals over matched samples; GEKS-T, splice, BCWFI, PRISM and the
nowcast build on these in week 2-3.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def matched_frame(df: pd.DataFrame, s: str, t: str) -> pd.DataFrame:
    """Matched-model sample between two periods.

    df columns: product_id, period, price. Returns one row per product present
    in BOTH periods with columns price_s, price_t.
    """
    wide = (
        df[df["period"].isin([s, t])]
        .pivot_table(index="product_id", columns="period", values="price", aggfunc="mean")
        .dropna()
    )
    if wide.empty:
        raise ValueError(f"no matched products between {s!r} and {t!r}")
    return wide.rename(columns={s: "price_s", t: "price_t"})


def jevons(df: pd.DataFrame, s: str, t: str) -> float:
    """Unweighted geometric-mean index P(s,t). The naive-team baseline."""
    m = matched_frame(df, s, t)
    return float(np.exp(np.mean(np.log(m["price_t"] / m["price_s"]))))


def tornqvist(df: pd.DataFrame, s: str, t: str, weights: pd.Series | None = None) -> float:
    """Törnqvist bilateral: ln P = Σ ½(w_s + w_t) ln(p_t/p_s).

    weights: pseudo-expenditure weights per product_id (BCWFI supplies
    DGCA-seat-share × booking-density). None → equal weights (reduces to Jevons).
    """
    m = matched_frame(df, s, t)
    if weights is None:
        w = pd.Series(1.0, index=m.index)
    else:
        w = weights.reindex(m.index).fillna(0.0)
        if w.sum() <= 0:
            raise ValueError("weights sum to zero over the matched sample")
    w = w / w.sum()
    return float(np.exp(np.sum(w * np.log(m["price_t"] / m["price_s"]))))
