"""Feature 006 — mid-term four-variant matrix runner (US1 + US3 backend).

Injects a synthetic universe shared by both mid-term strategies and stubs the
events service + regime so the test exercises orchestration without network.
Covers: fixed 4-variant shape, shared snapshot/regime, intra-pair parameter
identity, determinism, empty-variant isolation, and per-strategy bias-check.
"""
import pandas as pd
import pytest

from backend.src import strategies as _strategies  # noqa: F401 - registration
from backend.src.events.service import TickerEventsSnapshot
from backend.src.screening import engine, midterm_matrix
from backend.src.strategies import (
    midterm_52w_high_momentum as _mom,
    midterm_value_composite as _val,
)


def _matrix_universe() -> pd.DataFrame:
    """One snapshot serving both strategies.

    - GOOD: cheap + healthy value name, but 12-1 momentum -50% (a falling knife)
      and far from its 52w high → value_floor_off keeps it, value_floor_on drops
      it, momentum drops it.
    - RICH: expensive value name → fails the cheapness cut.
    - MOM: near its 52w high with clean fundamentals (no value yields) → a
      momentum candidate, excluded from the value composite.
    """
    cols = dict(
        sma_50=None, sma_150=None, sma_200=None, contraction_low_20=None,
        gp_to_assets=None, asset_growth=None, volume_ratio_recent=None,
        book_to_market=None, earnings_yield=None, cashflow_yield=None,
        sales_yield=None, f_score=None, f_score_evaluable=0, return_12_1=None,
    )
    rows = [
        {**cols, "ticker": "GOOD", "name": "Good Co", "sector": "Tech", "close": 50.0,
         "52w_high": 90.0, "atr": 1.0, "sma_200": 45.0, "sma_50": 49.0, "sma_150": 47.0,
         "contraction_low_20": 47.0, "debt_to_equity": 1.0, "fcf_ttm": 10.0,
         "gp_to_assets": 0.4, "asset_growth": 0.05, "volume_ratio_recent": 1.2,
         "book_to_market": 0.9, "earnings_yield": 0.12, "cashflow_yield": 0.10,
         "sales_yield": 2.0, "f_score": 8, "f_score_evaluable": 9, "return_12_1": -0.5},
        {**cols, "ticker": "RICH", "name": "Rich Co", "sector": "Tech", "close": 100.0,
         "52w_high": 200.0, "atr": 1.0, "sma_200": 90.0, "sma_50": 95.0, "sma_150": 92.0,
         "contraction_low_20": 95.0, "debt_to_equity": 0.5, "fcf_ttm": 20.0,
         "gp_to_assets": 0.5, "asset_growth": 0.03, "volume_ratio_recent": 1.0,
         "book_to_market": 0.05, "earnings_yield": 0.01, "cashflow_yield": 0.01,
         "sales_yield": 0.2, "f_score": 9, "f_score_evaluable": 9, "return_12_1": 0.1},
        {**cols, "ticker": "MOM", "name": "Momentum Co", "sector": "Tech", "close": 100.0,
         "52w_high": 101.0, "atr": 2.0, "sma_200": 80.0, "sma_50": 98.0, "sma_150": 90.0,
         "contraction_low_20": 95.0, "debt_to_equity": 0.5, "fcf_ttm": 30.0,
         "gp_to_assets": 0.6, "asset_growth": 0.02, "volume_ratio_recent": 1.5,
         "return_12_1": 0.4},
    ]
    return pd.DataFrame(rows)


class _FakeEvents:
    def ticker_events(self, ticker, **kwargs):
        return TickerEventsSnapshot(
            ticker=str(ticker), next_earnings_date=None, days_to_earnings=None,
            recent_8k_count_30d=0, events=[], sources=[],
        )


@pytest.fixture
def patched(monkeypatch):
    """Patch the snapshot build (counting calls), events, regime, and the cached
    reference thresholds so the matrix runs deterministically off the synthetic
    universe with no network or on-disk cache dependence."""
    calls = {"build": 0}

    def _build(*a, **k):
        calls["build"] += 1
        return _matrix_universe(), "2024-12-31T21:00:00Z"

    monkeypatch.setattr(engine, "_all_stooq_tickers", lambda: [])
    monkeypatch.setattr(engine, "build_universe_snapshot", _build)
    monkeypatch.setattr(engine, "EventsService", _FakeEvents)
    regime = {"regime": "Range-bound", "allows_new_entries": True, "note": "test"}
    monkeypatch.setattr(engine, "market_regime", lambda *a, **k: regime)
    monkeypatch.setattr(midterm_matrix, "market_regime", lambda *a, **k: regime)
    monkeypatch.setattr(_mom, "load_reference_thresholds", lambda *a, **k: None)
    monkeypatch.setattr(_val, "load_reference_thresholds", lambda *a, **k: None)
    return calls


def test_matrix_returns_four_fixed_variants_in_order(patched):
    run = midterm_matrix.run_midterm_matrix()
    assert [v.key for v in run.variants] == [
        "momentum_sector_on",
        "momentum_sector_off",
        "value_floor_on",
        "value_floor_off",
    ]
    assert [v.toggle_value for v in run.variants] == [0.5, 1.0, -0.20, -1.0]
    assert [v.toggle_on for v in run.variants] == [True, False, True, False]
    assert run.variants[0].label == "Momentum — sector gate ON"
    assert run.variants[2].label == "Value — momentum floor ON"


def test_matrix_shares_one_snapshot_and_regime(patched):
    run = midterm_matrix.run_midterm_matrix()
    # Build the (expensive) snapshot exactly once for all four variants (SC-001).
    assert patched["build"] == 1
    assert run.regime == "Range-bound"
    assert run.data_as_of == "2024-12-31T21:00:00Z"
    for v in run.variants:
        assert v.screen.data_as_of == run.data_as_of  # FR-002 / SC-004
        assert v.screen.disclaimer


def test_intra_pair_parameters_differ_only_by_toggle(patched):
    run = midterm_matrix.run_midterm_matrix()
    for a, b, toggle in (
        (run.variants[0], run.variants[1], "sector_strength_top_fraction"),
        (run.variants[2], run.variants[3], "min_momentum_12_1"),
    ):
        pa = {k: x for k, x in a.screen.parameters_snapshot.items() if k != toggle}
        pb = {k: x for k, x in b.screen.parameters_snapshot.items() if k != toggle}
        assert pa == pb  # FR-004 / SC-003
        assert a.screen.parameters_snapshot[toggle] != b.screen.parameters_snapshot[toggle]


def test_caller_supplied_toggles_are_ignored(patched):
    # Caller tries to override BOTH matrix-owned params; the matrix must win.
    run = midterm_matrix.run_midterm_matrix(
        parameters={"sector_strength_top_fraction": 0.99, "min_momentum_12_1": 0.5}
    )
    assert run.variants[0].screen.parameters_snapshot["sector_strength_top_fraction"] == 0.5
    assert run.variants[1].screen.parameters_snapshot["sector_strength_top_fraction"] == 1.0
    assert run.variants[2].screen.parameters_snapshot["min_momentum_12_1"] == -0.20
    assert run.variants[3].screen.parameters_snapshot["min_momentum_12_1"] == -1.0


def _fingerprint(run):
    return [
        [(c.ticker, c.score, c.entry, c.stop_loss, c.take_profit) for c in v.screen.candidates]
        for v in run.variants
    ]


def test_matrix_is_deterministic(patched):
    a = midterm_matrix.run_midterm_matrix()
    b = midterm_matrix.run_midterm_matrix()
    assert _fingerprint(a) == _fingerprint(b)  # FR-007 / SC-002


def test_empty_variant_does_not_drop_siblings(patched):
    run = midterm_matrix.run_midterm_matrix()
    by_key = {v.key: v for v in run.variants}
    # value_floor_off keeps the cheap+healthy GOOD; value_floor_on drops it for a
    # -50% 12-1 momentum, so that variant is empty — without affecting the others.
    assert [c.ticker for c in by_key["value_floor_off"].screen.candidates] == ["GOOD"]
    assert by_key["value_floor_on"].screen.candidates == []  # FR-016
    assert len(run.variants) == 4
    # The empty variant still carries gate-accounting notes.
    assert by_key["value_floor_on"].screen.data_notes is not None


def test_bias_check_is_per_strategy_and_failing_travels_both_variants(patched):
    run = midterm_matrix.run_midterm_matrix()
    mom_on, mom_off, val_on, val_off = run.variants
    # Same verdict for both variants of a strategy (Decision 6).
    assert mom_on.bias_check == mom_off.bias_check
    assert val_on.bias_check == val_off.bias_check
    # The free Stooq archive still FAILS survivorship → passed False on both
    # variants of each strategy (FR-015 / SC-009).
    assert val_on.bias_check["confirmed"] is True
    assert val_on.bias_check["passed"] is False
    assert val_off.bias_check["passed"] is False
    assert mom_on.bias_check["passed"] is False
