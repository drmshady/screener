from __future__ import annotations

from decimal import Decimal

from backend.src.models.portfolio import PortfolioCaps, SizingRequest
from backend.src.portfolio.sizing import size_position


def _valid_stop_ample_room() -> SizingRequest:
    return SizingRequest(
        candidate_ticker="NEW",
        entry=Decimal("50"),
        candidate_sector="Technology",
        total_capital=Decimal("100000"),
        holdings=[],
        caps=PortfolioCaps(per_position_cap_pct=0.10, per_sector_cap_pct=0.25),
        stop_loss=Decimal("44"),
    )


def test_valid_stop_ample_room_matches_risk_per_trade() -> None:
    # US4 AS-3 / SC-008: with a valid stop and ample cap + heat room, the output
    # is exactly the pre-US4 risk-per-trade result (no regression).
    response = size_position(_valid_stop_ample_room())

    assert response.suggested_shares == 166
    assert response.risk_per_share == Decimal("6.00")
    assert response.risk_per_trade_target == Decimal("1000.00")
    assert response.binding_constraint == "risk_target"
    assert response.caps_respected is True
    # The new safety signals are inert on a healthy request.
    assert response.conservative_fallback is False


def test_new_fields_are_additive_and_optional() -> None:
    response = size_position(_valid_stop_ample_room())

    # Additive fields exist but do not disturb the core sizing result.
    assert response.portfolio_heat_after_pct is not None
    assert response.reward_to_risk is None  # no target supplied in the request
