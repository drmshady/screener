"""Screen-level integration for midterm_value_composite (SC-001/003/004/007).

Injects a synthetic universe (the live EDGAR slim cache predates the value
concepts) and stubs the events service so the test exercises the full engine
candidate-assembly + gate flow without network.
"""
import pandas as pd
import pytest

from backend.src import strategies as _strategies  # noqa: F401 - registration
from backend.src.events.service import TickerEventsSnapshot
from backend.src.screening import engine


def _synthetic_universe() -> pd.DataFrame:
    rows = [
        dict(ticker="GOOD", name="Good Co", sector="Tech", close=50.0, atr=1.0,
             sma_200=45.0, contraction_low_20=47.0, debt_to_equity=1.0, fcf_ttm=10.0,
             book_to_market=0.9, earnings_yield=0.12, cashflow_yield=0.10, sales_yield=2.0,
             f_score=8, f_score_evaluable=9, value_metrics_count=4),
        dict(ticker="TRAP", name="Trap Co", sector="Tech", close=30.0, atr=1.0,
             sma_200=28.0, contraction_low_20=29.0, debt_to_equity=1.0, fcf_ttm=5.0,
             book_to_market=1.1, earnings_yield=0.15, cashflow_yield=0.12, sales_yield=2.5,
             f_score=2, f_score_evaluable=9, value_metrics_count=4),
        dict(ticker="RICH", name="Rich Co", sector="Tech", close=100.0, atr=1.0,
             sma_200=90.0, contraction_low_20=95.0, debt_to_equity=0.5, fcf_ttm=20.0,
             book_to_market=0.05, earnings_yield=0.01, cashflow_yield=0.01, sales_yield=0.2,
             f_score=9, f_score_evaluable=9, value_metrics_count=4),
    ]
    return pd.DataFrame(rows)


class _FakeEvents:
    def ticker_events(self, ticker, **kwargs):
        return TickerEventsSnapshot(
            ticker=str(ticker), next_earnings_date=None, days_to_earnings=None,
            recent_8k_count_30d=0, events=[], sources=[],
        )


@pytest.fixture
def _patched(monkeypatch):
    monkeypatch.setattr(engine, "_all_stooq_tickers", lambda: [])
    monkeypatch.setattr(
        engine, "build_universe_snapshot",
        lambda *a, **k: (_synthetic_universe(), "2024-12-31T21:00:00Z"),
    )
    monkeypatch.setattr(engine, "EventsService", _FakeEvents)


def test_value_screen_returns_gated_ranked_candidates(_patched):
    result = engine.run_strategy("midterm_value_composite")
    tickers = [c.ticker for c in result.candidates]
    # Only the cheap + healthy + sanely-levered name survives the hard gates.
    assert "GOOD" in tickers
    assert "TRAP" not in tickers  # failed F-Score
    assert "RICH" not in tickers  # failed cheapness cut


def test_value_candidates_carry_value_fields_and_disclosure(_patched):
    result = engine.run_strategy("midterm_value_composite")
    assert result.data_as_of and result.disclaimer  # SC-004
    good = next(c for c in result.candidates if c.ticker == "GOOD")
    assert good.value_composite is not None       # SC-003 diagnostics present
    assert good.f_score == 8
    assert good.book_to_market == pytest.approx(0.9)
    gates = {g.gate for g in good.gate_results}    # SC-007 per-gate accounting
    assert {"Value composite", "Piotroski F-Score", "Leverage sanity"} <= gates
