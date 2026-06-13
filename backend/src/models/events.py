from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EventSourceStatus(BaseModel):
    source_name: str
    source_as_of: str
    is_stale: bool


class TickerEvent(BaseModel):
    ticker: str | None = None
    event_type: Literal["earnings_scheduled", "8K_filed"]
    event_date: str
    event_time: str | None = None
    source_name: str
    source_as_of: str | None = None
    source_url: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketEvent(BaseModel):
    event_id: str
    event_type: str
    scheduled_at: str
    expected_value: str | None = None
    actual_value: str | None = None
    status: Literal["upcoming", "released", "cancelled"] = "upcoming"
    source_url: str


class TickerEventsResponse(BaseModel):
    ticker: str
    next_earnings_date: str | None = None
    days_to_earnings: int | None = None
    recent_8k_count_30d: int = 0
    events: list[TickerEvent]
    sources: list[EventSourceStatus]
    data_as_of: str
    disclaimer: str


class MarketEventsResponse(BaseModel):
    events: list[MarketEvent]
    source_name: str
    source_as_of: str
    is_stale: bool
    data_as_of: str
    disclaimer: str
