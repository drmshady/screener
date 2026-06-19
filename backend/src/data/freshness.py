from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .market_calendar import latest_completed_trading_day, trading_days_between

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = ROOT / "backend" / "data" / "manifest.json"


@dataclass(frozen=True)
class DataFreshnessRecord:
    source_name: str
    kind: str
    data_as_of: date | None
    latest_session: date
    sessions_behind: int | None
    is_stale: bool
    last_refresh_outcome: str


@dataclass(frozen=True)
class DataFreshnessSnapshot:
    sources: tuple[DataFreshnessRecord, ...]
    any_stale: bool
    latest_session: date


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"sources": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"sources": {}}


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latest_price_bar(raw: dict[str, Any]) -> date | None:
    by_ticker = raw.get("last_bar_date_by_ticker")
    if isinstance(by_ticker, dict):
        dates = [
            parsed.date()
            for value in by_ticker.values()
            if (parsed := _parse_datetime(value))
        ]
        if dates:
            return max(dates)
    for key in ("last_bar_date", "latest_bar"):
        parsed = _parse_datetime(raw.get(key))
        if parsed:
            return parsed.date()
    return None


def _source_data_as_of(raw: dict[str, Any]) -> date | None:
    if raw.get("kind") == "prices":
        latest_bar = _latest_price_bar(raw)
        if latest_bar:
            return latest_bar
    parsed = _parse_datetime(raw.get("source_as_of") or raw.get("last_success_at"))
    return parsed.date() if parsed else None


def _sessions_behind(data_as_of: date, latest_session: date, market: str) -> int:
    if data_as_of >= latest_session:
        return 0
    between = trading_days_between(data_as_of, latest_session, market)
    return between + (1 if pd.Timestamp(latest_session).date() > data_as_of else 0)


def _record_for_source(
    source_name: str,
    raw: dict[str, Any] | None,
    *,
    latest_session: date,
) -> DataFreshnessRecord:
    if raw is None:
        return DataFreshnessRecord(
            source_name=source_name,
            kind="unknown",
            data_as_of=None,
            latest_session=latest_session,
            sessions_behind=None,
            is_stale=True,
            last_refresh_outcome="failed",
        )

    kind = str(raw.get("kind") or "unknown")
    data_as_of = _source_data_as_of(raw)
    market = str(raw.get("market") or "US").upper()
    sessions = (
        _sessions_behind(data_as_of, latest_session, market)
        if data_as_of is not None
        else None
    )
    refresh_interval = int(raw.get("refresh_interval_days") or 0)
    computed_stale = sessions is None or sessions > refresh_interval
    is_stale = bool(raw.get("is_stale")) or computed_stale
    outcome = str(
        raw.get("last_refresh_outcome")
        or raw.get("refresh_outcome")
        or ("failed" if is_stale else "skipped-current")
    )
    return DataFreshnessRecord(
        source_name=source_name,
        kind=kind,
        data_as_of=data_as_of,
        latest_session=latest_session,
        sessions_behind=sessions,
        is_stale=is_stale,
        last_refresh_outcome=outcome,
    )


def compute_data_freshness(
    *,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
    now: datetime | None = None,
    required_sources: Iterable[str] | None = None,
) -> DataFreshnessSnapshot:
    """Compute per-source freshness from cached metadata only.

    This helper intentionally performs no network calls and writes nothing. It
    reads the manifest, normalizes source dates, and compares them to the latest
    completed US trading session.
    """
    manifest = _load_manifest(Path(manifest_path))
    sources_raw = manifest.get("sources", {})
    if not isinstance(sources_raw, dict):
        sources_raw = {}
    source_names = set(sources_raw)
    if required_sources:
        source_names.update(required_sources)
    latest_session = latest_completed_trading_day(now)
    records = tuple(
        _record_for_source(
            source_name,
            sources_raw.get(source_name)
            if isinstance(sources_raw.get(source_name), dict)
            else None,
            latest_session=latest_session,
        )
        for source_name in sorted(source_names)
    )
    return DataFreshnessSnapshot(
        sources=records,
        any_stale=any(record.is_stale for record in records),
        latest_session=latest_session,
    )
