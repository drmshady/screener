from __future__ import annotations

from fastapi import APIRouter, Query

from ..events.service import EventsService
from ..models.events import MarketEventsResponse, TickerEventsResponse

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/market", response_model=MarketEventsResponse)
def get_market_events(days_ahead: int = Query(default=7, ge=0, le=370)):
    return EventsService().market_response(days_ahead=days_ahead)


@router.get("/ticker/{ticker}", response_model=TickerEventsResponse)
def get_ticker_events(ticker: str):
    return EventsService().ticker_response(ticker)
