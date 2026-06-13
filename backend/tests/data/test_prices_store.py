from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from backend.src.data.prices import (
    fetch_incremental_ohlcv,
    latest_completed_trading_day,
)
from backend.src.data.prices_store import load_last_dates, load_prices, save_prices


def _rows(
    ticker: str, dates: list[str], close: float = 100.0, source_offset: int = 0
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": ticker,
                "as_of_date": pd.Timestamp(day).date(),
                "open": close,
                "high": close + 1,
                "low": close - 1,
                "close": close + index,
                "adj_close": close + index,
                "volume": 1000 + index,
                "source_name": "test",
                "source_as_of": datetime(
                    2026, 1, 1 + source_offset, tzinfo=timezone.utc
                ),
            }
            for index, day in enumerate(dates)
        ]
    )


def test_save_prices_upserts_without_deleting_other_tickers(tmp_path: Path):
    save_prices(_rows("AAA", ["2026-01-02", "2026-01-03"]), prices_dir=tmp_path)
    save_prices(_rows("BBB", ["2026-01-02"]), prices_dir=tmp_path)

    loaded = load_prices(prices_dir=tmp_path)

    assert set(loaded["ticker"]) == {"AAA", "BBB"}
    assert len(loaded) == 3


def test_save_prices_keeps_newest_source_as_of_for_duplicate(tmp_path: Path):
    save_prices(
        _rows("AAA", ["2026-01-02"], close=100, source_offset=0), prices_dir=tmp_path
    )
    save_prices(
        _rows("AAA", ["2026-01-02"], close=125, source_offset=1), prices_dir=tmp_path
    )

    loaded = load_prices(["AAA"], prices_dir=tmp_path)

    assert len(loaded) == 1
    assert float(loaded.iloc[0]["close"]) == 125.0


def test_load_last_dates_returns_max_per_ticker(tmp_path: Path):
    save_prices(_rows("AAA", ["2026-01-02", "2026-01-05"]), prices_dir=tmp_path)
    save_prices(_rows("BBB", ["2026-01-03"]), prices_dir=tmp_path)

    assert load_last_dates(prices_dir=tmp_path) == {
        "AAA": date(2026, 1, 5),
        "BBB": date(2026, 1, 3),
    }


def test_latest_completed_trading_day_uses_prior_session_until_settle_buffer():
    # 2026-06-11 (Thu) 12:00 UTC — today's session not yet closed -> latest is Wed 06-10.
    assert latest_completed_trading_day(
        datetime(2026, 6, 11, 12, tzinfo=timezone.utc)
    ) == date(2026, 6, 10)
    # After the ~22:00 UTC settle buffer, today's EOD bar is final.
    assert latest_completed_trading_day(
        datetime(2026, 6, 11, 23, tzinfo=timezone.utc)
    ) == date(2026, 6, 11)
    # Weekend rolls back to Friday: Sun 2026-06-14 12:00 UTC -> Fri 06-12.
    assert latest_completed_trading_day(
        datetime(2026, 6, 14, 12, tzinfo=timezone.utc)
    ) == date(2026, 6, 12)


def test_incremental_fetch_skips_warm_tickers(monkeypatch, tmp_path: Path):
    # A ticker already current to the latest completed session (Wed 06-10 as of
    # Thu 06-11 12:00 UTC) must not trigger any fetch.
    save_prices(_rows("AAA", ["2026-06-10"]), prices_dir=tmp_path)
    monkeypatch.setattr(
        "backend.src.data.prices.load_last_dates",
        lambda tickers: {"AAA": date(2026, 6, 10)},
    )

    class Provider:
        def fetch_ohlcv(self, tickers, start_date=None, end_date=None):
            raise AssertionError("warm ticker should not fetch")

    fetched = fetch_incremental_ohlcv(
        ["AAA"],
        provider=Provider(),
        today=datetime(2026, 6, 11, 12, tzinfo=timezone.utc),
    )

    assert fetched.empty
