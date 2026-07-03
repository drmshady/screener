from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, HTTPException

from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from ..lib.flags import (
    fit_reward_to_risk_floor,
    personal_use_directive,
    pipeline_enabled,
    portfolio_heat_ceiling,
)
from ..models.pipeline import (
    FitFacts,
    PipelineBoardItem,
    PipelineBoardRequest,
    PipelineBoardResponse,
)
from ..models.portfolio import (
    PortfolioCaps,
    PortfolioHoldingsRequest,
    SizingHolding,
    SizingRequest,
    SizingResponse,
)
from ..pipeline.fit import score_fit
from ..portfolio.exposure import existing_open_risk
from ..portfolio.sizing import size_position
from ..regime.calculator import current_regime_response
from ..strategies import midterm_52w_high_momentum as midterm
from . import analyze, portfolio
from .analyze import compute_candidate_result

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

_MOMENTUM_SLUG = "midterm_52w_high_momentum"


def _regime_allows_new_entries(regime_name: str | None) -> bool:
    """New momentum entries are allowed unless the strategy's own
    REGIME_FAVORABILITY marks the current regime unfavorable."""
    if regime_name is None:
        return True
    return midterm.REGIME_FAVORABILITY.get(regime_name) != "Unfavorable"


def _sizing_holdings() -> list[SizingHolding]:
    """Derive the current open holdings server-side (via the same
    ``_assemble_holdings`` the portfolio page uses) so the board's exposure and
    per-ticker sizing match the portfolio exactly (contract invariant 5)."""
    body = PortfolioHoldingsRequest(total_capital=Decimal("1"))
    holdings, _totals, _as_of, _realized_trades = portfolio._assemble_holdings(body)
    out: list[SizingHolding] = []
    for holding in holdings:
        if holding.status != "open":
            continue
        price = holding.current_price or holding.avg_cost
        out.append(
            SizingHolding(
                ticker=holding.ticker,
                shares=holding.net_quantity,
                current_price=price,
                sector=holding.sector,
            )
        )
    return out


def _reward_to_risk(analysis) -> float | None:
    risk = analysis.risk_distance
    reward = analysis.reward_distance
    if risk is None or reward is None or risk <= 0:
        return None
    return round(reward / risk, 4)


def _volatility(analysis) -> float | None:
    try:
        price = float(analysis.current_price)
    except (TypeError, ValueError):
        return None
    if analysis.atr is None or price <= 0:
        return None
    return analysis.atr / price


def _board_item(
    ticker: str,
    *,
    universe,
    holdings: list[SizingHolding],
    total_capital: Decimal,
    caps: PortfolioCaps,
    available_cash: Decimal | None,
    regime_allows: bool,
    r2r_floor: float,
    directive: bool,
) -> PipelineBoardItem:
    """Run one ticker through analyze → size_position → score_fit with
    per-ticker fail-soft (research.md D1). Any failure yields a single item with
    ``skipped_reason`` set and the rest of the board still renders."""
    symbol = ticker.strip().upper()
    try:
        analysis = compute_candidate_result(
            symbol, strategy=_MOMENTUM_SLUG, market_universe=universe
        )
    except HTTPException as exc:
        return PipelineBoardItem(ticker=symbol, skipped_reason=str(exc.detail))
    except Exception as exc:  # fail-soft: never let one ticker sink the board
        return PipelineBoardItem(ticker=symbol, skipped_reason=f"Could not analyze: {exc}")

    sector = analysis.sector or "Unclassified"
    entry_state = analysis.entry_timing.state if analysis.entry_timing else None

    try:
        sizing = size_position(
            SizingRequest(
                candidate_ticker=symbol,
                entry=Decimal(analysis.entry),
                candidate_sector=sector,
                total_capital=total_capital,
                holdings=holdings,
                caps=caps,
                stop_loss=Decimal(analysis.stop_loss),
                volatility=_volatility(analysis),
            )
        )
    except (InvalidOperation, ValueError) as exc:
        return PipelineBoardItem(
            ticker=symbol,
            entry_timing_state=entry_state,
            sector=sector,
            skipped_reason=f"Could not size: {exc}",
        )

    reward_to_risk = _reward_to_risk(analysis)
    if reward_to_risk is not None:
        sizing = sizing.model_copy(update={"reward_to_risk": reward_to_risk})

    facts = FitFacts(
        entry_ready=entry_state == "entry_ready",
        meaningful_size_survives=(
            sizing.suggested_shares > 0
            and sizing.caps_respected
            and not sizing.conservative_fallback
        ),
        heat_headroom_ok=sizing.binding_constraint != "portfolio_heat",
        sector_room_ok=sizing.binding_constraint != "sector_cap",
        not_overconcentrated=(
            sizing.resulting_position_pct_of_capital <= caps.per_position_cap_pct
        ),
        regime_allows_entries=regime_allows,
        reward_to_risk_ok=reward_to_risk is not None and reward_to_risk >= r2r_floor,
        cash_sufficient=(
            sizing.suggested_shares > 0
            and sizing.binding_constraint != "available_cash"
            and (
                available_cash is None
                or sizing.suggested_position_value <= available_cash
            )
        ),
    )

    fit = score_fit(facts, directive=directive)
    return PipelineBoardItem(
        ticker=symbol,
        entry_timing_state=entry_state,
        sizing_preview=sizing,
        fit=fit,
        sector=sector,
        skipped_reason=None,
    )


def _sort_key(item: PipelineBoardItem):
    """Fit-ranked, stable tie-break on ticker; skipped items sink to the bottom
    (determinism invariant 6)."""
    if item.fit is None:
        return (1, 0, item.ticker)
    return (0, -item.fit.score, item.ticker)


@router.post("/board", response_model=PipelineBoardResponse)
def pipeline_board(request: PipelineBoardRequest) -> PipelineBoardResponse:
    if not pipeline_enabled():
        raise HTTPException(status_code=404, detail="Pipeline board is not enabled")
    if request.strategy_slug != _MOMENTUM_SLUG:
        raise HTTPException(
            status_code=422,
            detail=(
                "The pipeline board is momentum-only: candidate readiness is only "
                "defined for midterm_52w_high_momentum."
            ),
        )

    directive = personal_use_directive()
    r2r_floor = fit_reward_to_risk_floor()

    try:
        regime_response = current_regime_response()
        regime_name = str(regime_response.regime)
        regime_dict = regime_response.model_dump(mode="json")
    except Exception:
        regime_name = None
        regime_dict = None
    regime_allows = _regime_allows_new_entries(regime_name)

    holdings = _sizing_holdings()

    # One universe snapshot for the whole batch (percentile gates); .SR names in
    # the batch still evaluate, just against the US compliant distribution.
    universe = analyze._market_universe(request.tickers[0] if request.tickers else "AAPL", None)

    items = [
        _board_item(
            ticker,
            universe=universe,
            holdings=holdings,
            total_capital=request.total_capital,
            caps=request.caps,
            available_cash=request.available_cash,
            regime_allows=regime_allows,
            r2r_floor=r2r_floor,
            directive=directive,
        )
        for ticker in request.tickers
    ]
    items.sort(key=_sort_key)

    ceiling_pct = portfolio_heat_ceiling()
    existing_risk = existing_open_risk(holdings)
    used_pct = (
        float(existing_risk / request.total_capital) if request.total_capital > 0 else 0.0
    )

    return PipelineBoardResponse(
        items=items,
        regime=regime_dict,
        regime_allows_new_entries=regime_allows,
        heat_ceiling_pct=ceiling_pct,
        heat_headroom_pct=ceiling_pct - used_pct,
        available_cash=request.available_cash,
        personal_use_directive=directive,
        data_as_of=utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )
