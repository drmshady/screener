from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta, timezone
from time import sleep
from typing import List, Optional

import pandas as pd
import yfinance as yf

from .market_calendar import latest_completed_trading_day
from .prices_store import load_last_dates


class PriceProvider(ABC):
    @abstractmethod
    def fetch_ohlcv(
        self,
        tickers: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for given tickers.
        Returns columns: ticker, as_of_date, open, high, low, close, adj_close,
        volume, source_name, source_as_of.
        """
        raise NotImplementedError


class YFinancePriceProvider(PriceProvider):
    def __init__(self, max_retries: int = 2, backoff_seconds: float = 0.75):
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def _download(
        self,
        tickers: list[str],
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> pd.DataFrame:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return yf.download(
                    tickers,
                    start=start_date.isoformat() if start_date else None,
                    end=end_date.isoformat() if end_date else None,
                    group_by="ticker",
                    auto_adjust=False,
                    progress=False,
                    threads=True,
                )
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    sleep(self.backoff_seconds * (2**attempt))
        if last_exc:
            raise last_exc
        return pd.DataFrame()

    def fetch_ohlcv(
        self,
        tickers: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        tickers = sorted({ticker.strip().upper() for ticker in tickers if ticker})
        if not tickers:
            return pd.DataFrame()

        df = self._download(tickers, start_date, end_date)
        if df.empty:
            return pd.DataFrame()

        now = datetime.now(timezone.utc)
        records: list[dict] = []
        if len(tickers) == 1:
            single = df
            if isinstance(df.columns, pd.MultiIndex):
                # Current yfinance returns MultiIndex (ticker, field) columns even for a
                # single-element list + group_by="ticker". Flatten to the field level so
                # the row.get("Close") parse below sees "Close", not ("SPY", "Close") —
                # otherwise every row is dropped as NaN and the fetch returns empty
                # (this silently broke SPY/regime and any single-ticker fetch).
                level0 = set(df.columns.get_level_values(0))
                single = df[tickers[0]] if tickers[0] in level0 else df.droplevel(0, axis=1)
            ticker_frames = [(tickers[0], single)]
        else:
            level0 = (
                set(df.columns.get_level_values(0))
                if hasattr(df.columns, "levels")
                else set()
            )
            ticker_frames = [
                (ticker, df[ticker]) for ticker in tickers if ticker in level0
            ]

        for ticker, ticker_df in ticker_frames:
            for idx, row in ticker_df.iterrows():
                if (
                    pd.isna(row.get("Close"))
                    or pd.isna(row.get("High"))
                    or pd.isna(row.get("Low"))
                ):
                    continue
                records.append(
                    {
                        "ticker": ticker,
                        "as_of_date": pd.Timestamp(idx).date(),
                        "open": float(row.get("Open", 0) or 0),
                        "high": float(row.get("High", 0) or 0),
                        "low": float(row.get("Low", 0) or 0),
                        "close": float(row.get("Close", 0) or 0),
                        "adj_close": float(row.get("Adj Close", 0) or 0),
                        "volume": int(row.get("Volume", 0) or 0),
                        "source_name": "yfinance",
                        "source_as_of": now,
                    }
                )
        return pd.DataFrame(records)


def _next_business_day(value: date) -> date:
    current = value + timedelta(days=1)
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return current


def fetch_incremental_ohlcv(
    tickers: list[str],
    history_days: int = 650,
    provider: PriceProvider | None = None,
    today: datetime | None = None,
) -> pd.DataFrame:
    """Fetch only missing bars for each ticker based on local max dates."""
    tickers = sorted({ticker.strip().upper() for ticker in tickers if ticker})
    if not tickers:
        return pd.DataFrame()
    provider = provider or YFinancePriceProvider()
    latest_complete = latest_completed_trading_day(today)
    end_date = latest_complete + timedelta(days=1)
    last_dates = load_last_dates(tickers)

    grouped: dict[date, list[str]] = {}
    for ticker in tickers:
        last = last_dates.get(ticker)
        if last is not None and last >= latest_complete:
            continue
        start = (
            _next_business_day(last)
            if last
            else end_date - timedelta(days=history_days)
        )
        if start > latest_complete:
            continue
        grouped.setdefault(start, []).append(ticker)

    frames: list[pd.DataFrame] = []
    for start_date, group in sorted(grouped.items()):
        fetched = provider.fetch_ohlcv(group, start_date=start_date, end_date=end_date)
        if not fetched.empty:
            frames.append(fetched)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
