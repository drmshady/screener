from datetime import date, timedelta

import pandas as pd

from backend.src.indicators.base_pattern import classify_base


def _series(values: list[float]) -> pd.Series:
    index = pd.date_range(date(2025, 1, 1), periods=len(values), freq="B")
    return pd.Series(values, index=index, dtype=float)


def test_flat_base_fixture_reports_pivot_length_and_depth():
    prices = _series([100, 101, 99, 102, 100, 101, 103, 101, 102, 100] * 3)

    result = classify_base(prices, prices - 2, prices)

    assert result.detected is True
    assert result.base_type == "flat"
    assert result.pivot == 103
    assert 5.5 <= result.base_length_weeks <= 6.5
    assert result.base_depth == (103 - 97) / 103


def test_cup_with_handle_uses_handle_high_as_pivot():
    close = _series(
        [100, 98, 94, 90, 86, 82, 80, 82, 86, 90, 94, 98, 100]
        + [99, 98, 97, 98, 99]
        + [100, 101, 102]
    )
    high = close + 1
    low = close - 1

    result = classify_base(high, low, close)

    assert result.detected is True
    assert result.base_type == "cup_with_handle"
    assert result.handle_high == 100
    assert result.pivot == 100
    assert result.base_length_weeks >= 4


def test_double_bottom_fixture_reports_interior_peak_pivot():
    close = _series(
        [100, 96, 90, 88, 91, 95, 98, 96, 92, 89, 91, 96, 99, 100]
        + [101, 102, 103, 104, 105, 106, 107]
    )
    high = close + 1
    low = close - 1

    result = classify_base(high, low, close)

    assert result.detected is True
    assert result.base_type == "double_bottom"
    assert result.pivot == 99


def test_insufficient_or_unclassifiable_history_is_not_fabricated():
    close = _series([100, 112, 91, 130, 80, 145, 70, 160])

    result = classify_base(close + 1, close - 1, close)

    assert result.detected is False
    assert result.base_type == "none"
    assert result.pivot is None


def test_most_recent_qualifying_base_wins():
    old_base = [50, 51, 49, 52, 50] * 6
    trend = [55, 58, 60, 62, 64]
    recent_base = [70, 71, 69, 72, 70] * 6
    close = _series(old_base + trend + recent_base)

    result = classify_base(close + 1, close - 1, close)

    assert result.detected is True
    assert result.base_type == "flat"
    assert result.pivot == 73
    assert result.base_start >= close.index[len(old_base)]
