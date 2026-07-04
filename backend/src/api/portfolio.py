from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agent.advisor_prompt import (
    build_holding_advisor_prompt,
    build_portfolio_advisor_prompt,
    build_watchlist_advisor_prompt,
    load_survivorship_status,
)
from .analyze import _market_universe, compute_candidate_result
from ..data.portfolio_store import (
    load_portfolio_state,
    load_transactions,
    save_portfolio_state,
    save_transactions,
)
from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from ..lib.flags import (
    personal_use_directive,
    portfolio_heat_ceiling,
    sentiment_export_generation,
)
from ..models.sentiment import SelectionOrigin, SentimentReport
from ..sentiment.budget import BudgetGuard as _BudgetGuard
from ..sentiment.store import CapturedReportStore as _CapturedReportStore
from . import sentiment as _sentiment_api
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
    RealizedTrade,
    TransactionsRequest,
    money,
)
from ..portfolio.aggregation import aggregate
from ..portfolio.holding_levels import compute_holding_levels
from ..portfolio.holding_risk import compute_holding_risk
from ..portfolio.pnl import compute_realized_pnl, compute_unrealized_pnl
from ..portfolio.transactions import parse_rows
from ..regime.calculator import current_regime_response
from ..screening.engine import build_single_ticker_snapshot
from ..strategies import midterm_52w_high_momentum as midterm
from ..strategies._registry import registry

_SUPPORTED_HOLDINGS_STRATEGY = "midterm_52w_high_momentum"

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# Kept as module globals so tests can inject a temp/seeded store + budget and
# stub on-demand generation without touching the real DB or live providers
# (mirrors api/strategies.py).
CapturedReportStore = _CapturedReportStore
BudgetGuard = _BudgetGuard


def _generate_sentiment(ticker: str, origin: SelectionOrigin, store, budget) -> SentimentReport:
    """Generate + capture one report (feature 017 extension). Isolated as a
    module-level indirection so tests can stub generation off (return None) or
    inject a deterministic report without hitting live providers."""
    return _sentiment_api.generate_and_capture(ticker, origin, store=store, budget=budget)


def _resolve_captured_sentiment(tickers) -> dict[str, SentimentReport]:
    """Best-effort resolve the most-recently captured sentiment report per ticker
    (feature 017). Reads the store only — never triggers source collection, scoring,
    or narrative generation (FR-009). Any per-ticker error omits only that ticker's
    section (fail-soft, FR-010)."""
    try:
        store = CapturedReportStore()
    except Exception:
        return {}
    resolved: dict[str, SentimentReport] = {}
    for ticker in tickers:
        try:
            report = store.latest_for_ticker(ticker)
        except Exception:
            report = None
        if report is not None:
            resolved[ticker] = report
    return resolved


def _resolve_or_generate_sentiment(
    tickers, *, origin: SelectionOrigin
) -> dict[str, SentimentReport]:
    """Feature 017 extension for the portfolio + watchlist exports: embed the
    most-recently captured sentiment per ticker; if a ticker has none captured
    yet, GENERATE and capture one on demand (generate-once-then-reuse), so the
    exported prompt always carries sentiment and subsequent re-exports reuse the
    stored report.

    Best-effort throughout: a store failure yields no sentiment; a per-ticker
    lookup/generation failure omits only that ticker's section (fail-soft,
    FR-010). Generation is skipped entirely when
    `sentiment_export_generation()` is OFF, restoring the strict reuse-only path.
    The screener export deliberately stays reuse-only (uses
    `_resolve_captured_sentiment`) and never generates."""
    try:
        store = CapturedReportStore()
    except Exception:
        return {}
    generate = sentiment_export_generation()
    budget = None
    resolved: dict[str, SentimentReport] = {}
    for ticker in tickers:
        report = None
        try:
            report = store.latest_for_ticker(ticker)
        except Exception:
            report = None
        if report is None and generate:
            try:
                if budget is None:
                    budget = BudgetGuard()
                report = _generate_sentiment(ticker, origin, store, budget)
            except Exception:
                report = None
        if report is not None:
            resolved[ticker] = report
    return resolved


_WATCHLIST_EXPORT_STRATEGIES = ("midterm_52w_high_momentum", "midterm_value_composite")


class WatchlistAdvisorPromptRequest(BaseModel):
    """Owner's watched names to export in the screener-results prompt format
    (feature 017 US3). An empty `tickers` list is valid and yields a clear
    'no watched names' prompt state (FR-013)."""

    strategy_slug: str = "midterm_52w_high_momentum"
    tickers: list[str] = Field(default_factory=list)
    as_of: str | None = None


class WatchlistAdvisorPromptResponse(BaseModel):
    strategy: str
    watched_count: int
    personal_use_directive: bool
    prompt: str
    data_as_of: str
    disclaimer: str


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


@router.post("/transactions", response_model=ImportResult)
def portfolio_add_transactions(body: TransactionsRequest) -> ImportResult:
    """Record one or more manual buy/sell transactions (Feature 016 US4).

    Reuses the feature-013 import validator (`parse_rows`) and the retained
    `transactions` list so manual entry and Sheet import converge on one holdings
    model. Idempotent: rows whose stable content-hash id already exists are counted
    as duplicates, not re-appended. Sheet metadata (if any) is preserved untouched.

    Always returns 200 — partial success (some rows rejected) is still success.
    422 only when the request body itself is malformed.
    """
    accepted_new, rejected = parse_rows(list(body.rows))

    persisted, sheet_id, sheet_range = load_transactions()
    existing_ids: set[str] = {t.id for t in persisted}

    net_new = [t for t in accepted_new if t.id not in existing_ids]
    duplicate_count = len(accepted_new) - len(net_new)

    merged = persisted + net_new
    save_transactions(merged, sheet_id, sheet_range)

    return ImportResult(
        accepted_count=len(net_new),
        duplicate_count=duplicate_count,
        rejected=rejected,
        transactions_total=len(merged),
        data_as_of=utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )


@router.delete("/transactions/{transaction_id}", response_model=ImportResult)
def portfolio_delete_transaction(transaction_id: str) -> ImportResult:
    """Remove one retained transaction by its stable content-hash id, then
    re-aggregate (correct a mistake). 404 if the id is unknown (Feature 016 US4)."""
    persisted, sheet_id, sheet_range = load_transactions()
    remaining = [t for t in persisted if t.id != transaction_id]
    if len(remaining) == len(persisted):
        raise HTTPException(
            status_code=404, detail=f"Transaction not found: {transaction_id}"
        )

    save_transactions(remaining, sheet_id, sheet_range)
    return ImportResult(
        accepted_count=0,
        duplicate_count=0,
        rejected=[],
        transactions_total=len(remaining),
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
) -> tuple[list[PortfolioHolding], PortfolioTotals, str | None, list[RealizedTrade]]:
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

    # Feature 016 (US4): additive, informational-only win/loss + mark-to-market.
    # Realized figures stay None/0 with no closed lots ⇒ byte-identical to today.
    realized = compute_realized_pnl(transactions)
    unrealized_pnl, _unrealized_notes = compute_unrealized_pnl(holdings)
    total_pnl: Decimal | None = None
    if realized.realized_pnl is not None or unrealized_pnl is not None:
        total_pnl = money(
            (realized.realized_pnl or Decimal("0")) + (unrealized_pnl or Decimal("0"))
        )

    totals = PortfolioTotals(
        total_invested=money(total_invested),
        total_capital_at_risk=money(total_capital_at_risk),
        total_capital_at_risk_pct=total_capital_at_risk_pct,
        heat_ceiling_pct=heat_ceiling_pct,
        heat_headroom_pct=heat_ceiling_pct - total_capital_at_risk_pct,
        realized_pnl=realized.realized_pnl,
        unrealized_pnl=unrealized_pnl,
        total_pnl=total_pnl,
        win_rate=realized.win_rate,
        closed_trade_count=realized.closed_trade_count,
        winning_trade_count=realized.winning_trade_count,
    )
    return holdings, totals, newest_as_of, realized.trades


def _best_effort_regime() -> str | None:
    """Current regime name for the prompt; None if unavailable (never fatal)."""
    try:
        return str(current_regime_response().regime)
    except Exception:
        return None


@router.post("/holdings", response_model=PortfolioHoldingsResponse)
def portfolio_holdings(body: PortfolioHoldingsRequest) -> PortfolioHoldingsResponse:
    _require_supported_strategy(body.strategy_slug)
    holdings, totals, newest_as_of, realized_trades = _assemble_holdings(body)
    return PortfolioHoldingsResponse(
        holdings=holdings,
        totals=totals,
        realized_trades=realized_trades,
        data_as_of=newest_as_of or utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )


@router.post("/holdings/advisor-prompt", response_model=PortfolioAdvisorPromptResponse)
def portfolio_holdings_advisor_prompt(
    body: PortfolioHoldingsRequest,
) -> PortfolioAdvisorPromptResponse:
    """One copy-ready hold/trim/exit review prompt covering every open holding."""
    _require_supported_strategy(body.strategy_slug)
    holdings, totals, newest_as_of, _realized_trades = _assemble_holdings(body)
    open_holdings = [h for h in holdings if h.status == "open"]
    strategy = registry.get(body.strategy_slug)
    directive = personal_use_directive()
    sentiment_by_ticker = _resolve_or_generate_sentiment(
        [h.ticker for h in open_holdings], origin=SelectionOrigin.HOLDING
    )
    prompt = build_portfolio_advisor_prompt(
        open_holdings,
        totals,
        strategy,
        survivorship=load_survivorship_status(slug=body.strategy_slug),
        regime=_best_effort_regime(),
        directive=directive,
        sentiment_by_ticker=sentiment_by_ticker,
    )
    return PortfolioAdvisorPromptResponse(
        strategy=body.strategy_slug,
        holding_count=len(open_holdings),
        personal_use_directive=directive,
        prompt=prompt,
        data_as_of=newest_as_of or utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )


@router.post("/watchlist/advisor-prompt", response_model=WatchlistAdvisorPromptResponse)
def watchlist_advisor_prompt(
    body: WatchlistAdvisorPromptRequest,
) -> WatchlistAdvisorPromptResponse:
    """One copy-ready advisor prompt over the owner's watched names, in the same
    screener-results format (feature 017 US3).

    Each watched ticker is re-computed against the current snapshot via
    `compute_candidate_result` (best-effort per ticker: an unresolvable name still
    appears with a no-coverage note). Its most-recently captured sentiment report
    is resolved from the store and embedded; the export triggers NO fresh source
    collection / scoring / narrative generation (FR-009). An empty watchlist is
    valid and returns a clear 'no watched names' body (FR-013)."""
    strategy = registry.get(body.strategy_slug)
    if strategy is None or body.strategy_slug not in _WATCHLIST_EXPORT_STRATEGIES:
        raise HTTPException(
            status_code=422,
            detail=(
                "Watchlist advisor-prompt export is available for the mid-term "
                "strategies (midterm_52w_high_momentum, midterm_value_composite)"
            ),
        )

    # Build the percentile-gate universe snapshot ONCE for momentum and reuse it
    # across every watched ticker instead of rebuilding it per compute call.
    market_universe = None
    if body.strategy_slug == "midterm_52w_high_momentum" and body.tickers:
        try:
            market_universe = _market_universe(body.tickers[0], body.as_of)
        except Exception:
            market_universe = None
        if market_universe is not None and market_universe.empty:
            market_universe = None

    results = []
    unresolved: list[str] = []
    newest_as_of: str | None = None
    for ticker in body.tickers:
        symbol = str(ticker).strip().upper()
        try:
            result = compute_candidate_result(
                symbol,
                strategy=body.strategy_slug,
                as_of=body.as_of,
                market_universe=market_universe,
            )
        except Exception:
            unresolved.append(symbol)
            continue
        results.append(result)
        if result.data_as_of:
            newest_as_of = max(newest_as_of or result.data_as_of, result.data_as_of)

    sentiment_by_ticker = _resolve_or_generate_sentiment(
        [r.ticker for r in results] + unresolved, origin=SelectionOrigin.SCREENER
    )
    directive = personal_use_directive()
    data_as_of = newest_as_of or utc_now_iso()
    prompt = build_watchlist_advisor_prompt(
        strategy,
        results,
        survivorship=load_survivorship_status(slug=body.strategy_slug),
        regime=_best_effort_regime(),
        directive=directive,
        data_as_of=data_as_of,
        disclaimer=DISCLAIMER_TEXT,
        unresolved=unresolved,
        sentiment_by_ticker=sentiment_by_ticker,
    )
    return WatchlistAdvisorPromptResponse(
        strategy=body.strategy_slug,
        watched_count=len(results) + len(unresolved),
        personal_use_directive=directive,
        prompt=prompt,
        data_as_of=data_as_of,
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
    holdings, _totals, _newest, _realized_trades = _assemble_holdings(body)
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
    sentiment = _resolve_or_generate_sentiment(
        [match.ticker], origin=SelectionOrigin.HOLDING
    ).get(match.ticker)
    prompt = build_holding_advisor_prompt(
        match,
        strategy,
        survivorship=load_survivorship_status(slug=body.strategy_slug),
        regime=_best_effort_regime(),
        directive=directive,
        sentiment=sentiment,
    )
    return HoldingAdvisorPromptResponse(
        ticker=symbol,
        strategy=body.strategy_slug,
        personal_use_directive=directive,
        prompt=prompt,
        data_as_of=match.data_as_of or utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )
