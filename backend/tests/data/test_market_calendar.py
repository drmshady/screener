from __future__ import annotations

from datetime import date, datetime, timezone

from backend.src.data.market_calendar import latest_completed_trading_day


def test_latest_completed_trading_day_skips_us_observed_holiday_weekend():
    # Independence Day 2026 falls on Saturday, so NYSE observes Friday 07-03.
    assert latest_completed_trading_day(
        datetime(2026, 7, 3, 23, tzinfo=timezone.utc)
    ) == date(2026, 7, 2)
    assert latest_completed_trading_day(
        datetime(2026, 7, 5, 12, tzinfo=timezone.utc)
    ) == date(2026, 7, 2)
    assert latest_completed_trading_day(
        datetime(2026, 7, 6, 12, tzinfo=timezone.utc)
    ) == date(2026, 7, 2)

