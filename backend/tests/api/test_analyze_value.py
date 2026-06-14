"""Single-ticker analysis for the value strategy (FR-009, SC-007).

Monkeypatches the price-snapshot + universe builders so the value composite and
F-Score gates are evaluated against a universe distribution (not skipped) without
hitting the network.
"""
import pandas as pd
import pytest

from backend.src import strategies as _strategies  # noqa: F401
from backend.src.api import analyze


def _single_row(ticker="VALU") -> pd.DataFrame:
    return pd.DataFrame([
        dict(ticker=ticker, name="Valu Inc", sector="Tech", close=50.0, atr=1.0,
             sma_200=45.0, contraction_low_20=47.0, debt_to_equity=1.0, fcf_ttm=10.0,
             book_to_market=0.9, earnings_yield=0.12, cashflow_yield=0.10, sales_yield=2.0,
             f_score=8, f_score_evaluable=9, value_metrics_count=4)
    ])


def _universe() -> pd.DataFrame:
    return pd.DataFrame([
        dict(ticker="PEER1", name="Peer1", sector="Tech", close=30.0, atr=1.0,
             sma_200=28.0, contraction_low_20=29.0, debt_to_equity=1.0, fcf_ttm=5.0,
             book_to_market=0.2, earnings_yield=0.03, cashflow_yield=0.02, sales_yield=0.5,
             f_score=5, f_score_evaluable=9, value_metrics_count=4),
        dict(ticker="PEER2", name="Peer2", sector="Tech", close=80.0, atr=1.0,
             sma_200=70.0, contraction_low_20=75.0, debt_to_equity=0.5, fcf_ttm=8.0,
             book_to_market=0.4, earnings_yield=0.05, cashflow_yield=0.04, sales_yield=1.0,
             f_score=7, f_score_evaluable=9, value_metrics_count=4),
    ])


@pytest.fixture
def _patched(monkeypatch):
    monkeypatch.setattr(
        analyze, "build_single_ticker_snapshot",
        lambda symbol, as_of=None: (_single_row(symbol), "2024-12-31T21:00:00Z", []),
    )
    monkeypatch.setattr(analyze, "_market_universe", lambda symbol, as_of: _universe())
    # The EDGAR value overlay would clobber nothing (synthetic row already has
    # value fields), but stub it to keep the test fully offline.
    monkeypatch.setattr(analyze, "_overlay_edgar_value", lambda *a, **k: None)
    monkeypatch.setattr(analyze, "_overlay_edgar", lambda *a, **k: None)


def test_value_gates_evaluated_against_universe(_patched):
    result = analyze.compute_candidate_result("VALU", strategy="midterm_value_composite")
    gates = {g.gate: g.status for g in result.gate_results}
    assert "Value composite" in gates
    assert gates["Value composite"] != "skipped"   # computed vs the universe
    assert gates["Piotroski F-Score"] == "pass"     # F-Score 8 >= 6
    assert result.f_score == 8
    assert result.value_composite is not None
    assert result.data_as_of and result.disclaimer


def test_value_strategy_is_accepted_by_analyze(_patched):
    # Must not raise the momentum-only 400.
    result = analyze.compute_candidate_result("VALU", strategy="midterm_value_composite")
    assert result.strategy == "midterm_value_composite"
