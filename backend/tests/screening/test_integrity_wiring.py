"""T009 [US1] — the live screen self-checks its output and demotes defects.

Written FIRST: must FAIL before the detector is wired into
``_screen_from_universe`` (T013) and the momentum contract exists (T012).

Stubs the snapshot build / events / regime / reference thresholds (the
test_midterm_matrix pattern) so the screen runs deterministically off a synthetic
universe with no network. One injected BELFB-like name has a spurious 12-1 return
that passes every gate and earns the TOP score, but trips the
``value_domain.return_plausible`` invariant. After the wiring it must:
  * carry ``data_suspect=True`` + a populated ``data_integrity_warnings`` naming
    the suspect figure (FR-017);
  * sort BELOW every clean candidate despite its higher score (FR-018);
  * leave clean candidates unflagged (SC-002);
  * record a "flagged N of M" aggregate data note (FR-004 / US4-AC4);
  * yield an identical figure set AND warning set on a re-run (FR-024 / SC-005).
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.src import strategies as _strategies  # noqa: F401 - registration
from backend.src.events.service import TickerEventsSnapshot
from backend.src.screening import engine
from backend.src.strategies import midterm_52w_high_momentum as _mom


def _universe() -> pd.DataFrame:
    """Three clean near-high names + one BELFB-like name whose 12-1 return is a
    spurious +1200% (passes the gates, top score, but implausible)."""
    cols = dict(
        sma_50=None, sma_150=None, contraction_low_20=None,
        gp_to_assets=None, asset_growth=None, daily_returns=None,
    )
    rows = [
        {**cols, "ticker": "AAA", "name": "Alpha", "sector": "Tech", "close": 100.0,
         "52w_high": 104.0, "atr": 2.0, "sma_200": 90.0, "debt_to_equity": 0.5,
         "fcf_ttm": 1e9, "volume_ratio_recent": 1.2, "return_12_1": 0.30},
        {**cols, "ticker": "CCC", "name": "Gamma", "sector": "Health", "close": 50.0,
         "52w_high": 52.0, "atr": 1.0, "sma_200": 45.0, "debt_to_equity": 0.4,
         "fcf_ttm": 2e9, "volume_ratio_recent": 1.1, "return_12_1": 0.25},
        {**cols, "ticker": "DDD", "name": "Delta", "sector": "Energy", "close": 80.0,
         "52w_high": 83.0, "atr": 1.5, "sma_200": 70.0, "debt_to_equity": 0.6,
         "fcf_ttm": 1.5e9, "volume_ratio_recent": 1.3, "return_12_1": 0.20},
        # BELFB-like: near its high, clean fundamentals, but a spurious +1200% return.
        {**cols, "ticker": "BELFB", "name": "Bel Fuse B", "sector": "Industrials",
         "close": 120.0, "52w_high": 123.0, "atr": 2.5, "sma_200": 95.0,
         "debt_to_equity": 0.7, "fcf_ttm": 5e8, "volume_ratio_recent": 1.05,
         "return_12_1": 12.0},
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
    monkeypatch.setenv("SCREENER_GATE_MODE", "hard")  # surviving names carry no soft warnings
    monkeypatch.setattr(engine, "_all_stooq_tickers", lambda: [])
    monkeypatch.setattr(
        engine, "build_universe_snapshot", lambda *a, **k: (_universe(), "2026-06-12T21:00:00Z")
    )
    monkeypatch.setattr(engine, "EventsService", _FakeEvents)
    monkeypatch.setattr(
        engine, "market_regime",
        lambda *a, **k: {"regime": "Trending up", "allows_new_entries": True, "note": "test"},
    )
    monkeypatch.setattr(_mom, "load_reference_thresholds", lambda *a, **k: None)


def _run():
    return engine.run_strategy("midterm_52w_high_momentum")


def test_corrupted_candidate_is_flagged_with_specific_warning(patched):
    result = _run()
    by_ticker = {c.ticker: c for c in result.candidates}
    belfb = by_ticker["BELFB"]
    assert belfb.data_suspect is True
    assert belfb.data_integrity_warnings, "BELFB must carry a data-integrity warning"
    rules = {w.rule for w in belfb.data_integrity_warnings}
    assert "value_domain.return_plausible" in rules
    w = next(w for w in belfb.data_integrity_warnings if w.rule == "value_domain.return_plausible")
    assert w.figure == "return_12_1"
    assert "verify before acting" in w.reason.lower()


def test_clean_candidates_are_not_flagged(patched):
    result = _run()
    for ticker in ("AAA", "CCC", "DDD"):
        c = next(c for c in result.candidates if c.ticker == ticker)
        assert c.data_suspect is False
        assert c.data_integrity_warnings == []


def test_flagged_high_score_name_is_demoted_below_all_clean(patched):
    result = _run()
    tickers = [c.ticker for c in result.candidates]
    # BELFB has the highest raw score but must sort dead last (FR-018).
    assert tickers[-1] == "BELFB"
    belfb = next(c for c in result.candidates if c.ticker == "BELFB")
    assert all(
        belfb.score >= c.score for c in result.candidates if c.ticker != "BELFB"
    ), "precondition: BELFB has the top raw score"
    # clean names keep their score order ahead of it (AAA > CCC > DDD by score)
    clean = [c for c in result.candidates if not c.data_suspect]
    assert [c.ticker for c in clean] == ["AAA", "CCC", "DDD"]


def test_aggregate_flag_count_recorded_in_data_notes(patched):
    result = _run()
    joined = " ".join(result.data_notes).lower()
    assert "flag" in joined
    assert "1" in joined and "4" in joined  # 1 of 4 names flagged


def test_screen_is_deterministic_in_figures_and_warnings(patched):
    a = _run()
    b = _run()
    fa = [(c.ticker, c.score, c.entry, c.take_profit, c.data_suspect,
           tuple(w.rule for w in c.data_integrity_warnings)) for c in a.candidates]
    fb = [(c.ticker, c.score, c.entry, c.take_profit, c.data_suspect,
           tuple(w.rule for w in c.data_integrity_warnings)) for c in b.candidates]
    assert fa == fb
