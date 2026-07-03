"""Feature 016 (US2): optional `available_cash` hard limit on `size_position`.

Contract: specs/016-momentum-cockpit/contracts/sizing-available-cash.md.
An absent `available_cash` is byte-identical to today; when present it caps
`suggested_shares` so `shares × entry ≤ available_cash` and reports
`binding_constraint == "available_cash"` only when cash is the tightest limit.
"""

from __future__ import annotations

from decimal import Decimal

from backend.src.models.portfolio import PortfolioCaps, SizingRequest
from backend.src.portfolio.sizing import size_position


def _caps() -> PortfolioCaps:
    return PortfolioCaps(per_position_cap_pct=0.10, per_sector_cap_pct=0.25)


def _ample_room(**overrides) -> SizingRequest:
    """Valid stop, ample cap + heat room → risk-per-trade of 166 shares."""
    base = dict(
        candidate_ticker="NEW",
        entry=Decimal("50"),
        candidate_sector="Technology",
        total_capital=Decimal("100000"),
        holdings=[],
        caps=_caps(),
        stop_loss=Decimal("44"),
    )
    base.update(overrides)
    return SizingRequest(**base)


def _dump(response) -> dict:
    # data_as_of is a wall-clock factory default; exclude it from equality.
    return response.model_dump(exclude={"data_as_of"})


def test_absent_available_cash_is_byte_identical() -> None:
    # Invariant 1: an unset available_cash produces exactly today's response,
    # and passing an explicit None is identical to omitting it.
    omitted = size_position(_ample_room())
    explicit_none = size_position(_ample_room(available_cash=None))
    assert _dump(omitted) == _dump(explicit_none)

    # Locks the documented pre-US2 result (regression fixture).
    assert omitted.suggested_shares == 166
    assert omitted.risk_per_share == Decimal("6.00")
    assert omitted.binding_constraint == "risk_target"
    assert omitted.caps_respected is True


def test_available_cash_binds_when_tightest() -> None:
    # Invariant 2: risk target is 166 shares (cost $8,300); cash of $5,000 caps
    # the position to 100 shares (cost exactly $5,000).
    response = size_position(_ample_room(available_cash=Decimal("5000")))

    assert response.suggested_shares == 100
    assert response.suggested_shares * response.suggested_position_value >= 0
    assert Decimal(response.suggested_shares) * Decimal("50") <= Decimal("5000")
    assert response.binding_constraint == "available_cash"
    assert response.caps_respected is True


def test_zero_available_cash_is_honest() -> None:
    # Invariant 3: zero cash → zero shares, cash reported (never a fabricated size).
    response = size_position(_ample_room(available_cash=Decimal("0")))

    assert response.suggested_shares == 0
    assert response.binding_constraint == "available_cash"


def test_available_cash_does_not_override_tighter_constraint() -> None:
    # Invariant 4: with stop_loss=49 the position cap binds at 200 shares
    # (cost $10,000). Ample cash ($50,000) must NOT steal the binding constraint.
    response = size_position(
        _ample_room(stop_loss=Decimal("49"), available_cash=Decimal("50000"))
    )

    assert response.suggested_shares == 200
    assert response.binding_constraint == "position_cap"


def test_available_cash_is_a_valid_binding_constraint_value() -> None:
    # Invariant 5: the binding-constraint vocabulary includes "available_cash".
    response = size_position(_ample_room(available_cash=Decimal("100")))
    assert response.binding_constraint == "available_cash"
    assert response.suggested_shares == 2  # floor(100 / 50)
