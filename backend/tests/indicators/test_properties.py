import pandas as pd
from hypothesis import given, strategies as st

from backend.src.indicators.moving_averages import calculate_sma
from backend.src.indicators.volatility import calculate_atr


@given(st.floats(min_value=1, max_value=1_000, allow_nan=False, allow_infinity=False))
def test_sma_of_constant_series_is_constant(value: float):
    result = calculate_sma(pd.Series([value] * 10, dtype=float), length=5)

    assert all(item == value for item in result.dropna())


@given(st.lists(st.floats(min_value=1, max_value=1_000, allow_nan=False, allow_infinity=False), min_size=20, max_size=40))
def test_atr_is_non_negative(prices: list[float]):
    close = pd.Series(prices, dtype=float)
    high = close + 1
    low = close - 1

    result = calculate_atr(high, low, close, length=14)

    assert all(item >= 0 for item in result.dropna())
