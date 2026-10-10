"""Wrap the preserved Kalman primitive without inventing economic comparability."""

import json
import math
from datetime import datetime

import numpy as np
from apix_index.nowcast import local_level_filter


def run_prism_filter(raw_price_data: dict | str) -> dict:
    """Filter normalized SerpApi time series; never smooth unlike products together.

    Input: a Pramana tool's JSON result containing series[{product_id,currency,points}].
    Each point is {observed_at,value,currency}. At least three distinct timestamps
    for the same specification are required. A single search is a cross-section,
    not a price history. Kalman outputs are estimates, not proven true prices.
    """
    data = json.loads(raw_price_data) if isinstance(raw_price_data, str) else raw_price_data
    if not isinstance(data, dict):
        raise TypeError("Expected a JSON object containing normalized series")
    series = data.get("series", [])
    if not isinstance(series, list) or len(series) > 40:
        raise ValueError("Supply at most 40 comparable product series")
    out = []
    for sample in series:
        currency = sample.get("currency")
        pid = sample.get("product_id")
        if not pid or not currency:
            raise ValueError("Each series needs product_id and currency")
        points = sample.get("points", [])
        if len(points) > 365:
            raise ValueError("At most 365 observations per series")
        by_time = {}
        for point in points:
            timestamp = datetime.fromisoformat(point["observed_at"])
            if timestamp.tzinfo is None:
                raise ValueError("Observation timestamps must include timezone")
            value = float(point["value"])
            if not math.isfinite(value) or value <= 0 or point.get("currency") != currency:
                raise ValueError("Prices must be positive, finite and in one currency")
            if timestamp in by_time and by_time[timestamp]["value"] != value:
                raise ValueError("Conflicting prices at the same timestamp")
            by_time[timestamp] = {**point, "value": value}
        points = [by_time[t] for t in sorted(by_time)]
        if len(points) < 3:
            out.append(
                {
                    "product_id": pid,
                    "status": "insufficient_history",
                    "n_observations": len(points),
                    "minimum_required": 3,
                    "smoothed_baseline": None,
                    "currency": currency,
                }
            )
            continue
        values = np.array([p["value"] for p in points], dtype=float)
        # Preserve original primitive; expose the exact parameters used for reproducibility.
        variance = float(np.var(np.diff(values)))
        q = r = max(variance / 3.0, 1e-6)
        mu, posterior = local_level_filter(values, q=q, r=r)
        predictive = posterior[-2] + q + r
        innovation = float(values[-1] - mu[-2])
        score = innovation / math.sqrt(predictive)
        out.append(
            {
                "product_id": pid,
                "title": sample.get("title"),
                "status": "ok",
                "currency": currency,
                "n_observations": len(points),
                "raw_latest": float(values[-1]),
                "smoothed_baseline": float(mu[-1]),
                "posterior_variance": float(posterior[-1]),
                "q": q,
                "r": r,
                "innovation_z": score,
                "anomaly": abs(score) >= 3,
                "band_low": float(mu[-1] - 1.96 * np.sqrt(posterior[-1])),
                "band_high": float(mu[-1] + 1.96 * np.sqrt(posterior[-1])),
                "trajectory": [
                    {
                        "observed_at": p["observed_at"],
                        "raw": float(y),
                        "baseline": float(m),
                        "variance": float(v),
                    }
                    for p, y, m, v in zip(points, values, mu, posterior, strict=True)
                ],
            }
        )
    return {
        "status": "ok" if any(s["status"] == "ok" for s in out) else "insufficient_history",
        "method": "pramana-kalman-local-level-v1",
        "series": out,
        "interpretation": "Smoothed latent baseline estimate, not a proven true price. "
        "Irregular captures are observation steps, not equally spaced calendar days. "
        "Parameters are fit to supplied history; bands are conditional model bands.",
    }
