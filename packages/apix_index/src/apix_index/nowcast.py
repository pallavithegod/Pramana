"""Kalman nowcast of the monthly CPI airfare item (PLAN §3.3), v1 scaffold.

Local-level state-space model on the daily headline index:
    state:  mu_t = mu_{t-1} + eta,   eta ~ N(0, q)
    obs:    y_t  = mu_t + eps,       eps ~ N(0, r)
Filtered mu_t + its variance give a running month-average estimate with a
confidence band — "on the 5th we predict what MoSPI prints on the 12th".
Runs only when enough daily observations exist (MIN_DAYS); we do not render
synthetic curves before that.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MIN_DAYS = 14


def local_level_filter(
    y: np.ndarray, q: float | None = None, r: float | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Kalman filter for the local-level model. Returns (mu, var) per day.
    Default variances from first differences (method-of-moments start)."""
    dy = np.diff(y)
    var_dy = float(np.var(dy)) if len(dy) > 1 else 1.0
    q = q if q is not None else max(var_dy / 3.0, 1e-6)
    r = r if r is not None else max(var_dy / 3.0, 1e-6)

    n = len(y)
    mu = np.zeros(n)
    P = np.zeros(n)
    mu[0], P[0] = y[0], r
    for t in range(1, n):
        mu_pred, P_pred = mu[t - 1], P[t - 1] + q
        K = P_pred / (P_pred + r)
        mu[t] = mu_pred + K * (y[t] - mu_pred)
        P[t] = (1 - K) * P_pred
    return mu, P


def nowcast_month(daily: pd.DataFrame) -> dict | None:
    """daily: columns (date, index). Returns the nowcast for the CURRENT month
    of `date` max, or None when the panel is too short (< MIN_DAYS)."""
    if len(daily) < MIN_DAYS:
        return None
    daily = daily.sort_values("date")
    y = daily["index"].to_numpy(dtype=float)
    mu, P = local_level_filter(y)
    month = daily["date"].iloc[-1][:7]
    in_month = daily["date"].str.startswith(month)
    # month estimate = mean of filtered levels over observed days + current
    # filtered level carried through remaining days
    obs = mu[in_month.to_numpy()]
    level, var = mu[-1], P[-1]
    days_in_month = pd.Period(month).days_in_month
    n_obs = int(in_month.sum())
    est = float((obs.sum() + level * (days_in_month - n_obs)) / days_in_month)
    band = float(1.96 * np.sqrt(var))
    return {
        "month": month,
        "nowcast_index": round(est, 2),
        "band_low": round(est - band, 2),
        "band_high": round(est + band, 2),
        "n_days_observed": n_obs,
        "days_in_month": days_in_month,
    }
