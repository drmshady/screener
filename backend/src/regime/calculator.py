from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd

from ..indicators.moving_averages import calculate_sma
from ..models.regime import RegimeInputs, RegimeResponse
from .breadth import BreadthSnapshot, breadth_snapshot
from ..screening.regime import _load_spy


def _money(value: float | None) -> Decimal | None:
    if value is None or pd.isna(value):
        return None
    return Decimal(str(round(float(value), 4)))


def _spy_inputs(
    as_of_date: str | None = None,
    spy_prices: pd.DataFrame | None = None,
    sma_length: int = 200,
) -> tuple[float | None, float | None, bool | None, date, str, str | None]:
    source = "injected"
    if spy_prices is None:
        spy_prices, source = _load_spy(as_of_date, sma_length)
    if spy_prices is None or spy_prices.empty:
        return (
            None,
            None,
            None,
            date.today(),
            source,
            "SPY price data unavailable; regime gate fails open.",
        )

    frame = spy_prices.copy()
    frame["as_of_date"] = pd.to_datetime(frame["as_of_date"])
    if as_of_date:
        frame = frame[frame["as_of_date"] <= pd.Timestamp(as_of_date)]
    frame = frame.dropna(subset=["close"]).sort_values("as_of_date")
    if frame.empty:
        return (
            None,
            None,
            None,
            date.today(),
            source,
            "SPY price data unavailable for the requested date; regime gate fails open.",
        )
    close = frame["close"].astype(float)
    last_date = pd.Timestamp(frame["as_of_date"].iloc[-1]).date()
    if len(close) < sma_length:
        return (
            float(close.iloc[-1]),
            None,
            None,
            last_date,
            source,
            f"Insufficient SPY history for a {sma_length}-day SMA; regime gate fails open.",
        )
    sma = calculate_sma(close, sma_length)
    last_close = float(close.iloc[-1])
    last_sma = float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else None
    unavailable_reason = (
        f"SPY {sma_length}-day SMA is unavailable; regime gate fails open."
        if last_sma is None
        else None
    )
    return (
        last_close,
        last_sma,
        None if last_sma is None else last_close > last_sma,
        last_date,
        source,
        unavailable_reason,
    )


def _classify(spy_above: bool | None, breadth_pct: float | None) -> str:
    if spy_above is True and breadth_pct is not None and breadth_pct > 0.60:
        return "Trending up"
    if spy_above is False and breadth_pct is not None and breadth_pct < 0.40:
        return "Trending down"
    return "Range-bound"


def _summary(spy_above: bool | None, breadth: BreadthSnapshot, regime: str) -> str:
    spy_text = (
        "SPY is above its 200-day SMA"
        if spy_above is True
        else (
            "SPY is below its 200-day SMA"
            if spy_above is False
            else "SPY 200-day SMA input is unavailable"
        )
    )
    if breadth.pct_above_sma200 is None:
        breadth_text = "S&P 500 breadth is unavailable"
    else:
        breadth_text = (
            f"{breadth.above_count}/{breadth.eligible_count} eligible S&P 500 constituents "
            f"({breadth.pct_above_sma200:.1%}) are above their 200-day SMA"
        )
    return f"{regime}: {spy_text}; {breadth_text}."


def current_regime_response(
    as_of_date: str | None = None,
    spy_prices: pd.DataFrame | None = None,
    breadth_prices: pd.DataFrame | None = None,
    constituents: list[str] | None = None,
    force_breadth_refresh: bool = False,
) -> RegimeResponse:
    spy_close, spy_sma, spy_above, spy_as_of, spy_source, spy_unavailable_reason = _spy_inputs(
        as_of_date=as_of_date,
        spy_prices=spy_prices,
    )
    breadth = breadth_snapshot(
        as_of_date=as_of_date,
        constituents=constituents,
        prices=breadth_prices,
        force_refresh=force_breadth_refresh,
    )
    regime = _classify(spy_above, breadth.pct_above_sma200)
    return RegimeResponse(
        regime=regime,
        rule_summary=_summary(spy_above, breadth, regime),
        inputs=RegimeInputs(
            spy_close=_money(spy_close),
            spy_sma200=_money(spy_sma),
            spy_above_sma200=spy_above,
            breadth_pct_above_sma200=breadth.pct_above_sma200,
            breadth_above_count=breadth.above_count,
            breadth_eligible_count=breadth.eligible_count,
            breadth_total_constituents=breadth.total_constituents,
            price_source_name=spy_source,
            unavailable_reason=spy_unavailable_reason,
            breadth_source_name=breadth.source_name,
            breadth_source_as_of=breadth.source_as_of,
        ),
        as_of_date=spy_as_of if as_of_date is None else pd.Timestamp(as_of_date).date(),
    )
