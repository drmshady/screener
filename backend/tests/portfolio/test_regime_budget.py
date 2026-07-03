from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from backend.src.models.portfolio import PortfolioCaps, SizingRequest
from backend.src.portfolio import sizing


def _request() -> SizingRequest:
    return SizingRequest(
        candidate_ticker="NEW",
        entry=Decimal("50"),
        candidate_sector="Technology",
        total_capital=Decimal("100000"),
        holdings=[],
        caps=PortfolioCaps(per_position_cap_pct=0.10, per_sector_cap_pct=0.25),
        stop_loss=Decimal("44"),
    )


def _stub_regime(regime: str):
    def _fake(*args, **kwargs):
        return SimpleNamespace(regime=regime)

    return _fake


def test_overlay_off_is_byte_identical_to_current_sizing(monkeypatch) -> None:
    # Default: SCREENER_REGIME_RISK_BUDGET unset (OFF).
    monkeypatch.setattr(sizing, "current_regime_response", _stub_regime("Trending down"))

    response = sizing.size_position(_request())

    assert response.risk_per_trade_target == Decimal("1000.00")
    assert response.suggested_shares == 166


def test_overlay_on_unfavorable_regime_scales_down_risk_budget(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_REGIME_RISK_BUDGET", "1")
    monkeypatch.setenv("SCREENER_REGIME_RISK_BUDGET_UNFAVORABLE", "0.5")
    monkeypatch.setattr(sizing, "current_regime_response", _stub_regime("Trending down"))

    response = sizing.size_position(_request())

    # Base risk budget is 1% of 100000 = 1000; unfavorable regime scales to 50%.
    assert response.risk_per_trade_target == Decimal("500.00")
    assert response.suggested_shares == 83


def test_overlay_on_favorable_regime_is_unchanged(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_REGIME_RISK_BUDGET", "1")
    monkeypatch.setenv("SCREENER_REGIME_RISK_BUDGET_UNFAVORABLE", "0.5")
    monkeypatch.setattr(sizing, "current_regime_response", _stub_regime("Trending up"))

    response = sizing.size_position(_request())

    assert response.risk_per_trade_target == Decimal("1000.00")
    assert response.suggested_shares == 166


def test_overlay_on_but_regime_unavailable_fails_open_to_1x(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_REGIME_RISK_BUDGET", "1")

    def _raise(*args, **kwargs):
        raise RuntimeError("SPY data unavailable")

    monkeypatch.setattr(sizing, "current_regime_response", _raise)

    response = sizing.size_position(_request())

    assert response.risk_per_trade_target == Decimal("1000.00")
    assert response.suggested_shares == 166
