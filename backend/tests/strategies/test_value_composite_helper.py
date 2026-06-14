"""Unit tests for the cross-sectional value-composite helper (research D1/D4)."""
import pandas as pd
import pytest

from backend.src.strategies._helpers.value_composite import compute_value_composite

_YIELD_COLS = ["book_to_market", "earnings_yield", "cashflow_yield", "sales_yield"]


def _df():
    return pd.DataFrame(
        {
            "ticker": ["A", "B", "C"],
            "sector": ["Tech", "Tech", "Tech"],
            "book_to_market": [0.10, 0.20, 0.15],
            "earnings_yield": [0.05, 0.10, None],   # C missing
            "cashflow_yield": [0.04, 0.08, 0.06],
            "sales_yield": [0.9, 1.8, 1.2],
        }
    )


def test_cheaper_name_ranks_higher_global():
    out = compute_value_composite(_df(), within_sector=False)
    s = out.set_index("ticker")["value_composite"]
    # B is cheapest on every yield -> top composite; A is dearest -> lowest.
    assert s["B"] == pytest.approx(1.0)
    assert s["B"] > s["C"] > s["A"]


def test_metrics_count_tracks_available_yields():
    out = compute_value_composite(_df(), within_sector=False)
    counts = out.set_index("ticker")["value_metrics_count"]
    assert counts["A"] == 4
    assert counts["B"] == 4
    assert counts["C"] == 3  # earnings_yield missing


def test_partial_composite_is_mean_of_present_ranks():
    out = compute_value_composite(_df(), within_sector=False)
    c = out.set_index("ticker").loc["C"]
    # C present on bm/cf/sy; each is the middle value -> rank 2/3 of those columns.
    assert c["value_composite"] == pytest.approx(2.0 / 3.0)


def test_within_sector_ranks_per_group():
    df = _df()
    df.loc[2, "sector"] = "Health"  # C alone in its sector -> rank 1.0 on each yield
    out = compute_value_composite(df, within_sector=True)
    s = out.set_index("ticker")["value_composite"]
    assert s["C"] == pytest.approx(1.0)  # only member of Health
    # Within Tech, B still beats A.
    assert s["B"] > s["A"]


def test_no_yield_columns_yields_empty_composite():
    df = pd.DataFrame({"ticker": ["A"], "sector": ["Tech"]})
    out = compute_value_composite(df, within_sector=False)
    assert out.loc[0, "value_composite"] != out.loc[0, "value_composite"]  # NaN
    assert out.loc[0, "value_metrics_count"] == 0
