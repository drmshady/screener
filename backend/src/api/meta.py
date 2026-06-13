from __future__ import annotations

import json
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..data.prices import latest_completed_trading_day
from ..lib.disclaimer import DISCLAIMER_TEXT

router = APIRouter()

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "data" / "manifest.json"


class SourceMeta(BaseModel):
    source_name: str
    kind: str
    source_as_of: datetime
    is_stale: bool
    refresh_interval_days: int
    source_url: str | None = None
    last_success_at: datetime | None = None
    last_bar_date: str | None = None
    display_name: str | None = None


class MetaResponse(BaseModel):
    sources: list[SourceMeta]
    disclaimer: str = DISCLAIMER_TEXT


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, str) and value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _latest_bar_datetime(raw: dict[str, Any]) -> tuple[datetime | None, str | None]:
    by_ticker = raw.get("last_bar_date_by_ticker")
    if not isinstance(by_ticker, dict) or not by_ticker:
        return None, None
    values = [str(value) for value in by_ticker.values() if value]
    if not values:
        return None, None
    latest = max(values)
    as_date = datetime.fromisoformat(latest).date()
    return datetime.combine(as_date, time(21, 0), tzinfo=timezone.utc), latest


def _parse_source(source_name: str, raw: dict[str, Any]) -> SourceMeta | None:
    last_success_at = _parse_datetime(
        raw.get("last_success_at") or raw.get("source_as_of")
    )
    bar_dt, last_bar_date = _latest_bar_datetime(raw)
    source_dt = bar_dt or last_success_at
    if not source_dt:
        return None
    if source_dt.tzinfo is None:
        source_dt = source_dt.replace(tzinfo=timezone.utc)
    refresh_days = int(raw.get("refresh_interval_days", 1))
    if raw.get("kind") == "prices" and last_bar_date:
        latest_complete = latest_completed_trading_day()
        age_days = max(
            0,
            (latest_complete - datetime.fromisoformat(str(last_bar_date)).date()).days,
        )
    else:
        age_days = (
            datetime.now(timezone.utc) - source_dt.astimezone(timezone.utc)
        ).total_seconds() / 86400
    return SourceMeta(
        source_name=source_name,
        kind=str(raw.get("kind", "unknown")),
        source_as_of=source_dt,
        is_stale=bool(raw.get("is_stale", age_days > refresh_days)),
        refresh_interval_days=refresh_days,
        source_url=raw.get("source_url"),
        last_success_at=last_success_at,
        last_bar_date=last_bar_date,
        display_name=raw.get("display_name"),
    )


@router.get("/healthz")
def healthz():
    return {"status": "ok"}


@router.get("/meta", response_model=MetaResponse)
def get_meta():
    if not MANIFEST_PATH.exists():
        return MetaResponse(sources=[])
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    sources_raw = manifest.get("sources", {})
    sources = [
        parsed
        for name, raw in sources_raw.items()
        if isinstance(raw, dict) and (parsed := _parse_source(name, raw)) is not None
    ]
    return MetaResponse(sources=sources)
