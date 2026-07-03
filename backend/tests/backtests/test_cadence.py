from __future__ import annotations

from datetime import date

import pandas as pd
from backend.src.backtests.runner import _rebalance_as_of_dates


def test_quarterly_and_monthly_cadence_use_multiple_dates_per_year() -> None:
    trading_days = pd.DatetimeIndex(pd.bdate_range("2020-01-01", "2020-12-31"))

    annual = _rebalance_as_of_dates(trading_days, date(2020, 1, 1), date(2020, 12, 31), "A")
    quarterly = _rebalance_as_of_dates(trading_days, date(2020, 1, 1), date(2020, 12, 31), "Q")
    monthly = _rebalance_as_of_dates(trading_days, date(2020, 1, 1), date(2020, 12, 31), "M")

    assert [d.month for d in annual] == [1]
    assert [d.month for d in quarterly] == [1, 4, 7, 10]
    assert len(monthly) == 12
    assert len(quarterly) > len(annual)
    assert len(monthly) > len(quarterly)
