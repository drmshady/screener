from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from backend.src.data.earnings_calendar import YFinanceEarningsCalendarProvider
from backend.src.data.econ_calendar import load_market_events_from_yaml
from backend.src.events.service import EventsService


def test_yfinance_provider_parses_dict_calendar(monkeypatch) -> None:
    class FakeTicker:
        calendar = {"Earnings Date": [date(2026, 6, 14)]}

    monkeypatch.setattr(
        "backend.src.data.earnings_calendar.yf.Ticker", lambda ticker: FakeTicker()
    )

    provider = YFinanceEarningsCalendarProvider()
    event = provider.next_earnings_event(
        "XYZ", as_of_date=date(2026, 6, 11), days_ahead=30
    )

    assert event is not None
    assert event.event_date == "2026-06-14"
    assert event.metadata["provider"] == "yfinance"


def test_yfinance_provider_parses_dataframe_calendar(monkeypatch) -> None:
    class FakeTicker:
        calendar = pd.DataFrame({"Earnings Date": [pd.Timestamp("2026-06-20")]})

    monkeypatch.setattr(
        "backend.src.data.earnings_calendar.yf.Ticker", lambda ticker: FakeTicker()
    )

    provider = YFinanceEarningsCalendarProvider()
    event = provider.next_earnings_event(
        "XYZ", as_of_date=date(2026, 6, 11), days_ahead=30
    )

    assert event is not None
    assert event.event_date == "2026-06-20"


def test_events_service_does_not_exclude_unknown_earnings(tmp_path: Path) -> None:
    service = EventsService(db_path=tmp_path / "catalog.db")

    assert (
        service.should_exclude_for_earnings(
            "UNKNOWN", as_of_date=date(2026, 6, 11), within_days=7
        )
        is False
    )


def test_events_service_excludes_known_imminent_earnings(tmp_path: Path) -> None:
    service = EventsService(db_path=tmp_path / "catalog.db")
    service.store_ticker_events(
        "XYZ",
        [
            {
                "ticker": "XYZ",
                "event_type": "earnings_scheduled",
                "event_date": "2026-06-14",
                "event_time": "08:30:00",
                "source_name": "yfinance_earnings_v1",
                "source_as_of": "2026-06-11T12:00:00Z",
                "source_url": "https://finance.yahoo.com/quote/XYZ",
                "metadata": {"provider": "fixture"},
            }
        ],
        source_name="yfinance_earnings_v1",
    )

    assert (
        service.should_exclude_for_earnings(
            "XYZ", as_of_date=date(2026, 6, 11), within_days=7
        )
        is True
    )
    assert (
        service.should_exclude_for_earnings(
            "XYZ", as_of_date=date(2026, 6, 11), within_days=2
        )
        is False
    )


def test_market_events_yaml_loader_filters_and_sorts(tmp_path: Path) -> None:
    calendar = tmp_path / "econ_calendar.yaml"
    calendar.write_text(
        """
source_name: econ_calendar_v1
source_as_of: "2026-06-11T00:00:00Z"
refresh_interval_days: 7
events:
  - event_id: ppi_2026_06
    event_type: PPI
    scheduled_at: "2026-06-11T12:30:00Z"
    expected_value:
    actual_value:
    status: upcoming
    source_url: https://www.bls.gov/schedule/
  - event_id: fomc_2026_06
    event_type: FOMC
    scheduled_at: "2026-06-17T18:00:00Z"
    expected_value:
    actual_value:
    status: upcoming
    source_url: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
""",
        encoding="utf-8",
    )

    events = load_market_events_from_yaml(
        calendar,
        start=datetime(2026, 6, 11, tzinfo=timezone.utc),
        end=datetime(2026, 6, 18, tzinfo=timezone.utc),
    )

    assert [event.event_type for event in events] == ["PPI", "FOMC"]
