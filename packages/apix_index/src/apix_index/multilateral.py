"""Rolling-window GEKS-Törnqvist with mean splice (PLAN §3.1).

Why GEKS-T (the churn fix): a fixed-base matched index breaks when products
enter/leave — exactly what happened 2 Sep 2026 when Akasa's calendar products
vanished and per-RBD flight products began (headline jumped +10.8% partly on
composition). GEKS-T compares every pair of days through EVERY other day as a
link, so a product observed on (s,l) and (l,t) still connects s→t even if it is
missing on s or t directly. Transitivity removes chain drift by construction
(IMF/ILO CPI Manual 2020 ch.10; ONS 2023 applies it to dynamic web data).

Splice: indices inside one window are internally consistent, but a rolling
window re-estimates history. We publish with a MEAN SPLICE on the full window
(geometric mean of all candidate splice paths) — no revisions, drift-free
extension (Ivancic–Diewert–Fox; ONS default).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .elementary import tornqvist

GEKS_WINDOW_DAYS = 14
# Backward-compatible name for callers of the mathematical primitive. The
# production APIx path imports GEKS_WINDOW_DAYS directly and cannot override it.
DEFAULT_WINDOW = GEKS_WINDOW_DAYS


def _bilateral(df: pd.DataFrame, s: str, t: str, weights: pd.Series | None) -> float:
    """Törnqvist P(s,t); NaN when no matched products (GEKS just skips the link)."""
    if s == t:
        return 1.0
    try:
        return tornqvist(df, s, t, weights)
    except ValueError:
        return float("nan")


def geks_tornqvist(
    prices: pd.DataFrame, weights: pd.Series | None = None
) -> pd.Series:
    """GEKS-T over one window.

    prices: columns (period, product_id, price) — period sortable (ISO dates).
    Returns index level per period, first period = 100. GEKS(s,t) =
    geomean_l [P(s,l)·P(l,t)] over links l with both legs defined.
    """
    periods = sorted(prices["period"].unique())
    if not periods:
        return pd.Series(dtype=float)
    base = periods[0]

    # Build the product-by-period matrix once per GEKS window.  The previous
    # implementation called ``tornqvist`` for every period pair, and each call
    # rebuilt the same pivot table from the long panel.  That is mathematically
    # correct but made a 30k-row hosted snapshot take more than 90 seconds.
    # Pairwise matching and weight normalisation below are identical to
    # elementary.tornqvist; only the repeated dataframe work is removed.
    wide = prices.pivot_table(
        index="product_id", columns="period", values="price", aggfunc="mean"
    ).reindex(columns=periods)
    log_prices = np.log(wide.to_numpy(dtype=float))
    period_position = {period: i for i, period in enumerate(periods)}
    product_weights = (
        None
        if weights is None
        else weights.reindex(wide.index).fillna(0.0).to_numpy(dtype=float)
    )

    def matrix_bilateral(s: str, t: str) -> float:
        price_s = log_prices[:, period_position[s]]
        price_t = log_prices[:, period_position[t]]
        matched = np.isfinite(price_s) & np.isfinite(price_t)
        if not matched.any():
            return float("nan")
        log_relative = price_t[matched] - price_s[matched]
        if product_weights is None:
            return float(np.exp(log_relative.mean()))
        else:
            pair_weights = product_weights[matched]
            total_weight = pair_weights.sum()
            if total_weight <= 0:
                return float("nan")
            pair_weights = pair_weights / total_weight
            return float(np.exp(np.sum(pair_weights * log_relative)))

    P: dict[tuple[str, str], float] = {}
    for a in periods:
        for b in periods:
            if a < b:
                P[(a, b)] = matrix_bilateral(a, b)

    def bil(a: str, b: str) -> float:
        if a == b:
            return 1.0
        return P[(a, b)] if a < b else (1.0 / P[(b, a)] if P[(b, a)] else float("nan"))

    out = {}
    for t in periods:
        links = [
            np.log(bil(base, l) * bil(l, t))
            for l in periods
            if np.isfinite(bil(base, l)) and np.isfinite(bil(l, t))
        ]
        out[t] = float(np.exp(np.mean(links)) * 100.0) if links else float("nan")
    return pd.Series(out).sort_index()


def rolling_geks(
    prices: pd.DataFrame,
    window: int = DEFAULT_WINDOW,
    weights: pd.Series | None = None,
) -> pd.Series:
    """Published series: full GEKS-T while ≤ window periods exist, then extend
    one period at a time with a mean splice (published values never revised)."""
    periods = sorted(prices["period"].unique())
    if len(periods) <= window:
        return geks_tornqvist(prices, weights)

    published = geks_tornqvist(
        prices[prices["period"].isin(periods[:window])], weights
    )
    for i in range(window, len(periods)):
        win = periods[i - window + 1 : i + 1]
        w_idx = geks_tornqvist(prices[prices["period"].isin(win)], weights)
        new_p = periods[i]
        # mean splice: geometric mean over all overlap periods of
        # published(o) · [win(new)/win(o)]
        candidates = [
            np.log(published[o] * w_idx[new_p] / w_idx[o])
            for o in win[:-1]
            if o in published.index and np.isfinite(w_idx.get(o, np.nan)) and w_idx[o] > 0
            and np.isfinite(published[o]) and np.isfinite(w_idx[new_p])
        ]
        published[new_p] = float(np.exp(np.mean(candidates))) if candidates else float("nan")
    return published.sort_index()
