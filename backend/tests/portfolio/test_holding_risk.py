from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.src.models.portfolio import (
    Holding,
    HoldingLevels,
    LevelBlock,
    PortfolioCaps,
)
from backend.src.portfolio.holding_risk import compute_holding_risk


def _block(stop_loss: Decimal | None = Decimal("90.00"), state: str = "ok") -> LevelBlock:
    return LevelBlock(
        entry=Decimal("100.00") if stop_loss is not None else None,
        stop_loss=stop_loss,
        tighter_stop_loss=Decimal("92.00") if stop_loss is not None else None,
        take_profit=Decimal("130.00") if stop_loss is not None else None,
        risk_distance=Decimal("10.00") if stop_loss is not None else None,
        reward_distance=Decimal("30.00") if stop_loss is not None else None,
        reward_ceiling_basis="r_multiple" if stop_loss is not None else None,
        levels_state=state,  # type: ignore[arg-type]
        rationale="Neutral level context.",
        status="holding" if state == "ok" else "insufficient_data",
    )


def _holding(quantity: str = "120") -> Holding:
    return Holding(
        ticker="MSFT",
        net_quantity=Decimal(quantity),
        avg_cost=Decimal("100.00"),
        cost_basis=Decimal(quantity) * Decimal("100.00"),
        earliest_buy_date=date(2025, 8, 15),
        most_recent_buy_date=date(2025, 10, 9),
        realized_pl=Decimal("0.00"),
        status="open",
    )


def _levels(stop_loss: Decimal | None = Decimal("90.00"), state: str = "ok") -> HoldingLevels:
    return HoldingLevels(
        original_plan=_block(stop_loss=Decimal("88.00"), state="ok"),
        current_condition=_block(stop_loss=stop_loss, state=state),
    )


def test_holding_risk_recommended_actual_and_capital_at_risk(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_SIZING_CONVICTION_SIGNAL", "none")

    risk = compute_holding_risk(
        _holding("120"),
        levels=_levels(Decimal("90.00")),
        current_price=Decimal("110.00"),
        sector="Information Technology",
        total_capital=Decimal("100000"),
        caps=PortfolioCaps(per_position_cap_pct=0.50, per_sector_cap_pct=0.75),
    )

    assert risk is not None
    assert risk.recommended_shares == 100
    assert risk.recommended_value == Decimal("10000.00")
    assert risk.actual_shares == Decimal("120")
    assert risk.actual_value == Decimal("13200.00")
    assert risk.actual_capital_at_risk == Decimal("1200.00")
    assert risk.actual_capital_at_risk_pct == 0.012
    assert risk.per_trade_risk_budget == Decimal("1000.00")
    assert risk.over_risk is True
    assert risk.binding_constraint == "per_trade_budget"


def test_holding_risk_names_position_cap_when_actual_value_exceeds_cap(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_SIZING_CONVICTION_SIGNAL", "none")

    risk = compute_holding_risk(
        _holding("120"),
        levels=_levels(Decimal("99.00")),
        current_price=Decimal("110.00"),
        sector="Information Technology",
        total_capital=Decimal("100000"),
        caps=PortfolioCaps(per_position_cap_pct=0.10, per_sector_cap_pct=0.75),
    )

    assert risk is not None
    assert risk.actual_capital_at_risk == Decimal("120.00")
    assert risk.over_risk is True
    assert risk.binding_constraint == "position_cap"


def test_holding_risk_fails_open_when_modulator_missing(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_SIZING_CONVICTION_SIGNAL", "fair_value")

    risk = compute_holding_risk(
        _holding("50"),
        levels=_levels(Decimal("90.00")),
        current_price=Decimal("110.00"),
        sector="Information Technology",
        total_capital=Decimal("100000"),
        caps=PortfolioCaps(per_position_cap_pct=0.50, per_sector_cap_pct=0.75),
    )

    assert risk is not None
    assert risk.fail_open is True
    assert risk.recommended_shares == 100
    assert risk.over_risk is False


def test_holding_risk_omitted_when_not_priceable_or_insufficient_data() -> None:
    common = dict(
        holding=_holding("50"),
        current_price=Decimal("110.00"),
        sector="Information Technology",
        total_capital=Decimal("100000"),
        caps=PortfolioCaps(),
    )

    assert compute_holding_risk(levels=None, **common) is None
    assert compute_holding_risk(levels=_levels(None, "insufficient_data"), **common) is None
    assert compute_holding_risk(current_price=None, levels=_levels(), **{k: v for k, v in common.items() if k != "current_price"}) is None
