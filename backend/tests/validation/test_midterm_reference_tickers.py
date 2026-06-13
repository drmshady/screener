from __future__ import annotations

import pytest


def test_reference_tickers_are_resolved(reference_tickers) -> None:
    assert len(reference_tickers) >= 8
    for ticker in ["EA", "BELFB", "ASYS", "AMAT", "ROST", "WYY"]:
        assert ticker in reference_tickers


def test_reference_ticker_pass_fail_outcomes_match(reference_tickers) -> None:
    """Every reference ticker's pass/fail verdict matches the hand oracle.

    This is the FR-006 correctness floor and it holds today: EA/BELFB/ASYS/
    AMAT/ROST are candidates; WYY and the proximity/quality probes are rejected.
    """
    outcome_mismatches = {
        ticker: data
        for ticker, data in reference_tickers.items()
        if data["expected"] != data["actual"]
    }
    assert not outcome_mismatches, f"pass/fail oracle mismatch: {outcome_mismatches}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "F-001: WYY is rejected at the quality gate before the asset_growth gate "
        "its oracle expects. Outcome (fail) is correct; the rejection *reason* "
        "differs. Flip this to a hard assertion once the gate-order/data is fixed."
    ),
)
def test_reference_ticker_rejection_gates_match(reference_tickers) -> None:
    """The gate that rejects each expected-fail ticker matches the oracle.

    Currently xfails because WYY dies at quality, not asset_growth (F-001).
    """
    gate_mismatches = {
        ticker: (data["expected_gate"], data["actual_gate"])
        for ticker, data in reference_tickers.items()
        if data["expected"] == "fail"
        and data["expected_gate"] is not None
        and data["expected_gate"] != data["actual_gate"]
    }
    assert not gate_mismatches, f"rejection-gate mismatch: {gate_mismatches}"
