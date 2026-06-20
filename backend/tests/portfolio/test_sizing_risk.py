from __future__ import annotations

from decimal import Decimal

from backend.src.models.portfolio import PortfolioCaps, SizingRequest
from backend.src.portfolio.sizing import size_position


def _request(*, entry: Decimal, stop_loss: Decimal) -> SizingRequest:
    return SizingRequest(
        candidate_ticker="NEW",
        entry=entry,
        candidate_sector="Technology",
        total_capital=Decimal("100000"),
        holdings=[],
        caps=PortfolioCaps(per_position_cap_pct=0.10, per_sector_cap_pct=0.25),
        stop_loss=stop_loss,
    )


def test_risk_target_shares_math(monkeypatch) -> None:
    # f=0.01 (default) * 100000 = 1000 risk budget; risk_per_share = 50-44 = 6
    # target_shares = floor(1000 / 6) = 166.
    response = size_position(_request(entry=Decimal("50"), stop_loss=Decimal("44")))

    assert response.risk_per_share == Decimal("6.00")
    assert response.risk_per_trade_target == Decimal("1000.00")
    assert response.suggested_shares == 166
    assert response.caps_respected is True
    assert response.binding_constraint == "risk_target"


def test_wider_stop_sizes_strictly_smaller() -> None:
    tight = size_position(_request(entry=Decimal("50"), stop_loss=Decimal("44")))
    wide = size_position(_request(entry=Decimal("50"), stop_loss=Decimal("40")))

    assert wide.suggested_shares < tight.suggested_shares


def test_deterministic_on_fixed_input() -> None:
    request = _request(entry=Decimal("50"), stop_loss=Decimal("44"))
    first = size_position(request)
    second = size_position(request)
    assert first == second
