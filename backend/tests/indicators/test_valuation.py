"""Golden-fixture tests for the value-multiple indicators (Principle IV).

Written before backend/src/indicators/valuation.py exists; they MUST fail first.
Each yield is fundamental / market value, so higher = cheaper and a negative
numerator sorts as *least* cheap (never as artificially cheap).
"""
import math

import pytest

from backend.src.indicators.valuation import (
    book_to_market,
    cashflow_yield,
    earnings_yield,
    sales_yield,
    value_composite,
)


def test_yields_golden_fixture():
    # market_cap = 1000
    assert book_to_market(500.0, 1000.0) == pytest.approx(0.5)
    assert earnings_yield(50.0, 1000.0) == pytest.approx(0.05)
    assert cashflow_yield(80.0, 1000.0) == pytest.approx(0.08)
    assert sales_yield(900.0, 1000.0) == pytest.approx(0.9)


def test_negative_numerator_is_preserved_not_clamped():
    # A negative-earnings firm gets a negative yield (least cheap), not None/0.
    assert earnings_yield(-30.0, 1000.0) == pytest.approx(-0.03)
    # Negative book value sorts strictly below a positive-book firm.
    assert book_to_market(-100.0, 1000.0) < book_to_market(100.0, 1000.0)


def test_nonpositive_or_missing_market_cap_yields_none():
    assert earnings_yield(50.0, 0.0) is None
    assert earnings_yield(50.0, -100.0) is None
    assert book_to_market(500.0, None) is None
    assert sales_yield(None, 1000.0) is None
    assert cashflow_yield(float("nan"), 1000.0) is None


def test_value_composite_all_four_present():
    composite, n = value_composite(
        {"book_to_market": 0.9, "earnings_yield": 0.8, "cashflow_yield": 0.7, "sales_yield": 0.6}
    )
    assert composite == pytest.approx(0.75)
    assert n == 4


def test_value_composite_partial_members():
    composite, n = value_composite(
        {"book_to_market": 0.9, "earnings_yield": None, "cashflow_yield": 0.5, "sales_yield": None}
    )
    assert composite == pytest.approx(0.7)
    assert n == 2


def test_value_composite_no_members():
    composite, n = value_composite(
        {"book_to_market": None, "earnings_yield": None, "cashflow_yield": math.nan, "sales_yield": None}
    )
    assert composite is None
    assert n == 0
