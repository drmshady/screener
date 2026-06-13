from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
import pandas as pd
import yfinance as yf

from ..lib.disclaimer import utc_now_iso
from ..models.events import TickerEvent

YFINANCE_EARNINGS_SOURCE = "yfinance_earnings_v1"
FINNHUB_EARNINGS_SOURCE = "finnhub_earnings_v1"


class EarningsCalendarProvider(ABC):
    source_name: str

    @abstractmethod
    def next_earnings_event(
        self,
        ticker: str,
        *,
        as_of_date: date | None = None,
        days_ahead: int = 90,
    ) -> TickerEvent | None:
        raise NotImplementedError


def _as_date(value: Any) -> date | None:
    if value in (None, "", pd.NaT):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return pd.Timestamp(value).date()
    except (TypeError, ValueError):
        return None


def _calendar_values(calendar: Any) -> list[Any]:
    if calendar is None:
        return []
    if isinstance(calendar, dict):
        value = calendar.get("Earnings Date") or calendar.get("EarningsDate")
        if isinstance(value, list):
            return value
        return [value]
    if isinstance(calendar, pd.DataFrame):
        if "Earnings Date" in calendar.columns:
            return calendar["Earnings Date"].dropna().tolist()
        if "Earnings Date" in calendar.index:
            value = calendar.loc["Earnings Date"]
            if isinstance(value, pd.Series):
                return value.dropna().tolist()
            return [value]
    return []


class YFinanceEarningsCalendarProvider(EarningsCalendarProvider):
    source_name = YFINANCE_EARNINGS_SOURCE

    def next_earnings_event(
        self,
        ticker: str,
        *,
        as_of_date: date | None = None,
        days_ahead: int = 90,
    ) -> TickerEvent | None:
        symbol = ticker.strip().upper()
        as_of = as_of_date or date.today()
        upper = as_of + timedelta(days=days_ahead)
        try:
            calendar = yf.Ticker(symbol).calendar
        except Exception:
            return None
        dates = sorted(
            event_date
            for raw in _calendar_values(calendar)
            if (event_date := _as_date(raw)) is not None
            and as_of <= event_date <= upper
        )
        if not dates:
            return None
        event_date = dates[0]
        return TickerEvent(
            ticker=symbol,
            event_type="earnings_scheduled",
            event_date=event_date.isoformat(),
            event_time=None,
            source_name=self.source_name,
            source_as_of=utc_now_iso(),
            source_url=f"https://finance.yahoo.com/quote/{symbol}/analysis",
            metadata={"provider": "yfinance"},
        )


class FinnhubEarningsCalendarProvider(EarningsCalendarProvider):
    source_name = FINNHUB_EARNINGS_SOURCE

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY")

    def next_earnings_event(
        self,
        ticker: str,
        *,
        as_of_date: date | None = None,
        days_ahead: int = 90,
    ) -> TickerEvent | None:
        if not self.api_key:
            return None
        symbol = ticker.strip().upper()
        as_of = as_of_date or date.today()
        to_date = as_of + timedelta(days=days_ahead)
        try:
            response = httpx.get(
                "https://finnhub.io/api/v1/calendar/earnings",
                params={
                    "symbol": symbol,
                    "from": as_of.isoformat(),
                    "to": to_date.isoformat(),
                    "token": self.api_key,
                },
                timeout=20,
            )
            response.raise_for_status()
            rows = response.json().get("earningsCalendar", [])
        except Exception:
            return None
        candidates = []
        for row in rows:
            if str(row.get("symbol", "")).upper() != symbol:
                continue
            event_date = _as_date(row.get("date"))
            if event_date is not None and as_of <= event_date <= to_date:
                candidates.append((event_date, row))
        if not candidates:
            return None
        event_date, row = sorted(candidates, key=lambda item: item[0])[0]
        return TickerEvent(
            ticker=symbol,
            event_type="earnings_scheduled",
            event_date=event_date.isoformat(),
            event_time=None,
            source_name=self.source_name,
            source_as_of=datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            source_url=f"https://finnhub.io/calendar/earnings?symbol={symbol}",
            metadata={"provider": "finnhub", "hour": row.get("hour")},
        )


def next_earnings_event(
    ticker: str,
    *,
    as_of_date: date | None = None,
    days_ahead: int = 90,
    providers: list[EarningsCalendarProvider] | None = None,
) -> TickerEvent | None:
    for provider in providers or [
        YFinanceEarningsCalendarProvider(),
        FinnhubEarningsCalendarProvider(),
    ]:
        event = provider.next_earnings_event(
            ticker,
            as_of_date=as_of_date,
            days_ahead=days_ahead,
        )
        if event is not None:
            return event
    return None
