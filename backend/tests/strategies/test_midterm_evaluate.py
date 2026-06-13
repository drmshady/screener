import pandas as pd
from backend.src.strategies.midterm_52w_high_momentum import (
    evaluate,
    evaluation_context,
)


def _base_row(**overrides):
    row = {
        "ticker": "PASS",
        "name": "Pass Co",
        "sector": "Technology",
        "close": 100.0,
        "52w_high": 102.0,
        "dist_to_high": 0.02,
        "sma_200": 80.0,
        "volume_ratio_recent": 1.1,
        "fcf_ttm": 10_000_000.0,
        "debt_to_equity": 0.4,
        "gp_to_assets": 0.6,
        "asset_growth": 0.02,
        "_gp_pass": True,
        "_ag_pass": True,
    }
    row.update(overrides)
    return row


def _statuses(row, *, single_ticker: bool = False):
    frame = pd.DataFrame([row])
    context = evaluation_context(
        frame,
        strong_sectors=None if single_ticker else {"Technology"},
        vol_col="volume_ratio_recent",
        gp_applied=not single_ticker,
        ag_applied=not single_ticker,
        single_ticker=single_ticker,
    )
    return {gate["gate"]: gate["status"] for gate in evaluate(row, context)}


def test_evaluate_reports_all_passes_for_passing_fixture():
    statuses = _statuses(_base_row())

    assert statuses["52-week-high proximity"] == "pass"
    assert statuses["Trend (above 200-day SMA)"] == "pass"
    assert statuses["Volume confirmation"] == "pass"
    assert statuses["Sector strength"] == "pass"
    assert statuses["Quality (leverage + cash flow)"] == "pass"
    assert statuses["Gross profitability"] == "pass"
    assert statuses["Low asset growth"] == "pass"


def test_evaluate_reports_each_individual_gate_failure():
    cases = [
        ("52-week-high proximity", _base_row(dist_to_high=0.20)),
        ("Trend (above 200-day SMA)", _base_row(sma_200=120.0)),
        ("Volume confirmation", _base_row(volume_ratio_recent=0.2)),
        ("Sector strength", _base_row(sector="Utilities")),
        ("Quality (leverage + cash flow)", _base_row(debt_to_equity=2.0)),
        ("Quality (leverage + cash flow)", _base_row(fcf_ttm=-1.0)),
        ("Gross profitability", _base_row(_gp_pass=False, gp_to_assets=0.1)),
        ("Low asset growth", _base_row(_ag_pass=False, asset_growth=0.5)),
    ]

    # Default (hard) mode: every gate reports pass/fail. (In tiered mode the
    # non-proximity gates would surface as 'warn' — covered separately.)
    for gate, row in cases:
        assert _statuses(row)[gate] == "fail"


def test_tiered_mode_warns_on_soft_gates_but_fails_proximity(monkeypatch):
    # Decision 7 (opt-in): SCREENER_GATE_MODE=tiered keeps only the 52-week-high
    # proximity gate hard; every other failing gate surfaces as a 'warn'.
    monkeypatch.setenv("SCREENER_GATE_MODE", "tiered")
    cases = [
        ("52-week-high proximity", _base_row(dist_to_high=0.20), "fail"),
        ("Trend (above 200-day SMA)", _base_row(sma_200=120.0), "warn"),
        ("Volume confirmation", _base_row(volume_ratio_recent=0.2), "warn"),
        ("Quality (leverage + cash flow)", _base_row(debt_to_equity=2.0), "warn"),
        ("Gross profitability", _base_row(_gp_pass=False, gp_to_assets=0.1), "warn"),
        ("Low asset growth", _base_row(_ag_pass=False, asset_growth=0.5), "warn"),
    ]
    for gate, row, expected in cases:
        assert _statuses(row)[gate] == expected, gate


def test_evaluate_reports_missing_data_and_universe_gates_as_skipped():
    statuses = _statuses(
        _base_row(sma_200=None, volume_ratio_recent=None, debt_to_equity=None),
        single_ticker=True,
    )

    assert statuses["Trend (above 200-day SMA)"] == "skipped"
    assert statuses["Volume confirmation"] == "skipped"
    assert statuses["Quality (leverage + cash flow)"] == "skipped"
    assert statuses["Sector strength"] == "skipped"
    assert statuses["Gross profitability"] == "skipped"
    assert statuses["Low asset growth"] == "skipped"
