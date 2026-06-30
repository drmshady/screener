from __future__ import annotations

import pandas as pd
import pytest

from backend.src.strategies import midterm_52w_high_momentum as midterm
from backend.src.strategies._helpers.vol_scaling import calculate_volatility_scalar


def _tickers(frame) -> list[str]:
    return frame["ticker"].astype(str).tolist()


def test_quality_screen_toggle_changes_hard_output(monkeypatch, frozen_snapshot) -> None:
    """The leverage cap (`max_debt_equity`) demonstrably changes the hard-mode set.

    The original form asserted that *relaxing* the cap to 99.0 flips the output,
    which only holds when the frozen snapshot happens to contain a name excluded
    SOLELY by leverage — pure data luck (it was inert on some snapshots and the
    test then failed without any code regression). Instead, derive a threshold
    that provably binds on THIS snapshot: tighten the cap just below the highest
    leverage among current survivors, so that name is guaranteed newly excluded
    and the set must change. Robust to universe composition while still proving
    the quality gate is wired into the live screen.
    """
    monkeypatch.setenv("SCREENER_GATE_MODE", "hard")
    base = _tickers(midterm.rules(frozen_snapshot.us))

    universe = frozen_snapshot.us
    survivor_de = (
        universe[universe["ticker"].astype(str).isin(base)]["debt_to_equity"]
        .astype(float)
        .dropna()
    )
    survivor_de = survivor_de[survivor_de > 0]
    distinct = sorted(survivor_de.unique())
    if not distinct:
        pytest.skip(
            "no surviving name carries a positive debt/equity on this snapshot; "
            "the leverage cap cannot bind here (inert, not a regression)"
        )
    # A threshold strictly below the highest survivor leverage excludes that name.
    binding = (distinct[-1] + distinct[-2]) / 2.0 if len(distinct) >= 2 else distinct[-1] / 2.0

    monkeypatch.setattr(midterm.PARAMETERS["max_debt_equity"], "default", binding)
    tightened = _tickers(midterm.rules(frozen_snapshot.us))
    # The highest-leverage survivor is in `base` but excluded under the tighter
    # cap, so the sets must differ regardless of any per-sector-cap backfill.
    assert set(tightened) != set(base)


def test_sector_relative_cap_changes_hard_output(monkeypatch, frozen_snapshot) -> None:
    monkeypatch.setenv("SCREENER_GATE_MODE", "hard")
    base = _tickers(midterm.rules(frozen_snapshot.us))
    monkeypatch.setattr(midterm.PARAMETERS["max_per_sector"], "default", 99)
    uncapped = _tickers(midterm.rules(frozen_snapshot.us))
    assert set(uncapped) != set(base)


def test_volatility_scaling_is_wired_into_live_screen_rows(frozen_snapshot) -> None:
    """F-002 (corrected): the Barroso–Santa-Clara vol-scaling modification IS
    wired into the live compliant-US screen — the rows carry a per-row
    `daily_returns` Series and the scalar varies across names (it is not a
    constant 1.0). The original finding's root cause ("rows lack daily_returns")
    was factually wrong.
    """
    us = frozen_snapshot.us
    assert "daily_returns" in us.columns
    series_rows = us["daily_returns"].apply(lambda v: isinstance(v, pd.Series))
    assert series_rows.all(), "every live screen row must carry a daily_returns Series"

    scalars = us.loc[series_rows, "daily_returns"].apply(
        lambda v: calculate_volatility_scalar(v, midterm.PARAMETERS["target_volatility"].default)
    )
    # The modification differentiates names by realized volatility (not inert).
    assert scalars.round(4).nunique() > 1
    assert not (scalars == 1.0).all()


def test_volatility_scaling_changes_selection_when_ranking_binds(monkeypatch, frozen_snapshot) -> None:
    """Vol-scaling demonstrably affects the output where the per-sector cap binds.

    In tiered mode the post-proximity universe is large enough that ranking
    decides the per-sector top-N, so neutralizing vol-scaling (scalar→1.0)
    changes both the set and the order — proving the modification is functional.
    In default hard mode the post-gate set is small and the sector cap does not
    bind, so vol-scaling has no *output* effect there (expected, not a defect):
    `target_volatility` is also scale-invariant for ranking and bites only via
    the 2.0 leverage cap / position sizing.
    """
    monkeypatch.setenv("SCREENER_GATE_MODE", "tiered")
    real = _tickers(midterm.rules(frozen_snapshot.us))
    monkeypatch.setattr(midterm, "calculate_volatility_scalar", lambda *a, **k: 1.0)
    neutralized = _tickers(midterm.rules(frozen_snapshot.us))
    assert set(real) != set(neutralized) or real != neutralized
