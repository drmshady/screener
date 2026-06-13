import math

import pandas as pd
import pytest

from backend.src.indicators.moving_averages import calculate_ema


def test_ema_golden_fixture_adjust_false_span_three():
    result = calculate_ema(pd.Series([1, 2, 3, 4, 5], dtype=float), length=3)

    assert math.isnan(result.iloc[0])
    assert math.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(2.25)
    assert result.iloc[3] == pytest.approx(3.125)
    assert result.iloc[4] == pytest.approx(4.0625)
