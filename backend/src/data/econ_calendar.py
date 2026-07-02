from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from ..models.events import MarketEvent
from .events_store import DEFAULT_DB_PATH, replace_market_events, upsert_event_source

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ECON_CALENDAR_PATH = ROOT / "backend" / "data" / "econ_calendar.yaml"
ECON_CALENDAR_SOURCE = "econ_calendar_v1"


def _parse_dt(value: str | datetime) -> datetime:
    parsed = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def load_econ_calendar(path: Path | str = DEFAULT_ECON_CALENDAR_PATH) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    payload.setdefault("source_name", ECON_CALENDAR_SOURCE)
    payload.setdefault("events", [])
    payload.setdefault("refresh_interval_days", 7)
    return payload


def load_market_events_from_yaml(
    path: Path | str = DEFAULT_ECON_CALENDAR_PATH,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[MarketEvent]:
    payload = load_econ_calendar(path)
    start_dt = start.astimezone(UTC) if start else datetime.now(UTC)
    end_dt = end.astimezone(UTC) if end else start_dt + timedelta(days=7)
    events: list[MarketEvent] = []
    for row in payload.get("events", []):
        scheduled = _parse_dt(row["scheduled_at"])
        if scheduled < start_dt or scheduled > end_dt:
            continue
        events.append(
            MarketEvent(
                event_id=str(row["event_id"]),
                event_type=str(row["event_type"]),
                scheduled_at=scheduled.isoformat().replace("+00:00", "Z"),
                expected_value=row.get("expected_value"),
                actual_value=row.get("actual_value"),
                status=row.get("status") or "upcoming",
                source_url=str(row.get("source_url") or ""),
            )
        )
    return sorted(events, key=lambda event: event.scheduled_at)


def seed_econ_calendar(
    *,
    path: Path | str = DEFAULT_ECON_CALENDAR_PATH,
    db_path: Path | str = DEFAULT_DB_PATH,
    refreshed_at: datetime | None = None,
) -> int:
    payload = load_econ_calendar(path)
    events = [
        MarketEvent(
            event_id=str(row["event_id"]),
            event_type=str(row["event_type"]),
            scheduled_at=_parse_dt(row["scheduled_at"])
            .isoformat()
            .replace("+00:00", "Z"),
            expected_value=row.get("expected_value"),
            actual_value=row.get("actual_value"),
            status=row.get("status") or "upcoming",
            source_url=str(row.get("source_url") or ""),
        )
        for row in payload.get("events", [])
    ]
    source_name = str(payload.get("source_name") or ECON_CALENDAR_SOURCE)
    source_as_of = str(payload.get("source_as_of"))
    replace_market_events(
        events, source_name=source_name, source_as_of=source_as_of, db_path=db_path
    )
    upsert_event_source(
        source_name,
        display_name="US macro calendar",
        kind="market_events",
        refresh_interval_days=int(payload.get("refresh_interval_days") or 7),
        last_refreshed_at=(refreshed_at or datetime.now(UTC))
        .astimezone(UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        db_path=db_path,
    )
    return len(events)


if __name__ == "__main__":
    count = seed_econ_calendar()
    print(f"Seeded {count} market events")
