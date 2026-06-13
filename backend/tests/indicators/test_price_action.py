import math

import pandas as pd

from backend.src.indicators.price_action import calculate_chandelier_exit_long, calculate_n_day_high, calculate_n_day_low


def test_n_day_high_and_low_golden_fixture():
    high = pd.Series([1, 3, 2, 5, 4], dtype=float)
    low = pd.Series([1, 2, 1, 4, 3], dtype=float)

    highs = calculate_n_day_high(high, length=3)
    lows = calculate_n_day_low(low, length=3)

    assert math.isnan(highs.iloc[0])
    assert math.isnan(lows.iloc[1])
    assert highs.iloc[2:].tolist() == [3.0, 5.0, 5.0]
    assert lows.iloc[2:].tolist() == [1.0, 1.0, 1.0]


def test_chandelier_exit_golden_fixture():
    high = pd.Series([10, 12, 11, 15], dtype=float)
    atr = pd.Series([1, 1, 2, 2], dtype=float)

    result = calculate_chandelier_exit_long(high, atr, length=3, multiplier=2)

    assert math.isnan(result.iloc[0])
    assert result.iloc[2] == 8.0
    assert result.iloc[3] == 11.0
