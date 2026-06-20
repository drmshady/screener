from __future__ import annotations

from decimal import Decimal

from backend.src.models.portfolio import PortfolioCaps, SizingRequest
from backend.src.portfolio.sizing import size_position


def _request(**overrides) -> SizingRequest:
    base = dict(
        candidate_ticker="NEW",
        entry=Decimal("50"),
        candidate_sector="Technology",
        total_capital=Decimal("1000000"),
        holdings=[],
        caps=PortfolioCaps(per_position_cap_pct=0.50, per_sector_cap_pct=0.75),
        stop_loss=Decimal("44"),
    )
    base.update(overrides)
    return SizingRequest(**base)


def test_fair_value_deeper_discount_sizes_at_least_as_large(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_SIZING_CONVICTION_SIGNAL", "fair_value")

    deep_discount = size_position(
        _request(fair_value=Decimal("100"), fair_value_trust_flag="trusted")
    )
    small_margin = size_position(
        _request(fair_value=Decimal("60"), fair_value_trust_flag="trusted")
    )

    assert deep_discount.suggested_shares >= small_margin.suggested_shares
    assert deep_discount.conviction_used is True
    assert deep_discount.conviction_signal == "fair_value"
    assert deep_discount.binding_constraint in {"conviction", "position_cap", "sector_cap"}


def test_fair_value_missing_or_untrusted_fails_open(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_SIZING_CONVICTION_SIGNAL", "fair_value")

    untrusted = size_position(
        _request(fair_value=Decimal("100"), fair_value_trust_flag="unavailable")
    )
    missing = size_position(_request())

    for response in (untrusted, missing):
        assert response.conviction_used is False
        assert response.caps_respected is True
        assert response.binding_constraint == "risk_target"
        # Risk-based-within-caps baseline: floor(0.01*1000000/6) = 1666
        assert response.suggested_shares == 1666


def test_inverse_vol_lower_volatility_sizes_at_least_as_large(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_SIZING_CONVICTION_SIGNAL", "inverse_vol")

    low_vol = size_position(_request(volatility=0.01))
    high_vol = size_position(_request(volatility=0.04))

    assert low_vol.suggested_shares >= high_vol.suggested_shares
    assert low_vol.conviction_used is True
    assert low_vol.conviction_signal == "inverse_vol"


def test_strategy_rank_better_rank_sizes_at_least_as_large(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_SIZING_CONVICTION_SIGNAL", "strategy_rank")

    top_rank = size_position(_request(strategy_rank=1))
    low_rank = size_position(_request(strategy_rank=10))

    assert top_rank.suggested_shares >= low_rank.suggested_shares
    assert top_rank.conviction_used is True
    assert top_rank.conviction_signal == "strategy_rank"


def test_none_signal_is_the_honest_baseline_no_modulation(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_SIZING_CONVICTION_SIGNAL", "none")

    with_fair_value = size_position(
        _request(fair_value=Decimal("100"), fair_value_trust_flag="trusted")
    )
    without = size_position(_request())

    assert with_fair_value.suggested_shares == without.suggested_shares
    assert with_fair_value.conviction_used is False
    assert with_fair_value.conviction_signal == "none"


def test_deterministic_on_fixed_input(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_SIZING_CONVICTION_SIGNAL", "fair_value")
    request = _request(fair_value=Decimal("100"), fair_value_trust_flag="trusted")
    first = size_position(request)
    second = size_position(request)
    assert first == second


def test_rationale_is_zero_directive_and_names_binding_constraint(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_SIZING_CONVICTION_SIGNAL", "fair_value")
    response = size_position(
        _request(fair_value=Decimal("100"), fair_value_trust_flag="trusted")
    )

    lowered = response.reasoning.lower()
    for banned in ("buy", "sell", "recommended", "strong buy"):
        assert banned not in lowered
    assert response.binding_constraint is not None
    assert response.binding_constraint.replace("_", " ") in lowered or (
        response.binding_constraint == "conviction" and "conviction" in lowered
    )
