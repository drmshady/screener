from __future__ import annotations

from decimal import Decimal

from ..lib import flags
from ..models.portfolio import (
    Holding,
    HoldingLevels,
    HoldingRisk,
    PortfolioCaps,
    SizingRequest,
    money,
    pct,
)
from .sizing import size_position


def _actual_capital_at_risk(
    *, shares: Decimal, entry: Decimal, stop_loss: Decimal
) -> Decimal:
    return money(max(Decimal("0"), shares * (entry - stop_loss)))


def _actual_value(*, shares: Decimal, current_price: Decimal) -> Decimal:
    return money(shares * current_price)


def _binding_constraint(
    *,
    actual_capital_at_risk: Decimal,
    per_trade_risk_budget: Decimal,
    actual_value: Decimal,
    sector_value: Decimal,
    total_capital: Decimal,
    caps: PortfolioCaps,
) -> str | None:
    if actual_capital_at_risk > per_trade_risk_budget:
        return "per_trade_budget"
    if pct(actual_value, total_capital) > caps.per_position_cap_pct:
        return "position_cap"
    if pct(sector_value, total_capital) > caps.per_sector_cap_pct:
        return "sector_cap"
    return None


def compute_holding_risk(
    holding: Holding,
    *,
    levels: HoldingLevels | None,
    current_price: Decimal | None,
    sector: str,
    total_capital: Decimal,
    caps: PortfolioCaps,
    sector_value: Decimal | None = None,
) -> HoldingRisk | None:
    """Attach actual-vs-sized risk facts for a priceable open holding.

    The recommendation comes from the existing `size_position` backbone. This
    module adds only the owner-held actual size, capital-at-risk, and over-risk
    read-out for the imported holding.
    """

    if current_price is None or levels is None:
        return None
    current = levels.current_condition
    if current.levels_state != "ok" or current.stop_loss is None:
        return None

    sizing = size_position(
        SizingRequest(
            candidate_ticker=holding.ticker,
            entry=holding.avg_cost,
            candidate_sector=sector,
            total_capital=total_capital,
            holdings=[],
            caps=caps,
            stop_loss=current.stop_loss,
        )
    )
    actual_value = _actual_value(
        shares=holding.net_quantity, current_price=current_price
    )
    actual_capital_at_risk = _actual_capital_at_risk(
        shares=holding.net_quantity,
        entry=holding.avg_cost,
        stop_loss=current.stop_loss,
    )
    per_trade_risk_budget = money(
        total_capital * Decimal(str(flags.risk_per_trade_fraction()))
    )
    binding_constraint = _binding_constraint(
        actual_capital_at_risk=actual_capital_at_risk,
        per_trade_risk_budget=per_trade_risk_budget,
        actual_value=actual_value,
        sector_value=sector_value if sector_value is not None else actual_value,
        total_capital=total_capital,
        caps=caps,
    )

    return HoldingRisk(
        recommended_shares=sizing.suggested_shares,
        recommended_value=money(sizing.suggested_position_value),
        actual_shares=holding.net_quantity,
        actual_value=actual_value,
        actual_capital_at_risk=actual_capital_at_risk,
        actual_capital_at_risk_pct=pct(actual_capital_at_risk, total_capital),
        per_trade_risk_budget=per_trade_risk_budget,
        over_risk=binding_constraint is not None,
        binding_constraint=binding_constraint,  # type: ignore[arg-type]
        sizing_reasoning=sizing.reasoning,
        fail_open=sizing.conviction_signal != "none" and not sizing.conviction_used,
    )
