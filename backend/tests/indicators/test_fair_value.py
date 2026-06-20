from __future__ import annotations

from datetime import date

from backend.src.indicators.fair_value import estimate_fair_value, graham_number


def test_graham_number_golden_value() -> None:
    # sqrt(22.5 * EPS * BVPS) = sqrt(22.5 * 5 * 50) = sqrt(5625) = 75.0
    assert graham_number(eps=5.0, bvps=50.0) == 75.0


def test_graham_number_none_for_non_positive_inputs() -> None:
    assert graham_number(eps=-1.0, bvps=50.0) is None
    assert graham_number(eps=5.0, bvps=0.0) is None
    assert graham_number(eps=None, bvps=50.0) is None


def test_intrinsic_model_golden_fixture_is_trusted() -> None:
    # close=100, book_to_market=0.5 -> BVPS=50; earnings_yield=0.05 -> EPS=5
    # Graham number = sqrt(22.5*5*50) = 75.0
    result = estimate_fair_value(
        close=100.0,
        book_to_market=0.5,
        earnings_yield=0.05,
        period_end="2024-06-30",
        as_of=date(2024, 9, 1),
        basis="intrinsic_model",
    )
    assert result["fair_value"] == 75.0
    assert result["basis"] == "intrinsic_model"
    assert result["source_as_of"] == "2024-06-30"
    assert result["trust_flag"] == "trusted"
    assert result["margin_of_safety"] == (75.0 - 100.0) / 75.0
    assert "Graham" in result["provenance"]


def test_valuation_yields_basis_uses_book_value_per_share() -> None:
    result = estimate_fair_value(
        close=100.0,
        book_to_market=0.5,
        earnings_yield=0.05,
        period_end="2024-06-30",
        as_of=date(2024, 9, 1),
        basis="valuation_yields",
    )
    assert result["fair_value"] == 50.0
    assert result["basis"] == "valuation_yields"
    assert result["trust_flag"] == "trusted"


def test_missing_inputs_yield_unavailable() -> None:
    result = estimate_fair_value(
        close=100.0,
        book_to_market=None,
        earnings_yield=0.05,
        period_end="2024-06-30",
        as_of=date(2024, 9, 1),
    )
    assert result["fair_value"] is None
    assert result["trust_flag"] == "unavailable"
    assert result["margin_of_safety"] is None


def test_negative_earnings_yields_unavailable_for_intrinsic_model() -> None:
    result = estimate_fair_value(
        close=100.0,
        book_to_market=0.5,
        earnings_yield=-0.05,
        period_end="2024-06-30",
        as_of=date(2024, 9, 1),
        basis="intrinsic_model",
    )
    assert result["fair_value"] is None
    assert result["trust_flag"] == "unavailable"


def test_stale_period_end_is_not_trusted() -> None:
    result = estimate_fair_value(
        close=100.0,
        book_to_market=0.5,
        earnings_yield=0.05,
        period_end="2022-01-01",
        as_of=date(2024, 9, 1),
        basis="intrinsic_model",
        max_stale_days=450,
    )
    assert result["fair_value"] == 75.0
    assert result["trust_flag"] == "stale"


def test_implausible_estimate_relative_to_price_is_out_of_range() -> None:
    # BVPS = 0.001*100 = 0.1, EPS = 0.001*100 = 0.1 -> Graham = sqrt(22.5*0.1*0.1)
    # = sqrt(0.225) ~= 0.474, far below the 5% (5.0) plausibility floor at close=100.
    result = estimate_fair_value(
        close=100.0,
        book_to_market=0.001,
        earnings_yield=0.001,
        period_end="2024-06-30",
        as_of=date(2024, 9, 1),
        basis="intrinsic_model",
    )
    assert result["trust_flag"] == "out_of_range"


def test_deterministic_on_fixed_input() -> None:
    kwargs = dict(
        close=100.0,
        book_to_market=0.5,
        earnings_yield=0.05,
        period_end="2024-06-30",
        as_of=date(2024, 9, 1),
        basis="intrinsic_model",
    )
    assert estimate_fair_value(**kwargs) == estimate_fair_value(**kwargs)
