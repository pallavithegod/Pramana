import numpy as np
import pandas as pd
import pytest
from apix_index import jevons, tornqvist


@pytest.fixture
def two_periods() -> pd.DataFrame:
    # product A doubles, product B halves; C exists only in t (must be dropped by matching)
    return pd.DataFrame(
        {
            "product_id": ["A", "B", "A", "B", "C"],
            "period": ["s", "s", "t", "t", "t"],
            "price": [100.0, 200.0, 200.0, 100.0, 999.0],
        }
    )


def test_jevons_geometric_mean(two_periods):
    # relatives: 2.0 and 0.5 → geometric mean = 1.0
    assert jevons(two_periods, "s", "t") == pytest.approx(1.0)


def test_tornqvist_equal_weights_matches_jevons(two_periods):
    assert tornqvist(two_periods, "s", "t") == pytest.approx(jevons(two_periods, "s", "t"))


def test_tornqvist_weighted(two_periods):
    w = pd.Series({"A": 3.0, "B": 1.0})  # w_A=0.75, w_B=0.25
    expected = np.exp(0.75 * np.log(2.0) + 0.25 * np.log(0.5))
    assert tornqvist(two_periods, "s", "t", w) == pytest.approx(expected)


def test_unmatched_product_ignored(two_periods):
    # C has no period-s price; matching must silently drop it (imputation comes later)
    assert jevons(two_periods, "s", "t") == pytest.approx(1.0)


def test_no_overlap_raises():
    df = pd.DataFrame(
        {"product_id": ["A", "B"], "period": ["s", "t"], "price": [1.0, 2.0]}
    )
    with pytest.raises(ValueError):
        jevons(df, "s", "t")
