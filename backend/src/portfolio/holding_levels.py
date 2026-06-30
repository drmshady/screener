from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..lib.disclaimer import utc_now_iso
from ..models.portfolio import Holding, LevelBlock, PortfolioHolding, HoldingLevels, money, pct
from ..screening.engine import build_single_ticker_snapshot
from ..strategies import midterm_52w_high_momentum as midterm


def _money_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    return money(Decimal(str(value)))


def _decimal_from_row(value: Any) -> Decimal | None:
    return _money_or_none(value)


def _status(
    *,
    levels_state: str,
    current_price: Decimal | None,
    stop_loss: Decimal | None,
    take_profit: Decimal | None,
) -> str:
    if levels_state != "ok" or current_price is None:
        return "insufficient_data"
    if stop_loss is not None and current_price <= stop_loss:
        return "stop_breached"
    if take_profit is not None and current_price >= take_profit:
        return "target_reached"
    return "holding"


def _distance(current_price: Decimal | None, level: Decimal | None) -> float | None:
    if current_price is None or current_price <= 0 or level is None:
        return None
    return float((level - current_price) / current_price)


def _block(levels: dict[str, Any], current_price: Decimal | None) -> LevelBlock:
    stop_loss = _money_or_none(levels.get("stop_loss"))
    take_profit = _money_or_none(levels.get("take_profit"))
    state = str(levels.get("levels_state") or "insufficient_data")
    return LevelBlock(
        entry=_money_or_none(levels.get("entry")),
        stop_loss=stop_loss,
        tighter_stop_loss=_money_or_none(levels.get("tighter_stop_loss")),
        take_profit=take_profit,
        risk_distance=_money_or_none(levels.get("risk_distance")),
        reward_distance=_money_or_none(levels.get("reward_distance")),
        reward_ceiling_basis=levels.get("reward_ceiling_basis"),
        bounds_applied=list(levels.get("bounds_applied") or []),
        levels_state="ok" if state == "ok" else "insufficient_data",
        rationale=str(levels.get("rationale") or "Insufficient data to derive bounded levels."),
        distance_to_stop_pct=_distance(current_price, stop_loss),
        distance_to_target_pct=_distance(current_price, take_profit),
        status=_status(
            levels_state=state,
            current_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        ),
    )


def _levels_for_row(row: Any, avg_cost: Decimal) -> dict[str, Any]:
    level_row = dict(row)
    level_row["close"] = float(avg_cost)
    return midterm.derive_levels(level_row)


def compute_holding_levels(holding: Holding) -> PortfolioHolding:
    """Attach purchase-anchored level facts to one open holding.

    The shared strategy helper is reused unchanged; only the row close is
    replaced with the owner's average cost so the level entry equals the fill
    basis for both original-plan and current-condition blocks.
    """

    try:
        original_snapshot, original_as_of, original_notes = build_single_ticker_snapshot(
            holding.ticker, as_of=holding.earliest_buy_date.isoformat()
        )
        current_snapshot, current_as_of, current_notes = build_single_ticker_snapshot(
            holding.ticker
        )
    except ValueError as exc:
        return PortfolioHolding(
            **holding.model_dump(),
            priceable=False,
            data_notes=[str(exc)],
            levels=None,
        )

    original_row = original_snapshot.iloc[0]
    current_row = current_snapshot.iloc[0]
    current_price = _decimal_from_row(current_row.get("close"))
    unrealized_pl = (
        money((current_price - holding.avg_cost) * holding.net_quantity)
        if current_price is not None
        else None
    )
    unrealized_pl_pct = pct(current_price - holding.avg_cost, holding.avg_cost) if current_price is not None else None

    original_levels = _levels_for_row(original_row, holding.avg_cost)
    current_levels = _levels_for_row(current_row, holding.avg_cost)
    notes = list(original_notes) + list(current_notes)

    return PortfolioHolding(
        **holding.model_dump(),
        priceable=True,
        sector=str(current_row.get("sector", "Unclassified")),
        current_price=current_price,
        unrealized_pl=unrealized_pl,
        unrealized_pl_pct=unrealized_pl_pct,
        data_notes=notes,
        data_as_of=max(original_as_of, current_as_of),
        levels=HoldingLevels(
            original_plan=_block(original_levels, current_price),
            current_condition=_block(current_levels, current_price),
        ),
    )


def newest_as_of(values: list[str]) -> str:
    return max(values) if values else utc_now_iso()
