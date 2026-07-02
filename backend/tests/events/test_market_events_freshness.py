from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from backend.src.data.econ_calendar import seed_econ_calendar
from backend.src.events.service import EventsService


def _write_calendar(path: Path) -> None:
    path.write_text(
        """
source_name: econ_calendar_v1
source_as_of: "2026-06-11T00:00:00Z"
refresh_interval_days: 7
events:
  - event_id: nfp_2026_07
    event_type: NFP
    scheduled_at: "2026-07-03T12:30:00Z"
    status: upcoming
    source_url: https://www.bls.gov/schedule/2026/home.htm
  - event_id: cpi_2026_07
    event_type: CPI
    scheduled_at: "2026-07-14T12:30:00Z"
    status: upcoming
    source_url: https://www.bls.gov/schedule/2026/home.htm
  - event_id: fomc_2027_06
    event_type: FOMC
    scheduled_at: "2027-06-09T18:00:00Z"
    status: upcoming
    source_url: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
""",
        encoding="utf-8",
    )


def test_market_events_freshness_uses_reseed_time_and_content_as_of(
    tmp_path: Path,
) -> None:
    calendar = tmp_path / "econ_calendar.yaml"
    db_path = tmp_path / "catalog.db"
    _write_calendar(calendar)

    reseeded_at = datetime(2026, 7, 2, 21, 0, tzinfo=UTC)
    assert seed_econ_calendar(path=calendar, db_path=db_path, refreshed_at=reseeded_at) == 3

    service = EventsService(db_path=db_path, econ_calendar_path=calendar)
    first = service.market_response(days_ahead=30, as_of=reseeded_at)
    second = service.market_response(days_ahead=30, as_of=reseeded_at)

    assert first.is_stale is False
    assert first.source_as_of == "2026-06-11T00:00:00Z"
    assert first.schedule_extends_through == "2027-06-09T18:00:00Z"
    assert [event.event_type for event in first.events] == ["NFP", "CPI"]
    assert first.model_dump(exclude={"data_as_of"}) == second.model_dump(
        exclude={"data_as_of"}
    )


def test_market_events_become_stale_only_after_refresh_interval(
    tmp_path: Path,
) -> None:
    calendar = tmp_path / "econ_calendar.yaml"
    db_path = tmp_path / "catalog.db"
    _write_calendar(calendar)

    seed_econ_calendar(
        path=calendar,
        db_path=db_path,
        refreshed_at=datetime(2026, 7, 2, 21, 0, tzinfo=UTC),
    )

    service = EventsService(db_path=db_path, econ_calendar_path=calendar)
    stale = service.market_response(
        days_ahead=30, as_of=datetime(2026, 7, 10, 21, 0, 1, tzinfo=UTC)
    )

    assert stale.is_stale is True
