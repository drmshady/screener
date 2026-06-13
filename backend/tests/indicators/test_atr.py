import math

import pandas as pd
import pytest

from backend.src.indicators.volatility import calculate_atr


def test_atr_wilder_golden_fixture():
    high = pd.Series([10, 12, 13, 15], dtype=float)
    low = pd.Series([9, 10, 12, 14], dtype=float)
    close = pd.Series([9.5, 11, 12.5, 14.5], dtype=float)

    result = calculate_atr(high, low, close, length=3)

    assert math.isnan(result.iloc[0])
    assert math.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(1.8333333333)
    assert result.iloc[3] == pytest.approx(2.0555555556)
