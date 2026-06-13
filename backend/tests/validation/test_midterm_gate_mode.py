"""Coverage for the Decision 7 tiered gate-mode branch added to the mid-term
strategy. Default stays `hard`; `tiered` makes the post-proximity gates soft
(warn + rank) instead of hard filters. This previously-untested production path
is exercised here.
"""

from __future__ import annotations

from backend.src.strategies import midterm_52w_high_momentum as midterm


def _tickers(frame) -> list[str]:
    return frame["ticker"].astype(str).tolist()


def test_default_gate_mode_is_hard(monkeypatch) -> None:
    monkeypatch.delenv("SCREENER_GATE_MODE", raising=False)
    assert midterm._gate_mode() == "hard"


def test_tiered_mode_runs_and_admits_more_than_hard(monkeypatch, frozen_snapshot) -> None:
    monkeypatch.setenv("SCREENER_GATE_MODE", "hard")
    hard = _tickers(midterm.rules(frozen_snapshot.us))
    monkeypatch.setenv("SCREENER_GATE_MODE", "tiered")
    tiered = midterm.rules(frozen_snapshot.us)
    tiered_tickers = _tickers(tiered)

    assert not tiered.empty
    # Soft gates admit more total names than the strict intersection.
    assert len(tiered_tickers) >= len(hard)
    # The one always-hard gate (52-week-high proximity) still binds every row.
    assert (
        tiered["dist_to_high"] <= midterm.PARAMETERS["proximity_pct"].default
    ).all()


def test_tiered_mode_is_deterministic(monkeypatch, frozen_snapshot) -> None:
    monkeypatch.setenv("SCREENER_GATE_MODE", "tiered")
    first = _tickers(midterm.rules(frozen_snapshot.us))
    second = _tickers(midterm.rules(frozen_snapshot.us))
    assert first == second
