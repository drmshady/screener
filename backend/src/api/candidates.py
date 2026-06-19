from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ..data.prices_store import load_prices
from ..events.service import EventsService
from ..lib.disclaimer import DISCLAIMER_TEXT
from ..screening.engine import _load_stooq_prices, _overlay_fresh_prices, run_strategy
from ..shariah.lookup import ShariahLookup
from ..strategies._registry import registry
from .. import strategies as _strategies  # noqa: F401 - registers strategy modules

router = APIRouter(prefix="/candidates", tags=["candidates"])


def _candidate_history_frame(symbol: str, days: int) -> tuple[pd.DataFrame, str]:
    end_date = date.today() + timedelta(days=1)
    lookback_days = max(int(days * 1.6) + 420, 900)
    start_date = end_date - timedelta(days=lookback_days)
    stooq = _load_stooq_prices([symbol], start_date, end_date)
    warm = load_prices([symbol], start_date=start_date, end_date=end_date)

    if not stooq.empty:
        prices = _overlay_fresh_prices(stooq, [symbol], end_date)
        source_name = (
            "Stooq archive + yfinance warm store"
            if not warm.empty
            and pd.to_datetime(warm["as_of_date"]).max()
            >= pd.to_datetime(stooq["as_of_date"]).max()
            else "Stooq archive"
        )
    else:
        prices = warm
        source_name = "yfinance warm store"

    if prices.empty:
        return prices, source_name

    prices = prices.copy()
    prices["ticker"] = prices["ticker"].astype(str).str.upper()
    prices["as_of_date"] = pd.to_datetime(prices["as_of_date"])
    prices = prices[prices["ticker"] == symbol].sort_values(["as_of_date"])
    prices = prices.drop_duplicates(["ticker", "as_of_date"], keep="last")
    prices = prices.dropna(subset=["close", "high", "low"])
    return prices, source_name


@router.get("/{ticker}/history")
def get_candidate_history(
    ticker: str,
    days: int = Query(default=400, ge=30, le=800),
):
    symbol = ticker.upper()
    prices, source_name = _candidate_history_frame(symbol, days)
    if prices.empty:
        raise HTTPException(
            status_code=404, detail="No local OHLCV history found for ticker"
        )

    prices["close"] = prices["close"].astype(float)
    prices["high"] = prices["high"].astype(float)
    prices["low"] = prices["low"].astype(float)
    prices["sma_200"] = prices["close"].rolling(200, min_periods=200).mean()
    prices["high_52w"] = prices["high"].rolling(252, min_periods=252).max()
    tail = prices.tail(days)
    latest_date = pd.Timestamp(tail["as_of_date"].max()).date()

    def _finite_or_none(value: object) -> float | None:
        numeric = float(value) if value is not None else float("nan")
        return numeric if pd.notna(numeric) else None

    return {
        "ticker": symbol,
        "points": [
            {
                "date": pd.Timestamp(row.as_of_date).date().isoformat(),
                "close": float(row.close),
                "high": float(row.high),
                "low": float(row.low),
                "sma_200": _finite_or_none(row.sma_200),
                "high_52w": _finite_or_none(row.high_52w),
            }
            for row in tail.itertuples(index=False)
        ],
        "source_name": source_name,
        "source_as_of": f"{latest_date.isoformat()}T21:00:00Z",
        "data_as_of": f"{latest_date.isoformat()}T21:00:00Z",
        "disclaimer": DISCLAIMER_TEXT,
    }


@router.get("/{ticker}")
def get_candidate(
    ticker: str,
    sources: str | None = Query(default=None),
    include: str | None = Query(default=None),
    exclude: str | None = Query(default=None),
    strategy: str | None = Query(default=None),
    sector_strength_top_fraction: float | None = Query(default=None),
):
    symbol = ticker.upper()
    is_saudi = symbol.endswith(".SR")
    matches = []
    data_as_of = None
    # Scope to the strategy the user screened (when provided) so the detail page
    # reflects that screen instead of every registered strategy; otherwise show all.
    strategies = (
        [s for s in registry.list_all() if s.slug == strategy]
        if strategy
        else registry.list_all()
    )
    for strat in strategies:
        parameters: dict = {"refresh_events": False, "regime_gate": False}
        if is_saudi:
            # Saudi names live in the Tadawul universe, not the US screen — run the
            # Saudi market so the detail page shows the same full strategy match.
            parameters["market"] = "SA"
        # Honor the screen's sector-strength gate toggle so its gate breakdown matches.
        if sector_strength_top_fraction is not None:
            parameters["sector_strength_top_fraction"] = sector_strength_top_fraction
        result = run_strategy(
            strat.slug,
            parameters=parameters,
            filters={"exclude_earnings_within_days": 0},
        )
        data_as_of = data_as_of or result.data_as_of
        matches.extend(
            candidate for candidate in result.candidates if candidate.ticker == symbol
        )
    if not matches:
        raise HTTPException(
            status_code=404, detail="Candidate not found in latest real-data screen"
        )

    first = matches[0]
    shariah_status = ShariahLookup(
        {
            "active_sources": sources,
            "include": include,
            "exclude": exclude,
        }
    ).status(first.ticker)
    events_snapshot = EventsService().ticker_events(
        first.ticker, as_of_date=None, refresh=False
    )
    return {
        "ticker": first.ticker,
        "name": first.name,
        "sector": first.sector,
        "current_price": first.current_price,
        "matches": matches,
        "events": [event.model_dump() for event in events_snapshot.events],
        "shariah": shariah_status.model_dump(),
        "data_as_of": data_as_of,
        "disclaimer": DISCLAIMER_TEXT,
    }
