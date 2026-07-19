from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from backend.src.api import portfolio as portfolio_api
from backend.src.api.app import app
from backend.src.models.portfolio import (
    HoldingLevels,
    LevelBlock,
    PortfolioHolding,
    PortfolioTotals,
)

client = TestClient(app)

# Feature 019 (US1): the /portfolio/holdings response carries an additive
# per-holding `instruction` block and a top-level `directive_enabled` boolean.
# The Hold/Trim/Sell verb only appears under the single-owner directive
# carve-out; the neutral status_label is always present (FR-008). Absent-field
# consumers stay byte-compatible (FR-013).


def _level_block(status: str, *, levels_state: str = "ok", dist: float | None = -0.10) -> LevelBlock:
    return LevelBlock(
        levels_state=levels_state,
        rationale="Bounded levels for the current condition.",
        status=status,  # type: ignore[arg-type]
        distance_to_stop_pct=dist,
    )


def _holding(
    ticker: str,
    *,
    status: str = "holding",
    levels_state: str = "ok",
    dist: float | None = -0.10,
) -> PortfolioHolding:
    cc = _level_block(status, levels_state=levels_state, dist=dist)
    return PortfolioHolding(
        ticker=ticker,
        net_quantity=Decimal("10"),
        avg_cost=Decimal("100.00"),
        cost_basis=Decimal("1000.00"),
        earliest_buy_date="2025-01-02",
        most_recent_buy_date="2025-01-02",
        realized_pl=Decimal("0.00"),
        status="open",
        priceable=True,
        sector="Technology",
        current_price=Decimal("110.00"),
        levels=HoldingLevels(original_plan=cc, current_condition=cc),
    )


def _totals() -> PortfolioTotals:
    return PortfolioTotals(
        total_invested=Decimal("1100.00"),
        total_capital_at_risk=Decimal("50.00"),
        total_capital_at_risk_pct=0.05,
        heat_ceiling_pct=1.0,
        heat_headroom_pct=0.5,
    )


def _stub_assembly(monkeypatch, holdings, totals) -> None:
    monkeypatch.setattr(
        portfolio_api,
        "_assemble_holdings",
        lambda body: (holdings, totals, "2026-06-12T00:00:00Z", []),
    )


def test_neutral_default_when_carveout_off(monkeypatch) -> None:
    monkeypatch.setattr(portfolio_api, "card_directive_enabled", lambda: False)
    _stub_assembly(monkeypatch, [_holding("NVDA", status="stop_breached", dist=-0.01)], _totals())

    resp = client.post("/portfolio/holdings", json={"total_capital": "100000"})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["directive_enabled"] is False
    instruction = body["holdings"][0]["instruction"]
    assert instruction is not None
    assert instruction["status_label"]  # neutral status always present
    assert instruction.get("directive") is None  # no verb when carve-out off


def test_verb_present_when_carveout_on(monkeypatch) -> None:
    monkeypatch.setattr(portfolio_api, "card_directive_enabled", lambda: True)
    _stub_assembly(monkeypatch, [_holding("NVDA", status="stop_breached", dist=-0.01)], _totals())

    resp = client.post("/portfolio/holdings", json={"total_capital": "100000"})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["directive_enabled"] is True
    assert body["holdings"][0]["instruction"]["directive"] == "sell"


def test_response_is_additive_and_backcompatible(monkeypatch) -> None:
    monkeypatch.setattr(portfolio_api, "card_directive_enabled", lambda: False)
    _stub_assembly(monkeypatch, [_holding("NVDA")], _totals())

    resp = client.post("/portfolio/holdings", json={"total_capital": "100000"})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # existing fields unchanged
    assert "holdings" in body and "totals" in body and "realized_trades" in body
    assert body["data_as_of"] and body["disclaimer"]
    assert body["totals"]["total_invested"] == "1100.00"
    # a healthy holding with the carve-out off -> Hold intent, neutral label, no verb
    instruction = body["holdings"][0]["instruction"]
    assert instruction["status_label"]
    assert instruction.get("directive") is None
