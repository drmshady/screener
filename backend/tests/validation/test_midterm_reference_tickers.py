from __future__ import annotations


def test_reference_tickers_are_resolved(reference_tickers) -> None:
    assert len(reference_tickers) >= 8
    for ticker in ["EA", "BELFB", "ASYS", "AMAT", "ROST", "WYY"]:
        assert ticker in reference_tickers


def test_reference_ticker_pass_fail_outcomes_match(reference_tickers) -> None:
    """Every reference ticker's pass/fail verdict matches the hand oracle.

    FR-006 correctness floor: EA/BELFB/ASYS/AMAT/ROST are candidates; WYY and
    the proximity/quality probes are rejected.
    """
    outcome_mismatches = {
        ticker: data
        for ticker, data in reference_tickers.items()
        if data["expected"] != data["actual"]
    }
    assert not outcome_mismatches, f"pass/fail oracle mismatch: {outcome_mismatches}"


def test_reference_ticker_rejection_gates_match(reference_tickers) -> None:
    """The gate that rejects each expected-fail ticker matches the oracle.

    WYY is expected at the *quality* gate (D/E ~5.9 trips quality before the
    asset-growth gate it also fails) — the strategy applies gates in the
    declared order, so quality-first is correct (F-001 resolved: the oracle's
    expectation was corrected, the strategy was already right).
    """
    gate_mismatches = {
        ticker: (data["expected_gate"], data["actual_gate"])
        for ticker, data in reference_tickers.items()
        if data["expected"] == "fail"
        and data["expected_gate"] is not None
        and data["expected_gate"] != data["actual_gate"]
    }
    assert not gate_mismatches, f"rejection-gate mismatch: {gate_mismatches}"
