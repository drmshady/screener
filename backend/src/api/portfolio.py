from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agent.advisor_prompt import (
    build_holding_advisor_prompt,
    build_portfolio_advisor_prompt,
    load_survivorship_status,
)
from ..data.portfolio_store import (
    load_portfolio_state,
    load_transactions,
    save_portfolio_state,
    save_transactions,
)
from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from ..lib.flags import personal_use_directive, portfolio_heat_ceiling
from ..models.portfolio import (
    HoldingAdvisorPromptResponse,
    ImportRequest,
    ImportResult,
    PortfolioAdvisorPromptResponse,
    PortfolioHolding,
    PortfolioHoldingsRequest,
    PortfolioHoldingsResponse,
    PortfolioTotals,
    PortfolioQuote,
    PortfolioQuotesRequest,
    PortfolioQuotesResponse,
    money,
)
from ..portfolio.aggregation import aggregate
from ..portfolio.holding_levels import compute_holding_levels
from ..portfolio.holding_risk import compute_holding_risk
from ..portfolio.transactions import parse_rows
from ..regime.calculator import current_regime_response
from ..screening.engine import build_single_ticker_snapshot
from ..strategies import midterm_52w_high_momentum as midterm
from ..strategies._registry import registry

_SUPPORTED_HOLDINGS_STRATEGY = "midterm_52w_high_momentum"

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
                fair_value=_money_or_none(row.get("fair_value")),
                fair_value_trust_flag=row.get("fair_value_trust_flag"),
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


@router.post("/import", response_model=ImportResult)
def portfolio_import(body: ImportRequest) -> ImportResult:
    """Validate and idempotently apply transaction rows from the owner's Google Sheet.

    The browser reads the sheet via a short-lived GIS token and POSTs the raw rows
    here; the server normalises, validates, deduplicates, and persists.

    Always returns 200 — partial success (some rows rejected) is still success.
    422 only when the request body itself is malformed.
    """
    # Parse and validate the incoming rows
    accepted_new, rejected = parse_rows(list(body.rows))

    # Load existing persisted transactions (empty list if none yet)
    persisted, existing_sheet_id, existing_sheet_range = load_transactions()
    existing_ids: set[str] = {t.id for t in persisted}

    # Idempotent merge: skip ids already present
    net_new = [t for t in accepted_new if t.id not in existing_ids]
    duplicate_count = len(accepted_new) - len(net_new)

    merged = persisted + net_new
    sheet_id = body.sheet_id or existing_sheet_id
    sheet_range = body.sheet_range or existing_sheet_range
    save_transactions(merged, sheet_id, sheet_range)

    return ImportResult(
        accepted_count=len(net_new),
        duplicate_count=duplicate_count,
        rejected=rejected,
        transactions_total=len(merged),
        data_as_of=utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )


def _require_supported_strategy(slug: str) -> None:
    if slug != _SUPPORTED_HOLDINGS_STRATEGY:
        raise HTTPException(
            status_code=400,
            detail="Portfolio holding levels are currently available for the midterm 52-week-high strategy",
        )


def _assemble_holdings(
    body: PortfolioHoldingsRequest,
) -> tuple[list[PortfolioHolding], PortfolioTotals, str | None]:
    """Aggregate transactions into priced holdings + portfolio totals.

    Single source of truth shared by /holdings and the held-position advisor
    prompt routes, so the prompt's numbers are byte-identical to the table's.
    """
    transactions, _sheet_id, _sheet_range = load_transactions()
    base_holdings = aggregate(transactions)
    holdings: list[PortfolioHolding] = []
    newest_as_of: str | None = None

    for holding in base_holdings:
        if holding.status != "open":
            holdings.append(PortfolioHolding(**holding.model_dump()))
            continue
        enriched = compute_holding_levels(holding)
        if enriched.data_as_of:
            newest_as_of = max(newest_as_of or enriched.data_as_of, enriched.data_as_of)
        holdings.append(enriched)

    total_invested = Decimal("0")
    sector_values: dict[str, Decimal] = {}
    for holding in holdings:
        if holding.status != "open":
            continue
        basis_price = holding.current_price or holding.avg_cost
        value = basis_price * holding.net_quantity
        total_invested += value
        sector_values[holding.sector] = sector_values.get(holding.sector, Decimal("0")) + value

    total_capital_at_risk = Decimal("0")
    for holding in holdings:
        if holding.status != "open":
            continue
        risk = compute_holding_risk(
            holding,
            levels=holding.levels,
            current_price=holding.current_price,
            sector=holding.sector,
            total_capital=body.total_capital,
            caps=body.caps,
            sector_value=sector_values.get(holding.sector, Decimal("0")),
            available_cash=body.available_cash,
        )
        holding.risk = risk
        if risk is not None:
            total_capital_at_risk += risk.actual_capital_at_risk

    total_capital_at_risk_pct = (
        float(total_capital_at_risk / body.total_capital)
        if body.total_capital > 0
        else 0.0
    )
    heat_ceiling_pct = portfolio_heat_ceiling()
    totals = PortfolioTotals(
        total_invested=money(total_invested),
        total_capital_at_risk=money(total_capital_at_risk),
        total_capital_at_risk_pct=total_capital_at_risk_pct,
        heat_ceiling_pct=heat_ceiling_pct,
        heat_headroom_pct=heat_ceiling_pct - total_capital_at_risk_pct,
    )
    return holdings, totals, newest_as_of


def _best_effort_regime() -> str | None:
    """Current regime name for the prompt; None if unavailable (never fatal)."""
    try:
        return str(current_regime_response().regime)
    except Exception:
        return None


@router.post("/holdings", response_model=PortfolioHoldingsResponse)
def portfolio_holdings(body: PortfolioHoldingsRequest) -> PortfolioHoldingsResponse:
    _require_supported_strategy(body.strategy_slug)
    holdings, totals, newest_as_of = _assemble_holdings(body)
    return PortfolioHoldingsResponse(
        holdings=holdings,
        totals=totals,
        data_as_of=newest_as_of or utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )


@router.post("/holdings/advisor-prompt", response_model=PortfolioAdvisorPromptResponse)
def portfolio_holdings_advisor_prompt(
    body: PortfolioHoldingsRequest,
) -> PortfolioAdvisorPromptResponse:
    """One copy-ready hold/trim/exit review prompt covering every open holding."""
    _require_supported_strategy(body.strategy_slug)
    holdings, totals, newest_as_of = _assemble_holdings(body)
    open_holdings = [h for h in holdings if h.status == "open"]
    strategy = registry.get(body.strategy_slug)
    directive = personal_use_directive()
    prompt = build_portfolio_advisor_prompt(
        open_holdings,
        totals,
        strategy,
        survivorship=load_survivorship_status(slug=body.strategy_slug),
        regime=_best_effort_regime(),
        directive=directive,
    )
    return PortfolioAdvisorPromptResponse(
        strategy=body.strategy_slug,
        holding_count=len(open_holdings),
        personal_use_directive=directive,
        prompt=prompt,
        data_as_of=newest_as_of or utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )


@router.post(
    "/holdings/{ticker}/advisor-prompt", response_model=HoldingAdvisorPromptResponse
)
def holding_advisor_prompt(
    ticker: str, body: PortfolioHoldingsRequest
) -> HoldingAdvisorPromptResponse:
    """One copy-ready hold/trim/exit review prompt for a single held position."""
    _require_supported_strategy(body.strategy_slug)
    holdings, _totals, _newest = _assemble_holdings(body)
    symbol = ticker.strip().upper()
    match = next(
        (h for h in holdings if h.ticker == symbol and h.status == "open"), None
    )
    if match is None:
        raise HTTPException(
            status_code=404, detail=f"No open holding for ticker: {symbol}"
        )
    strategy = registry.get(body.strategy_slug)
    directive = personal_use_directive()
    prompt = build_holding_advisor_prompt(
        match,
        strategy,
        survivorship=load_survivorship_status(slug=body.strategy_slug),
        regime=_best_effort_regime(),
        directive=directive,
    )
    return HoldingAdvisorPromptResponse(
        ticker=symbol,
        strategy=body.strategy_slug,
        personal_use_directive=directive,
        prompt=prompt,
        data_as_of=match.data_as_of or utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )
