from __future__ import annotations

from decimal import Decimal

from backend.src.models.portfolio import PortfolioCaps, SizingHolding, SizingRequest
from backend.src.portfolio.sizing import size_position


def _request(
    *, holdings: list[SizingHolding], stop_loss: Decimal | None = Decimal("44")
) -> SizingRequest:
    return SizingRequest(
        candidate_ticker="NEW",
        entry=Decimal("50"),
        candidate_sector="Technology",
        total_capital=Decimal("100000"),
        holdings=holdings,
        caps=PortfolioCaps(per_position_cap_pct=0.10, per_sector_cap_pct=0.25),
        stop_loss=stop_loss,
    )


def test_heat_ceiling_binds_and_reduces_shares(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_PORTFOLIO_HEAT_CEILING", "0.03")
    # Existing holding: value 12500, synthetic risk-to-stop = 12500 * (0.02*10) = 2500.
    # Proposed risk-target: entry 50 / stop 44 -> risk_per_share 6, budget 1000 ->
    # 166 shares -> proposed risk 996. Total 3496 > 3000 (3% of 100000) ceiling.
    # Allowed proposed risk = 3000 - 2500 = 500 -> floor(500/6) = 83 shares.
    holdings = [
        SizingHolding(
            ticker="AAA",
            shares=Decimal("125"),
            current_price=Decimal("100"),
            sector="Health Care",
        )
    ]
    response = size_position(_request(holdings=holdings))

    assert response.binding_constraint == "portfolio_heat"
    assert response.suggested_shares == 83
    assert response.suggested_shares < 166  # reduced from the risk-per-trade target
    assert response.portfolio_heat_after_pct is not None
    assert response.portfolio_heat_after_pct <= 0.03 + 1e-9


def test_empty_portfolio_heat_does_not_bind_by_default() -> None:
    response = size_position(_request(holdings=[]))

    # Default ceiling (1.0) leaves the single proposed position well under heat.
    assert response.binding_constraint == "risk_target"
    assert response.suggested_shares == 166
    assert response.portfolio_heat_after_pct is not None
    assert 0.0 < response.portfolio_heat_after_pct < 1.0


def test_heat_headroom_leaves_valid_positions_unchanged(monkeypatch) -> None:
    # A generous ceiling with a single small existing holding must not bind: the
    # result matches the plain risk-per-trade target.
    monkeypatch.setenv("SCREENER_PORTFOLIO_HEAT_CEILING", "0.50")
    holdings = [
        SizingHolding(
            ticker="BBB",
            shares=Decimal("10"),
            current_price=Decimal("100"),
            sector="Utilities",
        )
    ]
    response = size_position(_request(holdings=holdings))

    assert response.binding_constraint == "risk_target"
    assert response.suggested_shares == 166
