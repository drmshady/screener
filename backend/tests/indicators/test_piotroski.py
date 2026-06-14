"""Golden-fixture tests for the Piotroski (2000) F-Score (Principle IV).

Written before backend/src/indicators/piotroski.py exists; they MUST fail first.
A signal whose inputs are missing is scored as None (no point awarded) and
decrements the evaluable count — it is never a silent pass.
"""
from backend.src.indicators.piotroski import FundamentalsYear, f_score


def _perfect_pair():
    prior = FundamentalsYear(
        net_income=80.0, total_assets=1000.0, operating_cf=90.0, long_term_debt=200.0,
        current_assets=400.0, current_liabilities=200.0, shares_outstanding=100.0,
        gross_profit=300.0, revenue=900.0,
    )
    current = FundamentalsYear(
        net_income=120.0, total_assets=1100.0, operating_cf=150.0, long_term_debt=150.0,
        current_assets=500.0, current_liabilities=200.0, shares_outstanding=100.0,
        gross_profit=420.0, revenue=1000.0,
    )
    return current, prior


def test_f_score_perfect_nine():
    current, prior = _perfect_pair()
    score, evaluable, signals = f_score(current, prior)
    assert score == 9
    assert evaluable == 9
    assert all(v == 1 for v in signals.values())


def test_missing_inputs_decrement_evaluable_and_award_no_point():
    current, prior = _perfect_pair()
    # Drop two current inputs: gross_profit (margin signal) and shares (dilution signal).
    current.gross_profit = None
    current.shares_outstanding = None
    score, evaluable, signals = f_score(current, prior)
    assert signals["gross_margin_up"] is None
    assert signals["no_dilution"] is None
    assert evaluable == 7
    assert score == 7  # the other seven still pass; missing ones add nothing


def test_failing_signal_scores_zero_not_none():
    current, prior = _perfect_pair()
    current.net_income = -50.0  # ROA now negative
    score, evaluable, signals = f_score(current, prior)
    assert signals["roa_positive"] == 0       # evaluated and failed, not missing
    assert signals["roa_improved"] == 0       # ΔROA negative
    assert signals["accruals_ok"] == 1        # cfo 150 > ni -50
    assert evaluable == 9
    assert score == 7
