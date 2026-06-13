from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..data.portfolio_store import load_portfolio_state, save_portfolio_state
from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from ..models.portfolio import (
    PortfolioQuote,
    PortfolioQuotesRequest,
    PortfolioQuotesResponse,
    money,
)
from ..screening.engine import build_single_ticker_snapshot
from ..strategies import midterm_52w_high_momentum as midterm
from ..strategies._registry import registry

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class PortfolioStateEnvelope(BaseModel):
    """Opaque persisted state (portfolio + watchlist + settings); shape owned by
    the frontend store. `state` is None when nothing has been saved yet."""
    state: dict[str, Any] | None = None
    updated_at: str | None = None


class PortfolioStateWrite(BaseModel):
    state: dict[str, Any] = Field(default_factory=dict)


@router.get("/state", response_model=PortfolioStateEnvelope)
def get_portfolio_state() -> PortfolioStateEnvelope:
    """Return the server-persisted portfolio/watchlist/settings blob (or empty)."""
    stored = load_portfolio_state()
    if not stored:
        return PortfolioStateEnvelope(state=None, updated_at=None)
    return PortfolioStateEnvelope(
        state=stored.get("state"), updated_at=stored.get("updated_at")
    )


@router.put("/state", response_model=PortfolioStateEnvelope)
def put_portfolio_state(body: PortfolioStateWrite) -> PortfolioStateEnvelope:
    """Persist the portfolio/watchlist/settings blob (single user, last-write-wins)."""
    updated_at = save_portfolio_state(body.state)
    return PortfolioStateEnvelope(state=body.state, updated_at=updated_at)


def _money_or_none(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return money(Decimal(str(value)))


@router.post("/quotes", response_model=PortfolioQuotesResponse)
def portfolio_quotes(request: PortfolioQuotesRequest) -> PortfolioQuotesResponse:
    quotes: list[PortfolioQuote] = []
    newest_as_of: str | None = None
    for item in request.holdings:
        strategy = registry.get(item.strategy_slug)
        if strategy is None:
            raise HTTPException(
                status_code=404, detail=f"Strategy not found: {item.strategy_slug}"
            )
        if item.strategy_slug != "midterm_52w_high_momentum":
            raise HTTPException(
                status_code=400,
                detail="Portfolio strategy levels are currently available for the midterm 52-week-high strategy",
            )
        try:
            snapshot, data_as_of, data_notes = build_single_ticker_snapshot(item.ticker)
        except ValueError as exc:
            quotes.append(
                PortfolioQuote(
                    ticker=item.ticker,
                    name=item.ticker,
                    sector="Unclassified",
                    strategy_slug=item.strategy_slug,
                    is_stale=True,
                    data_notes=[str(exc)],
                    data_as_of=utc_now_iso(),
                )
            )
            continue

        row = snapshot.iloc[0]
        levels = midterm.derive_levels(row)
        notes = list(data_notes)
        is_stale = bool(notes)
        newest_as_of = max(newest_as_of or data_as_of, data_as_of)
        quotes.append(
            PortfolioQuote(
                ticker=item.ticker,
                name=str(row.get("name", item.ticker)),
                sector=str(row.get("sector", "Unclassified")),
                strategy_slug=item.strategy_slug,
                latest_price=money(Decimal(str(float(row["close"])))),
                entry=_money_or_none(levels["entry"]),
                stop_loss=_money_or_none(levels["stop_loss"]),
                tighter_stop_loss=_money_or_none(levels["tighter_stop_loss"]),
                take_profit=_money_or_none(levels["take_profit"]),
                is_stale=is_stale,
                data_notes=notes,
                data_as_of=data_as_of,
            )
        )

    return PortfolioQuotesResponse(
        quotes=quotes,
        data_as_of=newest_as_of or utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )
