"""Market-aware trading calendar so US (Mon-Fri) and Saudi/Tadawul (Sun-Thu)
data can coexist without their differing weekends causing problems.

The concrete bug this prevents: a stray weekend bar from a data provider (e.g. a
Friday bar for a Saudi name, which doesn't trade Fridays) would otherwise shift
the snapshot's "latest date" onto a non-trading day and empty the universe at the
liquidity gate. We drop per-market weekend rows before computing the latest
session or the staleness gap.

weekday(): Mon=0 ... Fri=4, Sat=5, Sun=6.
"""
from __future__ import annotations

import pandas as pd

# Weekend weekday indices per market.
_US_WEEKEND = {5, 6}        # Sat, Sun
_SAUDI_WEEKEND = {4, 5}     # Fri, Sat (Tadawul trades Sun-Thu)


def market_of(ticker: str) -> str:
    """'SA' for Tadawul (.SR) symbols, else 'US'."""
    return "SA" if str(ticker).strip().upper().endswith(".SR") else "US"


def _weekend_for(market: str) -> set[int]:
    return _SAUDI_WEEKEND if market == "SA" else _US_WEEKEND


def is_trading_day(d, market: str) -> bool:
    return pd.Timestamp(d).weekday() not in _weekend_for(market)


def drop_market_weekends(prices: pd.DataFrame) -> pd.DataFrame:
    """Remove rows that fall on each ticker's market weekend.

    Vectorized: US rows keep Mon-Fri, Saudi (.SR) rows keep Sun-Thu. A provider's
    stray weekend bar is dropped so it can't become the snapshot's latest date.
    """
    if prices.empty or "as_of_date" not in prices or "ticker" not in prices:
        return prices
    weekday = pd.to_datetime(prices["as_of_date"]).dt.weekday
    is_saudi = prices["ticker"].astype(str).str.upper().str.endswith(".SR")
    keep_us = ~is_saudi & ~weekday.isin(list(_US_WEEKEND))
    keep_sa = is_saudi & ~weekday.isin(list(_SAUDI_WEEKEND))
    return prices[keep_us | keep_sa]


def trading_days_between(start, end, market: str) -> int:
    """Number of trading sessions strictly between two dates for a market
    (used by the staleness gap so Saudi names aren't judged on the US calendar)."""
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    if end <= start:
        return 0
    weekend = _weekend_for(market)
    days = pd.date_range(start, end, freq="D", inclusive="neither")
    return int(sum(1 for d in days if d.weekday() not in weekend))
