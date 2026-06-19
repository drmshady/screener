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

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import pandas as pd

# Weekend weekday indices per market.
_US_WEEKEND = {5, 6}        # Sat, Sun
_SAUDI_WEEKEND = {4, 5}     # Fri, Sat (Tadawul trades Sun-Thu)


def market_of(ticker: str) -> str:
    """'SA' for Tadawul (.SR) symbols, else 'US'."""
    return "SA" if str(ticker).strip().upper().endswith(".SR") else "US"


def _weekend_for(market: str) -> set[int]:
    return _SAUDI_WEEKEND if market == "SA" else _US_WEEKEND


def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
    holiday = date(year, month, day)
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    days_until = (weekday - current.weekday()) % 7
    return current + timedelta(days=days_until + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    return current - timedelta(days=(current.weekday() - weekday) % 7)


def _easter_date(year: int) -> date:
    """Return Gregorian Easter Sunday using the Meeus/Jones/Butcher algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _us_market_holidays_for_year(year: int) -> set[date]:
    holidays = {
        _observed_fixed_holiday(year, 1, 1),
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Presidents' Day
        _easter_date(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),  # Memorial Day
        _observed_fixed_holiday(year, 7, 4),
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed_fixed_holiday(year, 12, 25),
    }
    if year >= 2022:
        holidays.add(_observed_fixed_holiday(year, 6, 19))  # Juneteenth
    return holidays


@lru_cache(maxsize=64)
def _holiday_set(market: str, start_year: int, end_year: int) -> frozenset[date]:
    if market == "SA":
        return frozenset()
    holidays: set[date] = set()
    for year in range(start_year, end_year + 1):
        holidays.update(_us_market_holidays_for_year(year))
    return frozenset(holidays)


def _holidays_for(market: str, start: date, end: date) -> frozenset[date]:
    return _holiday_set(market, start.year - 1, end.year + 1)


def is_trading_day(d, market: str) -> bool:
    value = pd.Timestamp(d).date()
    market = str(market or "US").upper()
    return (
        value.weekday() not in _weekend_for(market)
        and value not in _holidays_for(market, value, value)
    )


def _previous_trading_day(value: date, market: str) -> date:
    current = value
    while not is_trading_day(current, market):
        current -= timedelta(days=1)
    return current


def latest_completed_trading_day(
    now: datetime | None = None, market: str = "US"
) -> date:
    """
    Latest completed trading session for EOD data.

    For US data, today's EOD bar is treated as final only after a 22:00 UTC
    settle buffer. Weekends and supported market holidays roll back to the
    previous valid session.
    """
    moment = now or datetime.now(timezone.utc)
    anchor = moment.date() if moment.hour >= 22 else moment.date() - timedelta(days=1)
    return _previous_trading_day(anchor, str(market or "US").upper())


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
    market = str(market or "US").upper()
    days = pd.date_range(start, end, freq="D", inclusive="neither")
    return int(sum(1 for d in days if is_trading_day(d, market)))
