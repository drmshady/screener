import math

import pandas as pd

from backend.src.indicators.moving_averages import calculate_sma


def test_sma_golden_fixture():
    result = calculate_sma(pd.Series([1, 2, 3, 4, 5], dtype=float), length=3)

    assert math.isnan(result.iloc[0])
    assert math.isnan(result.iloc[1])
    assert result.iloc[2:].tolist() == [2.0, 3.0, 4.0]
