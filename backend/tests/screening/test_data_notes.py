"""Honest data-completeness reporting: gates that cannot run on the given
universe are reported (ScreenResult.data_notes / rules() attrs), and the
per-candidate reason names only the gates that actually ran."""
from __future__ import annotations

import pandas as pd
import pytest

from backend.src.strategies.midterm_52w_high_momentum import rules


@pytest.fixture(autouse=True)
def _hard_gate_mode(monkeypatch):
    # These assert HARD-filter behavior (fail-closed quality, AG/volume filtering).
    # The default is now tiered (Decision 7); pin hard mode for this file.
    monkeypatch.setenv("SCREENER_GATE_MODE", "hard")


def _full_universe(n: int = 40) -> pd.DataFrame:
    sectors = ["Tech", "Energy", "Health", "Fin"]
    rows = []
    for i in range(n):
        rows.append(
            {"ticker": f"T{i}", "sector": sectors[i % 4], "close": 100.0,
             "52w_high": 102.0, "fcf_ttm": 1e9, "debt_to_equity": 0.5,
             "atr": 2.0, "sma_200": 90.0, "gp_to_assets": 0.6,
             "volume_ratio_50": 1.5, "volume_ratio_recent": 1.1,
             "asset_growth": 0.05}
        )
    return pd.DataFrame(rows)


def test_all_gates_run_on_complete_data():
    out = rules(_full_universe())
    assert not out.empty
    # The sector-strength gate is DISABLED by default (2026-06-12) — counterproductive
    # metric — so it is reported skipped; every OTHER gate runs on complete data.
    skipped = out.attrs["gates_skipped"]
    assert all("sector-strength" in note for note in skipped), skipped
    reason = out["reason"].iloc[0]
    # Hard-mode reason lists the gates that ran (gates_applied labels).
    for fragment in ["52-week high", "volume-confirmed",
                     "200-day SMA", "positive FCF", "gross profitability",
                     "low asset growth"]:
        assert fragment.lower() in reason.lower(), f"missing {fragment!r} in {reason!r}"
    assert "leading sector" not in reason.lower()


def test_asset_growth_gate_keeps_low_growth_half():
    df = _full_universe(n=40)
    # Bottom-half (low) growth = first 20 names; top-half (high) growth = last 20.
    df["asset_growth"] = [0.01 * i for i in range(40)]  # 0.00 .. 0.39 ascending
    out = rules(df)
    assert not out.empty
    kept = set(out["ticker"])
    # No high-growth name (index >= 20, growth >= 0.20) should survive.
    assert not any(int(t[1:]) >= 20 for t in kept), kept


def test_asset_growth_gate_fails_open_when_missing():
    df = _full_universe(n=40).drop(columns=["asset_growth"])
    out = rules(df)
    assert not out.empty
    assert any("asset-growth gate skipped" in n for n in out.attrs["gates_skipped"])
    assert "low asset growth" not in out["reason"].iloc[0].lower()


def test_missing_gp_column_reported_and_not_claimed():
    df = _full_universe().drop(columns=["gp_to_assets"])
    out = rules(df)
    assert not out.empty
    assert any("gross-profitability gate skipped" in note for note in out.attrs["gates_skipped"])
    # The reason must NOT claim a gate that never ran.
    assert "gross profitability" not in out["reason"].iloc[0].lower()


def test_missing_volume_column_reported_and_not_claimed():
    df = _full_universe().drop(columns=["volume_ratio_50", "volume_ratio_recent"])
    out = rules(df)
    assert not out.empty
    assert any("volume-confirmation gate skipped" in note for note in out.attrs["gates_skipped"])
    assert "volume-confirmed" not in out["reason"].iloc[0].lower()


def test_small_universe_sector_skip_reported():
    out = rules(_full_universe(n=5))
    assert not out.empty
    assert any("sector-strength gate skipped" in note for note in out.attrs["gates_skipped"])
    assert "leading sector" not in out["reason"].iloc[0].lower()


def test_quality_screen_missing_fundamentals_fails_closed_and_reported():
    df = _full_universe()
    df.loc[0:9, "fcf_ttm"] = None  # 10 names missing FCF
    out = rules(df)
    assert not out.empty
    assert any("missing" in note and "quality" in note for note in out.attrs["gates_skipped"])
    # The names with missing fundamentals must NOT appear in the output.
    assert not set(f"T{i}" for i in range(10)) & set(out["ticker"])
