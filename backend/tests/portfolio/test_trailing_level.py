from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
from backend.src.models.portfolio import Holding
from backend.src.portfolio import holding_levels


def _holding(avg_cost: str = "100.00") -> Holding:
    return Holding(
        ticker="MSFT",
        net_quantity=Decimal("5"),
        avg_cost=Decimal(avg_cost),
        cost_basis=Decimal(avg_cost) * Decimal("5"),
        earliest_buy_date=date(2025, 8, 15),
        most_recent_buy_date=date(2025, 10, 9),
        realized_pl=Decimal("0.00"),
        status="open",
    )


def _snapshot(
    close: float,
    *,
    chandelier_exit: float | None,
    atr: float = 5.0,
    sma_200: float = 120.0,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "MSFT",
                "name": "Microsoft",
                "sector": "Information Technology",
                "close": close,
                "atr": atr,
                "sma_200": sma_200,
                "contraction_low_20": sma_200 - 2.0,
                "chandelier_exit": chandelier_exit,
            }
        ]
    )


def _compute(monkeypatch, close: float, chandelier_exit: float | None, avg_cost: str = "100.00"):
    def fake_snapshot(ticker: str, as_of: str | None = None):
        return _snapshot(close, chandelier_exit=chandelier_exit), "2026-06-30T21:00:00Z", []

    monkeypatch.setattr(holding_levels, "build_single_ticker_snapshot", fake_snapshot)
    return holding_levels.compute_holding_levels(_holding(avg_cost))


def test_winner_trailing_stop_sits_above_cost_and_is_not_looser(monkeypatch) -> None:
    result = _compute(monkeypatch, close=150.0, chandelier_exit=138.0)

    assert result.levels is not None
    trailing = result.levels.trailing
    assert trailing is not None
    # (a) above the average cost, protecting gains, and never looser than the
    # cost-anchored current-condition stop (SC-004).
    assert trailing.stop_loss is not None
    assert trailing.stop_loss > Decimal("100.00")
    current_stop = result.levels.current_condition.stop_loss
    assert current_stop is not None
    assert trailing.stop_loss >= current_stop
    assert trailing.status == "gains_protected"
    assert trailing.entry == Decimal("150.00")  # current-price basis, not avg cost
    assert trailing.take_profit is None
    assert trailing.distance_to_stop_pct is not None and trailing.distance_to_stop_pct < 0


def test_trailing_rationale_is_zero_directive(monkeypatch) -> None:
    result = _compute(monkeypatch, close=150.0, chandelier_exit=138.0)

    assert result.levels is not None and result.levels.trailing is not None
    rationale = result.levels.trailing.rationale.lower()
    for banned in ("buy", "sell", "recommend", "strong buy"):
        assert banned not in rationale
    assert "protect" in rationale


def test_trailing_absent_when_price_at_or_below_cost(monkeypatch) -> None:
    # Price below cost: no unrealized gains to protect -> no fabricated level.
    result = _compute(monkeypatch, close=95.0, chandelier_exit=90.0)
    assert result.levels is not None
    assert result.levels.trailing is None


def test_trailing_absent_when_chandelier_missing(monkeypatch) -> None:
    result = _compute(monkeypatch, close=150.0, chandelier_exit=None)
    assert result.levels is not None
    assert result.levels.trailing is None
