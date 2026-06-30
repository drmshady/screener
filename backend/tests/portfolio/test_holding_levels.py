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


def _snapshot(close: float, atr: float = 5.0, sma_200: float = 92.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "MSFT",
                "name": "Microsoft",
                "sector": "Information Technology",
                "close": close,
                "atr": atr,
                "sma_200": sma_200,
                "contraction_low_20": 91.0,
            }
        ]
    )


def test_holding_levels_forces_entry_to_average_cost(monkeypatch) -> None:
    calls: list[str | None] = []

    def fake_snapshot(ticker: str, as_of: str | None = None):
        calls.append(as_of)
        return _snapshot(125.0 if as_of is None else 97.0), "2026-06-30T21:00:00Z", []

    monkeypatch.setattr(holding_levels, "build_single_ticker_snapshot", fake_snapshot)

    result = holding_levels.compute_holding_levels(_holding("100.00"))

    assert calls == ["2025-08-15", None]
    assert result.levels is not None
    assert result.levels.original_plan.entry == Decimal("100.00")
    assert result.levels.current_condition.entry == Decimal("100.00")


def test_holding_levels_reports_distance_and_status(monkeypatch) -> None:
    def fake_snapshot(ticker: str, as_of: str | None = None):
        return _snapshot(104.0), "2026-06-30T21:00:00Z", []

    monkeypatch.setattr(holding_levels, "build_single_ticker_snapshot", fake_snapshot)

    result = holding_levels.compute_holding_levels(_holding("100.00"))

    assert result.current_price == Decimal("104.00")
    assert result.unrealized_pl == Decimal("20.00")
    assert result.unrealized_pl_pct == 0.04
    assert result.levels is not None
    current = result.levels.current_condition
    assert current.status == "holding"
    assert current.distance_to_stop_pct is not None
    assert current.distance_to_stop_pct < 0
    assert current.distance_to_target_pct is not None


def test_holding_levels_insufficient_data_fallback(monkeypatch) -> None:
    def fake_snapshot(ticker: str, as_of: str | None = None):
        return _snapshot(100.0, atr=0.0), "2026-06-30T21:00:00Z", ["stale input"]

    monkeypatch.setattr(holding_levels, "build_single_ticker_snapshot", fake_snapshot)

    result = holding_levels.compute_holding_levels(_holding("100.00"))

    assert result.priceable is True
    assert result.data_notes == ["stale input", "stale input"]
    assert result.levels is not None
    assert result.levels.current_condition.levels_state == "insufficient_data"
    assert result.levels.current_condition.status == "insufficient_data"


def test_holding_levels_breach_and_target_status(monkeypatch) -> None:
    def stop_snapshot(ticker: str, as_of: str | None = None):
        return _snapshot(85.0), "2026-06-30T21:00:00Z", []

    monkeypatch.setattr(holding_levels, "build_single_ticker_snapshot", stop_snapshot)
    breached = holding_levels.compute_holding_levels(_holding("100.00"))
    assert breached.levels is not None
    assert breached.levels.current_condition.status == "stop_breached"

    def target_snapshot(ticker: str, as_of: str | None = None):
        return _snapshot(135.0), "2026-06-30T21:00:00Z", []

    monkeypatch.setattr(holding_levels, "build_single_ticker_snapshot", target_snapshot)
    reached = holding_levels.compute_holding_levels(_holding("100.00"))
    assert reached.levels is not None
    assert reached.levels.current_condition.status == "target_reached"


def test_holding_levels_deterministic(monkeypatch) -> None:
    def fake_snapshot(ticker: str, as_of: str | None = None):
        return _snapshot(125.0 if as_of is None else 97.0), "2026-06-30T21:00:00Z", []

    monkeypatch.setattr(holding_levels, "build_single_ticker_snapshot", fake_snapshot)

    first = holding_levels.compute_holding_levels(_holding()).model_dump()
    second = holding_levels.compute_holding_levels(_holding()).model_dump()

    assert first == second
