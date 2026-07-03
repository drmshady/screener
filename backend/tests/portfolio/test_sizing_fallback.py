from __future__ import annotations

from decimal import Decimal

from backend.src.models.portfolio import PortfolioCaps, SizingRequest
from backend.src.portfolio.sizing import size_position


def _no_stop_request(
    *, entry: Decimal = Decimal("50"), total_capital: Decimal = Decimal("100000")
) -> SizingRequest:
    return SizingRequest(
        candidate_ticker="NEW",
        entry=entry,
        candidate_sector="Technology",
        total_capital=total_capital,
        holdings=[],
        caps=PortfolioCaps(per_position_cap_pct=0.10, per_sector_cap_pct=0.25),
        # No stop_loss -> conservative fallback branch (US4/FR-009).
    )


def test_missing_stop_sizes_smaller_than_legacy_cap_fill() -> None:
    # entry 50, capital 100000. Legacy cap-fill would fill the 10% position cap
    # (10000 -> 200 shares). The conservative fallback sizes a small position:
    # synthetic stop = 50 * 0.02 * 10 = 10; risk budget = 0.01*100000 = 1000;
    # shares = floor(1000 / 10) = 100 (strictly smaller than 200).
    response = size_position(_no_stop_request())

    assert response.conservative_fallback is True
    assert response.binding_constraint == "conservative_fallback"
    assert response.suggested_shares == 100
    assert response.suggested_shares < 200  # strictly smaller than legacy cap-fill
    assert "conservative" in response.reasoning.lower()


def test_conservative_fallback_reasoning_is_zero_directive() -> None:
    lowered = size_position(_no_stop_request()).reasoning.lower()
    for banned in ("buy", "sell", "recommended", "strong buy"):
        assert banned not in lowered


def test_conservative_fallback_is_deterministic() -> None:
    request = _no_stop_request()
    first = size_position(request)
    second = size_position(request)
    assert first.model_dump(exclude={"data_as_of"}) == second.model_dump(
        exclude={"data_as_of"}
    )
