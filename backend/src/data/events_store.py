from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from ..lib.disclaimer import utc_now_iso
from ..models.events import EventSourceStatus, MarketEvent, TickerEvent

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = ROOT / "backend" / "data" / "catalog.db"


def parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def ensure_events_tables(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticker_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_time TEXT,
                source_name TEXT NOT NULL,
                source_as_of TEXT NOT NULL,
                source_url TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
            """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                expected_value TEXT,
                actual_value TEXT,
                status TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_as_of TEXT NOT NULL,
                source_url TEXT NOT NULL
            )
            """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events_sources (
                source_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                kind TEXT NOT NULL,
                refresh_interval_days INTEGER NOT NULL,
                last_refreshed_at TEXT NOT NULL,
                is_stale INTEGER NOT NULL
            )
            """)
        conn.commit()


def replace_ticker_events(
    ticker: str,
    source_name: str,
    events: Iterable[TickerEvent | dict[str, Any]],
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    ensure_events_tables(db_path)
    rows: list[dict[str, Any]] = []
    for event in events:
        payload = event.model_dump() if isinstance(event, TickerEvent) else dict(event)
        rows.append(
            {
                "ticker": str(payload.get("ticker") or ticker).upper(),
                "event_type": payload["event_type"],
                "event_date": str(payload["event_date"]),
                "event_time": payload.get("event_time"),
                "source_name": payload.get("source_name") or source_name,
                "source_as_of": payload.get("source_as_of") or utc_now_iso(),
                "source_url": payload.get("source_url") or "",
                "metadata": json.dumps(payload.get("metadata") or {}, sort_keys=True),
            }
        )
    with sqlite3.connect(Path(db_path)) as conn:
        conn.execute(
            "DELETE FROM ticker_events WHERE ticker = ? AND source_name = ?",
            (ticker.upper(), source_name),
        )
        conn.executemany(
            """
            INSERT INTO ticker_events
            (ticker, event_type, event_date, event_time, source_name, source_as_of, source_url, metadata)
            VALUES (:ticker, :event_type, :event_date, :event_time, :source_name, :source_as_of, :source_url, :metadata)
            """,
            rows,
        )
        conn.commit()


def load_ticker_events(
    ticker: str,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[TickerEvent]:
    ensure_events_tables(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT ticker, event_type, event_date, event_time, source_name, source_as_of, source_url, metadata
            FROM ticker_events
            WHERE ticker = ?
            ORDER BY event_date ASC, event_type ASC
            """,
            (ticker.upper(),),
        ).fetchall()
    events: list[TickerEvent] = []
    for row in rows:
        events.append(
            TickerEvent(
                ticker=row["ticker"],
                event_type=row["event_type"],
                event_date=row["event_date"],
                event_time=row["event_time"],
                source_name=row["source_name"],
                source_as_of=row["source_as_of"],
                source_url=row["source_url"],
                metadata=json.loads(row["metadata"] or "{}"),
            )
        )
    return events


def replace_market_events(
    events: Iterable[MarketEvent | dict[str, Any]],
    *,
    source_name: str,
    source_as_of: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    ensure_events_tables(db_path)
    rows: list[dict[str, Any]] = []
    for event in events:
        payload = event.model_dump() if isinstance(event, MarketEvent) else dict(event)
        rows.append(
            {
                "event_id": payload["event_id"],
                "event_type": payload["event_type"],
                "scheduled_at": payload["scheduled_at"],
                "expected_value": payload.get("expected_value"),
                "actual_value": payload.get("actual_value"),
                "status": payload.get("status") or "upcoming",
                "source_name": source_name,
                "source_as_of": source_as_of,
                "source_url": payload.get("source_url") or "",
            }
        )
    with sqlite3.connect(Path(db_path)) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO market_events
            (event_id, event_type, scheduled_at, expected_value, actual_value, status, source_name, source_as_of, source_url)
            VALUES (:event_id, :event_type, :scheduled_at, :expected_value, :actual_value, :status, :source_name, :source_as_of, :source_url)
            """,
            rows,
        )
        conn.commit()


def load_market_events(
    start: datetime,
    end: datetime,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[MarketEvent]:
    ensure_events_tables(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT event_id, event_type, scheduled_at, expected_value, actual_value, status, source_url
            FROM market_events
            WHERE scheduled_at >= ? AND scheduled_at <= ?
            ORDER BY scheduled_at ASC
            """,
            (
                start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            ),
        ).fetchall()
    return [MarketEvent(**dict(row)) for row in rows]


def upsert_event_source(
    source_id: str,
    *,
    display_name: str,
    kind: str,
    refresh_interval_days: int,
    last_refreshed_at: str | None = None,
    is_stale: bool = False,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    ensure_events_tables(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO events_sources
            (source_id, display_name, kind, refresh_interval_days, last_refreshed_at, is_stale)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                display_name,
                kind,
                refresh_interval_days,
                last_refreshed_at or utc_now_iso(),
                int(is_stale),
            ),
        )
        conn.commit()


def load_event_sources(
    source_ids: Iterable[str] | None = None,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[EventSourceStatus]:
    ensure_events_tables(db_path)
    ids = list(source_ids or [])
    where = ""
    params: list[str] = []
    if ids:
        where = f"WHERE source_id IN ({','.join('?' for _ in ids)})"
        params = ids
    with sqlite3.connect(Path(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT source_id, refresh_interval_days, last_refreshed_at, is_stale
            FROM events_sources
            {where}
            ORDER BY source_id ASC
            """,
            params,
        ).fetchall()
    statuses: list[EventSourceStatus] = []
    now = datetime.now(timezone.utc)
    for row in rows:
        source_as_of = row["last_refreshed_at"]
        parsed = parse_dt(source_as_of)
        derived_stale = (
            True
            if parsed is None
            else now - parsed > timedelta(days=int(row["refresh_interval_days"]))
        )
        statuses.append(
            EventSourceStatus(
                source_name=row["source_id"],
                source_as_of=source_as_of,
                is_stale=bool(row["is_stale"]) or derived_stale,
            )
        )
    return statuses


def event_days_to(event_date: str, as_of_date: date) -> int:
    return (date.fromisoformat(event_date) - as_of_date).days
