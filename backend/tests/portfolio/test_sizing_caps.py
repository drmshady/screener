from __future__ import annotations

from decimal import Decimal

from backend.src.models.portfolio import PortfolioCaps, SizingRequest
from backend.src.portfolio.sizing import size_position


def test_cap_binds_tighter_than_risk_target() -> None:
    # risk_budget = 0.01*100000 = 1000; risk_per_share = 50-49 = 1 -> risk target
    # = 1000 shares -> trade value 50000 = 50% of capital, far above the 10%
    # position cap (10000 -> 200 shares). The cap must win.
    request = SizingRequest(
        candidate_ticker="TIGHT",
        entry=Decimal("50"),
        candidate_sector="Technology",
        total_capital=Decimal("100000"),
        holdings=[],
        caps=PortfolioCaps(per_position_cap_pct=0.10, per_sector_cap_pct=0.25),
        stop_loss=Decimal("49"),
    )

    response = size_position(request)

    assert response.suggested_shares == 200
    assert response.caps_respected is True
    assert response.binding_constraint == "position_cap"
    assert response.resulting_position_pct_of_capital <= 0.10


def test_no_suggestion_breaches_position_or_sector_cap_sampled() -> None:
    caps = PortfolioCaps(per_position_cap_pct=0.10, per_sector_cap_pct=0.25)
    total_capital = Decimal("100000")

    for index in range(50):
        entry = Decimal(10 + (index % 23) * 7)
        stop_loss = entry - Decimal(1 + (index % 9))
        request = SizingRequest(
            candidate_ticker=f"CAP{index}",
            entry=entry,
            candidate_sector="Technology",
            total_capital=total_capital,
            holdings=[],
            caps=caps,
            stop_loss=stop_loss,
        )
        response = size_position(request)

        assert response.caps_respected is True
        assert response.resulting_position_pct_of_capital <= caps.per_position_cap_pct
        assert response.resulting_sector_pct_of_capital <= caps.per_sector_cap_pct


def test_existing_zero_room_cap_breach_branch_preserved() -> None:
    # No stop_loss -> legacy cap-fill path; the pre-existing "cannot size without
    # breaching cap" branch must still fire unmodified.
    response = size_position(
        SizingRequest(
            candidate_ticker="BIG",
            entry=Decimal("501"),
            candidate_sector="Technology",
            total_capital=Decimal("5000"),
            holdings=[],
            caps=PortfolioCaps(per_position_cap_pct=0.10, per_sector_cap_pct=0.25),
        )
    )

    assert response.caps_respected is False
    assert response.suggested_shares == 0
    assert "Cannot size without breaching cap" in response.reasoning
