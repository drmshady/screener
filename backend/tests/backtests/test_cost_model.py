from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from backend.src.backtests.runner import _forward_return


def _prices() -> pd.core.groupby.DataFrameGroupBy:
    frame = pd.DataFrame(
        [
            {"ticker": "ABC", "as_of_date": "2020-01-31", "open": 100, "high": 100, "low": 100, "close": 100},
            {"ticker": "ABC", "as_of_date": "2020-02-03", "open": 100, "high": 100, "low": 100, "close": 100},
            {"ticker": "ABC", "as_of_date": "2020-02-04", "open": 110, "high": 110, "low": 110, "close": 110},
        ]
    )
    frame["as_of_date"] = pd.to_datetime(frame["as_of_date"])
    return frame.groupby("ticker", sort=False)


def test_per_side_cost_model_reduces_forward_return() -> None:
    frictionless = _forward_return(_prices(), "ABC", date(2020, 1, 31), horizon_days=4, cost_bps=0)
    modeled = _forward_return(_prices(), "ABC", date(2020, 1, 31), horizon_days=4, cost_bps=10)

    assert frictionless == pytest.approx(0.10)
    assert modeled == pytest.approx(0.098)
    assert modeled < frictionless
