"""Feature 018 T014 (US1) — portfolio-section assemble + attention ordering.

Pure tests over constructed holdings/totals (no snapshot dependency): they assert
the `PortfolioStatusSection` mapping (totals/P&L/heat, `is_empty`) and the
deterministic attention precedence (risk/heat breach → stop proximity → stage
change), tie-broken by `(severity desc, ticker asc)`.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.src.brief import assemble
from backend.src.models.brief import AttentionReason
from backend.src.models.portfolio import (
    HoldingLevels,
    HoldingRisk,
    LevelBlock,
    PortfolioHolding,
    PortfolioTotals,
)


def _level(status: str, *, stop: str | None = "90", distance: float | None = None) -> LevelBlock:
    return LevelBlock(
        stop_loss=Decimal(stop) if stop is not None else None,
        levels_state="ok" if stop is not None else "insufficient_data",
        rationale="test",
        distance_to_stop_pct=distance,
        status=status,  # type: ignore[arg-type]
    )


def _holding(
    ticker: str,
    *,
    sector: str = "Tech",
    current_price: str = "100",
    current_status: str = "holding",
    distance: float | None = None,
    over_risk: bool = False,
    risk_pct: float = 0.0,
    car: str = "0",
) -> PortfolioHolding:
    levels = HoldingLevels(
        original_plan=_level("holding"),
        current_condition=_level(current_status, distance=distance),
    )
    risk = None
    if over_risk or risk_pct:
        risk = HoldingRisk(
            recommended_shares=1,
            recommended_value=Decimal("100"),
            actual_shares=Decimal("10"),
            actual_value=Decimal("1000"),
            actual_capital_at_risk=Decimal(car),
            actual_capital_at_risk_pct=risk_pct,
            per_trade_risk_budget=Decimal("50"),
            over_risk=over_risk,
            binding_constraint="per_trade_budget" if over_risk else None,
            sizing_reasoning="test",
        )
    return PortfolioHolding(
        ticker=ticker,
        net_quantity=Decimal("10"),
        avg_cost=Decimal("95"),
        cost_basis=Decimal("950"),
        earliest_buy_date=date(2025, 1, 1),
        most_recent_buy_date=date(2025, 1, 1),
        realized_pl=Decimal("0"),
        status="open",
        sector=sector,
        current_price=Decimal(current_price),
        unrealized_pl=Decimal("50"),
        unrealized_pl_pct=0.05,
        levels=levels,
        risk=risk,
    )


def _totals(**kw) -> PortfolioTotals:
    base = dict(total_invested=Decimal("1000"), heat_ceiling_pct=1.0, heat_headroom_pct=0.5)
    base.update(kw)
    return PortfolioTotals(**base)


def test_empty_portfolio_is_flagged() -> None:
    section = assemble.build_portfolio_section([], _totals(total_invested=Decimal("0")), {})
    assert section.is_empty is True
    assert section.holdings == []
    assert section.attention == []


def test_section_maps_totals_and_holdings() -> None:
    holdings = [_holding("AAA"), _holding("BBB")]
    totals = _totals(
        total_invested=Decimal("2000"),
        realized_pnl=Decimal("120"),
        unrealized_pnl=Decimal("80"),
        total_pnl=Decimal("200"),
        win_rate=0.6,
        total_capital_at_risk_pct=0.2,
        heat_ceiling_pct=1.0,
        heat_headroom_pct=0.8,
    )
    section = assemble.build_portfolio_section(holdings, totals, {})
    assert section.is_empty is False
    assert section.total_value == Decimal("2000")
    assert section.total_pnl == Decimal("200")
    assert section.win_rate == 0.6
    assert section.heat_headroom_pct == 0.8
    assert [h.ticker for h in section.holdings] == ["AAA", "BBB"]


def test_attention_precedence_and_tiebreak() -> None:
    holdings = [
        _holding("STOPFAR", current_status="holding", distance=0.20),  # not near → no attn
        _holding("STOPNEAR", current_status="holding", distance=0.02),  # stop proximity
        _holding("RISK", over_risk=True, risk_pct=0.3, car="300"),      # risk breach
        _holding("TARGET", current_status="target_reached"),            # stage change
    ]
    section = assemble.build_portfolio_section(holdings, _totals(), {})
    codes = [(a.ticker, a.reason_code) for a in section.attention]
    # risk_breach first, then stop_proximity, then stage_change; STOPFAR absent.
    assert codes == [
        ("RISK", AttentionReason.RISK_BREACH),
        ("STOPNEAR", AttentionReason.STOP_PROXIMITY),
        ("TARGET", AttentionReason.STAGE_CHANGE),
    ]


def test_heat_breach_flags_top_risk_holding() -> None:
    holdings = [
        _holding("SMALL", over_risk=True, risk_pct=0.1, car="100"),
        _holding("BIG", over_risk=True, risk_pct=0.4, car="400"),
    ]
    # Aggregate heat over ceiling ⇒ the largest-risk holding is a heat_breach.
    section = assemble.build_portfolio_section(holdings, _totals(heat_headroom_pct=-0.1), {})
    top = section.attention[0]
    assert top.ticker == "BIG"
    assert top.reason_code is AttentionReason.HEAT_BREACH


def test_attention_is_deterministic() -> None:
    holdings = [_holding("RISK", over_risk=True, risk_pct=0.3, car="300")]
    a = assemble.build_portfolio_section(holdings, _totals(), {})
    b = assemble.build_portfolio_section(holdings, _totals(), {})
    assert [x.model_dump() for x in a.attention] == [x.model_dump() for x in b.attention]
