import math

import pandas as pd
import pytest

from backend.src.indicators.volatility import calculate_adr, calculate_adr_ratio


def test_adr_golden_fixture():
    high = pd.Series([11, 12, 13], dtype=float)
    low = pd.Series([10, 10, 10], dtype=float)

    result = calculate_adr(high, low, length=2)

    assert math.isnan(result.iloc[0])
    assert result.iloc[1] == pytest.approx(0.15)
    assert result.iloc[2] == pytest.approx(0.25)


def test_adr_ratio_golden_fixture():
    high = pd.Series([11, 12, 13, 14, 15], dtype=float)
    low = pd.Series([10, 10, 10, 10, 10], dtype=float)

    result = calculate_adr_ratio(high, low, recent_length=2, prior_length=2)

    assert result.iloc[3] == pytest.approx(0.35 / 0.15)
    assert result.iloc[4] == pytest.approx(0.45 / 0.25)
