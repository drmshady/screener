import pandas as pd

from backend.src.indicators.price_action import calculate_chandelier_exit_long


def test_chandelier_exit_tracks_highest_high_minus_atr_multiple():
    high = pd.Series([20, 21, 19, 24, 23], dtype=float)
    atr = pd.Series([1, 1, 1.5, 2, 2], dtype=float)

    result = calculate_chandelier_exit_long(high, atr, length=3, multiplier=3)

    assert result.iloc[2] == 16.5
    assert result.iloc[3] == 18.0
    assert result.iloc[4] == 18.0
