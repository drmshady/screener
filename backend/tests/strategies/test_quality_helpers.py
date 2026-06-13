import pandas as pd

from backend.src.strategies._helpers.quality import (
    gross_profitability_mask,
    passes_quality_screen,
)


def test_gross_profitability_keeps_top_half_by_median():
    series = pd.Series([0.1, 0.2, 0.3, 0.4], index=["a", "b", "c", "d"])
    mask = gross_profitability_mask(series, min_percentile=0.5)
    # median of [0.1,0.2,0.3,0.4] = 0.25 -> keep 0.3 and 0.4
    assert mask.tolist() == [False, False, True, True]


def test_gross_profitability_missing_values_fail_gate():
    series = pd.Series([0.5, None, 0.4], index=["a", "b", "c"])
    mask = gross_profitability_mask(series, min_percentile=0.5)
    assert mask["b"] is False or mask["b"] == False  # NaN never passes
    assert mask["a"] == True


def test_gross_profitability_all_missing_returns_all_false():
    series = pd.Series([None, None], index=["a", "b"], dtype="float64")
    mask = gross_profitability_mask(series, min_percentile=0.5)
    assert mask.tolist() == [False, False]


def test_passes_quality_screen_rejects_high_leverage_and_negative_fcf():
    assert passes_quality_screen(0.5, 1_000_000, max_debt_equity=1.5) is True
    assert passes_quality_screen(2.0, 1_000_000, max_debt_equity=1.5) is False
    assert passes_quality_screen(0.5, -1, max_debt_equity=1.5) is False
