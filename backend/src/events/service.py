from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ..data.earnings_calendar import (
    YFINANCE_EARNINGS_SOURCE,
    EarningsCalendarProvider,
    next_earnings_event,
)
from ..data.econ_calendar import ECON_CALENDAR_SOURCE, seed_econ_calendar
from ..data.events_store import (
    DEFAULT_DB_PATH,
    event_days_to,
    load_event_sources,
    load_market_events,
    load_ticker_events,
    replace_ticker_events,
    upsert_event_source,
)
from ..data.filings_8k import SEC_8K_SOURCE, fetch_recent_8k_filings
from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from ..models.events import (
    EventSourceStatus,
    MarketEventsResponse,
    TickerEvent,
    TickerEventsResponse,
)


@dataclass
class TickerEventsSnapshot:
    ticker: str
    next_earnings_date: str | None
    days_to_earnings: int | None
    recent_8k_count_30d: int
    events: list[TickerEvent]
    sources: list[EventSourceStatus]


class EventsService:
    def __init__(
        self,
        *,
        db_path: Path | str = DEFAULT_DB_PATH,
        earnings_providers: list[EarningsCalendarProvider] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.earnings_providers = earnings_providers

    def store_ticker_events(
        self,
        ticker: str,
        events: list[TickerEvent | dict],
        *,
        source_name: str,
    ) -> None:
        replace_ticker_events(ticker, source_name, events, db_path=self.db_path)
        upsert_event_source(
            source_name,
            display_name=source_name,
            kind="ticker_events",
            refresh_interval_days=3 if source_name == YFINANCE_EARNINGS_SOURCE else 1,
            db_path=self.db_path,
        )

    def refresh_ticker_events(
        self,
        ticker: str,
        *,
        as_of_date: date | None = None,
        earnings_days_ahead: int = 90,
    ) -> None:
        symbol = ticker.upper()
        as_of = as_of_date or date.today()

        try:
            earnings = next_earnings_event(
                symbol,
                as_of_date=as_of,
                days_ahead=earnings_days_ahead,
                providers=self.earnings_providers,
            )
            replace_ticker_events(
                symbol,
                YFINANCE_EARNINGS_SOURCE,
                [earnings] if earnings else [],
                db_path=self.db_path,
            )
            upsert_event_source(
                YFINANCE_EARNINGS_SOURCE,
                display_name="yfinance earnings calendar",
                kind="ticker_events",
                refresh_interval_days=3,
                db_path=self.db_path,
            )
        except Exception:
            upsert_event_source(
                YFINANCE_EARNINGS_SOURCE,
                display_name="yfinance earnings calendar",
                kind="ticker_events",
                refresh_interval_days=3,
                is_stale=True,
                db_path=self.db_path,
            )

        try:
            filings = fetch_recent_8k_filings(
                symbol, as_of_date=as_of, db_path=self.db_path
            )
            replace_ticker_events(symbol, SEC_8K_SOURCE, filings, db_path=self.db_path)
            upsert_event_source(
                SEC_8K_SOURCE,
                display_name="SEC EDGAR 8-K filings",
                kind="ticker_events",
                refresh_interval_days=1,
                db_path=self.db_path,
            )
        except Exception:
            upsert_event_source(
                SEC_8K_SOURCE,
                display_name="SEC EDGAR 8-K filings",
                kind="ticker_events",
                refresh_interval_days=1,
                is_stale=True,
                db_path=self.db_path,
            )

    def ticker_events(
        self,
        ticker: str,
        *,
        as_of_date: date | None = None,
        refresh: bool = True,
        earnings_days_ahead: int = 90,
    ) -> TickerEventsSnapshot:
        symbol = ticker.upper()
        as_of = as_of_date or date.today()
        if refresh:
            self.refresh_ticker_events(
                symbol,
                as_of_date=as_of,
                earnings_days_ahead=earnings_days_ahead,
            )

        events = load_ticker_events(symbol, db_path=self.db_path)
        filtered: list[TickerEvent] = []
        next_earnings_date: str | None = None
        for event in events:
            days = event_days_to(event.event_date, as_of)
            if event.event_type == "8K_filed" and -30 <= days <= 0:
                filtered.append(event)
            elif event.event_type == "earnings_scheduled" and days >= 0:
                filtered.append(event)
                if next_earnings_date is None or event.event_date < next_earnings_date:
                    next_earnings_date = event.event_date

        days_to_earnings = (
            event_days_to(next_earnings_date, as_of) if next_earnings_date else None
        )
        recent_8k_count = sum(1 for event in filtered if event.event_type == "8K_filed")
        sources = load_event_sources(
            [YFINANCE_EARNINGS_SOURCE, SEC_8K_SOURCE],
            db_path=self.db_path,
        )
        return TickerEventsSnapshot(
            ticker=symbol,
            next_earnings_date=next_earnings_date,
            days_to_earnings=days_to_earnings,
            recent_8k_count_30d=recent_8k_count,
            events=filtered,
            sources=sources,
        )

    def should_exclude_for_earnings(
        self,
        ticker: str,
        *,
        as_of_date: date,
        within_days: int,
        refresh: bool = False,
    ) -> bool:
        if within_days <= 0:
            return False
        snapshot = self.ticker_events(
            ticker,
            as_of_date=as_of_date,
            refresh=refresh,
            earnings_days_ahead=max(within_days, 90),
        )
        return (
            snapshot.days_to_earnings is not None
            and 0 <= snapshot.days_to_earnings <= within_days
        )

    def ticker_response(
        self,
        ticker: str,
        *,
        as_of_date: date | None = None,
    ) -> TickerEventsResponse:
        snapshot = self.ticker_events(ticker, as_of_date=as_of_date)
        return TickerEventsResponse(
            ticker=snapshot.ticker,
            next_earnings_date=snapshot.next_earnings_date,
            days_to_earnings=snapshot.days_to_earnings,
            recent_8k_count_30d=snapshot.recent_8k_count_30d,
            events=snapshot.events,
            sources=snapshot.sources,
            data_as_of=utc_now_iso(),
            disclaimer=DISCLAIMER_TEXT,
        )

    def market_response(
        self,
        *,
        days_ahead: int = 7,
        as_of: datetime | None = None,
    ) -> MarketEventsResponse:
        now = as_of or datetime.now(timezone.utc)
        seed_econ_calendar(db_path=self.db_path)
        end = now + timedelta(days=max(days_ahead, 0))
        events = load_market_events(now, end, db_path=self.db_path)
        sources = load_event_sources([ECON_CALENDAR_SOURCE], db_path=self.db_path)
        source = sources[0] if sources else None
        return MarketEventsResponse(
            events=events,
            source_name=ECON_CALENDAR_SOURCE,
            source_as_of=source.source_as_of if source else utc_now_iso(),
            is_stale=source.is_stale if source else True,
            data_as_of=utc_now_iso(),
            disclaimer=DISCLAIMER_TEXT,
        )
