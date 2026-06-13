import math

import pandas as pd
import pytest

from backend.src.indicators.momentum import calculate_12_1_return, calculate_n_month_return, sector_relative_rank


def test_n_month_return_golden_fixture():
    close = pd.Series(range(1, 44), dtype=float)

    result = calculate_n_month_return(close, months=1)

    assert math.isnan(result.iloc[20])
    assert result.iloc[21] == pytest.approx(21.0)


def test_12_1_return_golden_fixture():
    close = pd.Series(range(1, 254), dtype=float)

    result = calculate_12_1_return(close)

    assert result.iloc[252] == pytest.approx(231.0)


def test_sector_relative_rank_golden_fixture():
    df = pd.DataFrame(
        {
            "sector": ["Tech", "Tech", "Health"],
            "score": [0.8, 0.4, 0.9],
        }
    )

    result = sector_relative_rank(df)

    assert result.tolist() == [0.5, 1.0, 1.0]
