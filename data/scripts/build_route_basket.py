"""Build the route basket + BCWFI route weights from DGCA TABLE 5.01
(city-pair-wise scheduled domestic passenger traffic, FY 2024-25).

Outputs:
  data/route_weights.csv   — all 800+ pairs, bidirectional pax, seat-share weight s_r
  data/route_basket.yaml   — top-N IATA-mapped pairs the collectors actually run

Source file lives OUTSIDE the repo (extractions folder) — pass --src to override.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SRC = (
    REPO_ROOT.parent / "extractions" / "TABLE 5.01 (INDIAN CITY-WISE PASSENGER TRAFFIC).xlsx"
)

# City → primary IATA (top domestic cities; extend as basket grows)
IATA = {
    "DELHI": "DEL", "MUMBAI": "BOM", "BENGALURU": "BLR", "BANGALORE": "BLR",
    "HYDERABAD": "HYD", "CHENNAI": "MAA", "KOLKATA": "CCU", "AHMEDABAD": "AMD",
    "PUNE": "PNQ", "GOA": "GOI", "DABOLIM": "GOI", "MOPA": "GOX", "KOCHI": "COK", "COCHIN": "COK", "JAIPUR": "JAI",
    "LUCKNOW": "LKO", "GUWAHATI": "GAU", "PATNA": "PAT", "SRINAGAR": "SXR",
    "COIMBATORE": "CJB", "THIRUVANANTHAPURAM": "TRV", "BHUBANESWAR": "BBI",
    "VARANASI": "VNS", "INDORE": "IDR", "NAGPUR": "NAG", "CHANDIGARH": "IXC",
    "RANCHI": "IXR", "VISAKHAPATNAM": "VTZ", "AMRITSAR": "ATQ", "BAGDOGRA": "IXB",
    "UDAIPUR": "UDR", "JAMMU": "IXJ", "MANGALURU": "IXE", "MANGALORE": "IXE",
    "KOZHIKODE": "CCJ", "CALICUT": "CCJ", "PORT BLAIR": "IXZ", "RAIPUR": "RPR",
    "DEHRADUN": "DED", "LEH": "IXL", "MADURAI": "IXM", "SURAT": "STV",
    "BHOPAL": "BHO", "VADODARA": "BDQ", "TIRUCHIRAPPALLI": "TRZ", "AGARTALA": "IXA",
    "IMPHAL": "IMF", "JODHPUR": "JDH", "PRAYAGRAJ": "IXD", "VIJAYAWADA": "VGA",
}


def norm(city: str) -> str:
    return str(city).strip().upper()


def main(src: Path, top_n: int) -> None:
    raw = pd.read_excel(src, header=None)
    # locate header row: contains "CITY 1"
    hdr = raw.index[raw.apply(lambda r: r.astype(str).str.contains("CITY 1").any(), axis=1)][0]
    df = pd.read_excel(src, header=hdr)
    df.columns = [str(c).strip().upper() for c in df.columns]
    c1 = next(c for c in df.columns if "CITY 1" in c)
    c2 = next(c for c in df.columns if "CITY 2" in c)
    pax_cols = [c for c in df.columns if "PASSENGERS" in c]
    df = df[[c1, c2, *pax_cols]].dropna(subset=[c1, c2])
    df = df[~df[c1].astype(str).str.contains("TOTAL|GRAND", case=False, na=False)]
    for c in pax_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["pax_total"] = df[pax_cols].sum(axis=1)
    df["city1"], df["city2"] = df[c1].map(norm), df[c2].map(norm)
    df = df[df["pax_total"] > 0]

    total = df["pax_total"].sum()
    df["weight_s_r"] = df["pax_total"] / total
    out = df[["city1", "city2", "pax_total", "weight_s_r"]].sort_values(
        "pax_total", ascending=False
    )
    out.to_csv(REPO_ROOT / "data" / "route_weights.csv", index=False)

    routes = []
    for _, r in out.iterrows():
        o, d = IATA.get(r["city1"]), IATA.get(r["city2"])
        if o and d and o != d:
            routes.append(
                {
                    "origin": o, "dest": d,
                    "city_pair": f"{r['city1'].title()}-{r['city2'].title()}",
                    "annual_pax": int(r["pax_total"]),
                    "weight": round(float(r["weight_s_r"]), 6),
                }
            )
        if len(routes) == top_n:
            break

    basket = {
        "source": "DGCA TABLE 5.01, city-pair domestic pax, FY 2024-25",
        "generated_by": "data/scripts/build_route_basket.py",
        "note": "weights = share of total domestic city-pair pax (BCWFI s_r numerator)",
        "routes": routes,
    }
    with open(REPO_ROOT / "data" / "route_basket.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(basket, f, sort_keys=False, allow_unicode=True)

    print(f"route_weights.csv: {len(out)} pairs, {total:,.0f} pax total")
    print(f"route_basket.yaml: top {len(routes)} IATA-mapped routes:")
    for rt in routes:
        print(f"  {rt['origin']}-{rt['dest']}  {rt['annual_pax']:>12,}  w={rt['weight']:.4f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--src", type=Path, default=DEFAULT_SRC)
    p.add_argument("--top-n", type=int, default=12)
    a = p.parse_args()
    main(a.src, a.top_n)
