from __future__ import annotations

import pytest

from backend.src.strategies import midterm_52w_high_momentum as midterm


def _tickers(frame) -> list[str]:
    return frame["ticker"].astype(str).tolist()


def test_quality_screen_toggle_changes_hard_output(monkeypatch, frozen_snapshot) -> None:
    monkeypatch.setenv("SCREENER_GATE_MODE", "hard")
    base = _tickers(midterm.rules(frozen_snapshot.us))
    monkeypatch.setattr(midterm.PARAMETERS["max_debt_equity"], "default", 99.0)
    relaxed = _tickers(midterm.rules(frozen_snapshot.us))
    assert set(relaxed) != set(base)


def test_sector_relative_cap_changes_hard_output(monkeypatch, frozen_snapshot) -> None:
    monkeypatch.setenv("SCREENER_GATE_MODE", "hard")
    base = _tickers(midterm.rules(frozen_snapshot.us))
    monkeypatch.setattr(midterm.PARAMETERS["max_per_sector"], "default", 99)
    uncapped = _tickers(midterm.rules(frozen_snapshot.us))
    assert set(uncapped) != set(base)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "F-002: volatility scaling is inert on the live screen — the screen rows "
        "carry no per-row daily_returns Series, so changing target_volatility "
        "moves neither the set nor the ordering. Wire daily_returns into the "
        "screen rows (or drop the modification claim), then this asserts an effect."
    ),
)
def test_volatility_scaling_has_an_observable_effect(monkeypatch, frozen_snapshot) -> None:
    """A declared modification must change the screen output (FR-006a).

    Currently xfails: target_volatility does not move the candidate set/order
    because the live screen rows lack daily_returns (F-002).
    """
    monkeypatch.setenv("SCREENER_GATE_MODE", "hard")
    base = midterm.rules(frozen_snapshot.us)
    monkeypatch.setattr(midterm.PARAMETERS["target_volatility"], "default", 0.30)
    widened = midterm.rules(frozen_snapshot.us)
    same_set = set(_tickers(widened)) == set(_tickers(base))
    same_order = _tickers(widened) == _tickers(base)
    assert not (same_set and same_order)
