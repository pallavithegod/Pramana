"""Volatility-aware quality gates (PLAN §3.4 — "Turbulence-Adjusted HB gate", v1).

Standard NSO outlier rules (fixed Tukey fences) reject legitimate airfare
dynamics: a T+1 fare 3× the T+45 fare is normal, and volatile routes swing more
than trunk routes. So control limits are computed PER STRATUM (route × lead
bucket) with a robust dispersion estimate, and every rejection carries a reason
code — auditability is the point, not just cleaning.

v1 rule (documented, deterministic):
  - stratum = (route, lead bucket); statistic = log(total_fare)
  - centre  = stratum median, spread = MAD (scaled, 1.4826×)
  - |modified z| > Z_REJECT            → reject  code "MZ_GT_5"
  - fare <= 0 or NaN                   → reject  code "NONPOSITIVE"
  - stratum too small (< MIN_N quotes) → keep    (never reject on thin evidence)
The spread naturally widens on volatile strata — that IS the turbulence
adjustment; explicit covariate-conditioned bands land with more panel data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

Z_REJECT = 5.0
MIN_N = 5
_MAD_SCALE = 1.4826


def apply_gates(quotes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split quotes into (clean, rejected). Expects columns origin, dest,
    lead_days, total_fare. Rejected rows gain a `reject_code` column."""
    df = quotes.copy()
    bad_value = ~np.isfinite(df["total_fare"]) | (df["total_fare"] <= 0)
    rejects = [df[bad_value].assign(reject_code="NONPOSITIVE")]
    df = df[~bad_value].copy()

    df["_stratum"] = df["origin"] + "-" + df["dest"] + "|" + df["lead_days"].astype(str)
    logp = np.log(df["total_fare"])
    med = logp.groupby(df["_stratum"]).transform("median")
    mad = (logp - med).abs().groupby(df["_stratum"]).transform("median") * _MAD_SCALE
    n = df.groupby("_stratum")["total_fare"].transform("size")

    with np.errstate(divide="ignore", invalid="ignore"):
        mz = (logp - med) / mad
    outlier = (n >= MIN_N) & mad.gt(0) & mz.abs().gt(Z_REJECT)

    rejects.append(df[outlier].assign(reject_code="MZ_GT_5").drop(columns="_stratum"))
    clean = df[~outlier].drop(columns="_stratum")
    rejected = pd.concat(rejects, ignore_index=True) if any(len(r) for r in rejects) else (
        df.iloc[0:0].assign(reject_code=pd.Series(dtype=str))
    )
    return clean, rejected
