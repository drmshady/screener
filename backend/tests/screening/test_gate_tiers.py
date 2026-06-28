"""Feature 012 US2 — three-tier gate classification + expanded coverage.

Covers FR-009–015 / SC-003/004/009:
- the per-strategy gate→tier declaration (essential / preferred / disqualifier);
- expanded_coverage ON retains a preferred-gate non-pass (marked skipped + reason)
  and demotes it strictly below all clean names;
- essential gates (proximity) still exclude regardless of the toggle;
- expanded_coverage OFF reproduces today's hard-mode output (byte-identical);
- the strict clean-above-skipped ordering invariant.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.src.models.strategy import Strategy, StrategyParameter
from backend.src.screening.engine import _screen_from_universe
from backend.src.screening.gate_tiers import GATE_TIERS, gate_tier, gate_tiers
from backend.src.strategies import midterm_52w_high_momentum as midterm


# ---------------------------------------------------------------------------
# gate_tiers.py — the per-strategy declaration (FR-009/009a)
# ---------------------------------------------------------------------------


def test_momentum_default_tier_map_classifies_each_named_gate():
    tiers = gate_tiers("midterm_52w_high_momentum")
    assert tiers["liquidity"] == "essential"
    assert tiers["data_integrity"] == "essential"
    assert tiers["52-week-high proximity"] == "essential"
    assert tiers["market regime"] == "preferred"
    assert tiers["sector strength"] == "preferred"
    assert tiers["relative strength"] == "preferred"
    assert tiers["climax-top exhaustion"] == "disqualifier"
    assert tiers["huge-gap breakout"] == "disqualifier"


def test_gate_tier_classifies_actual_gate_labels_and_defaults_to_preferred():
    slug = "midterm_52w_high_momentum"
    assert gate_tier(slug, "52-week-high proximity") == "essential"
    assert gate_tier(slug, "Sector strength") == "preferred"
    assert gate_tier(slug, "Trend (above 200-day SMA)") == "preferred"
    assert gate_tier(slug, "Relative strength") == "preferred"
    # an unknown soft gate defaults to preferred (demote-not-exclude), never
    # silently essential.
    assert gate_tier(slug, "Some future soft gate") == "preferred"


def test_gate_tier_overrides_via_env(monkeypatch):
    monkeypatch.setenv("SCREENER_GATE_TIER_OVERRIDES", "sector strength=essential")
    assert gate_tier("midterm_52w_high_momentum", "Sector strength") == "essential"
    assert gate_tiers("midterm_52w_high_momentum")["sector strength"] == "essential"


def test_canonical_map_is_declared_for_momentum():
    assert "midterm_52w_high_momentum" in GATE_TIERS


# ---------------------------------------------------------------------------
# Engine wiring — retention, skipped_gates, and ordering (FR-010/012, SC-004)
# ---------------------------------------------------------------------------


def _screen_row(ticker: str, *, score: float = 1.0, warnings=None, gate_results=None, **overrides):
    warned = list(warnings or [])
    row = {
        "ticker": ticker,
        "name": f"{ticker} Corp",
        "sector": "Technology",
        "close": 102.0,
        "entry": 102.0,
        "stop_loss": 94.0,
        "take_profit": 120.0,
        "score": score,
        "reason": "within 5% of 52-week high",
        "gate_results": gate_results or [],
        "warnings": warned,
        "warning_count": len(warned),
        "data_integrity_warnings": [],
        "data_suspect": False,
        "pivot": 100.0,
        "base_type": "flat",
        "base_length_weeks": 6.0,
        "base_depth": 0.18,
        "breakout_volume_ratio": 1.5,
        "dist_above_pivot": 0.02,
        "dist_above_sma_200": 0.13,
        "sma_200": 90.0,
        "climax_advance": 0.1,
        "prior_trend_weeks": 10.0,
        "gap_above_pivot": 0.0,
    }
    row.update(overrides)
    return row


def _stub_strategy(slug: str, rows: list[dict]) -> Strategy:
    return Strategy(
        slug=slug,
        name="Stub Strategy",
        timeframe="Mid-term",
        citation="Test",
        description="Test strategy",
        holding_period_days={"min": 1, "max": 2},
        parameters={},
        regime_favorability={},
        default_exclude_earnings_within_days=0,
        enabled_by_default=True,
        modifications=[],
        rules=lambda universe: pd.DataFrame(rows),
    )


def _screen(rows, params):
    strategy = _stub_strategy("midterm_52w_high_momentum", rows)
    return _screen_from_universe(
        strategy,
        strategy.slug,
        pd.DataFrame(rows),
        "2026-06-26T00:00:00Z",
        params,
        {},
        {},
        False,
        None,
    )


def test_expanded_coverage_records_skipped_gate_and_demotes_below_clean():
    clean = _screen_row("CLEAN", score=2.0)
    warned = _screen_row(
        "WARNED",
        score=9.0,  # higher raw score must NOT lift it above the clean name
        warnings=["Sector strength"],
        gate_results=[
            {"gate": "Sector strength", "status": "warn", "detail": "outside the leading sectors"}
        ],
    )
    result = _screen([clean, warned], {"expanded_coverage": True})

    # both retained
    assert {c.ticker for c in result.candidates} == {"CLEAN", "WARNED"}
    # strict ordering: the skipped-gate name sinks below the clean name (SC-004)
    assert [c.ticker for c in result.candidates] == ["CLEAN", "WARNED"]

    warned_c = next(c for c in result.candidates if c.ticker == "WARNED")
    assert [s.gate for s in warned_c.skipped_gates] == ["Sector strength"]
    assert "leading sectors" in warned_c.skipped_gates[0].reason
    clean_c = next(c for c in result.candidates if c.ticker == "CLEAN")
    assert clean_c.skipped_gates == []


def test_essential_gate_never_recorded_as_skipped():
    # Even if a (degenerate) warned list contains the essential proximity gate,
    # it must not be surfaced as a skipped *preferred* gate (FR-011).
    warned = _screen_row(
        "WARNED",
        warnings=["52-week-high proximity", "Sector strength"],
        gate_results=[
            {"gate": "52-week-high proximity", "status": "warn", "detail": "x"},
            {"gate": "Sector strength", "status": "warn", "detail": "outside leaders"},
        ],
    )
    result = _screen([warned], {"expanded_coverage": True})
    skipped = [s.gate for s in result.candidates[0].skipped_gates]
    assert skipped == ["Sector strength"]


def test_default_off_has_no_skipped_gates():
    clean = _screen_row("CLEAN")
    result = _screen([clean], {})
    assert result.candidates[0].skipped_gates == []


# ---------------------------------------------------------------------------
# Strategy rules() — preferred demote-not-exclude vs essential exclude (FR-013)
# ---------------------------------------------------------------------------


def _rules_row(ticker, sector, close, high, ret, fcf, de, atr, sma_200, gp):
    return {
        "ticker": ticker,
        "name": ticker,
        "sector": sector,
        "close": close,
        "52w_high": high,
        "return_12_1": ret,
        "fcf_ttm": fcf,
        "debt_to_equity": de,
        "atr": atr,
        "sma_200": sma_200,
        "contraction_low_20": close - (2 * atr),
        "gp_to_assets": gp,
    }


@pytest.fixture()
def _no_reference_thresholds(monkeypatch):
    # Keep the cross-sectional GP/AG gates on the contemporaneous quantile so the
    # tiny synthetic universe isn't graded against an unrelated cached cut.
    monkeypatch.setattr(midterm, "load_reference_thresholds", lambda: None)
    monkeypatch.delenv("SCREENER_GATE_MODE", raising=False)
    monkeypatch.delenv("SCREENER_EXPANDED_COVERAGE", raising=False)


def test_expanded_coverage_retains_preferred_trend_failure(_no_reference_thresholds):
    universe = pd.DataFrame(
        [
            _rules_row("UP", "Technology", 100.0, 101.0, 0.30, 10_000_000, 0.3, 2.0, 90.0, 0.5),
            # DOWN is near its high but below its 200-day SMA -> the (preferred)
            # trend gate fails.
            _rules_row("DOWN", "Technology", 100.0, 101.0, 0.30, 10_000_000, 0.3, 2.0, 110.0, 0.5),
        ]
    )

    # Default (hard) mode excludes the trend failure entirely (today's behaviour).
    hard = midterm.rules(universe.copy())
    assert hard["ticker"].tolist() == ["UP"]

    # Expanded coverage retains it, marked with a soft-gate warning.
    expanded = universe.copy()
    expanded.attrs["expanded_coverage"] = True
    tiered = midterm.rules(expanded)
    assert set(tiered["ticker"]) == {"UP", "DOWN"}
    down = tiered[tiered["ticker"] == "DOWN"].iloc[0]
    assert "Trend (above 200-day SMA)" in list(down["warnings"])
    assert int(down["warning_count"]) >= 1


def _entry_row(ticker, *, ret, entry_ready):
    """A momentum universe row carrying the entry-timing inputs, near its high and
    above its SMA-200 so it survives the strategy gates. `entry_ready` toggles the
    breakout-volume confirmation only, flipping the entry-timing STATE without
    changing the strategy score (which is driven by `ret`)."""
    base = _rules_row(ticker, "Technology", 100.0, 101.0, ret, 10_000_000, 0.3, 2.0, 90.0, 0.5)
    base.update(
        {
            "pivot": 98.0,
            "base_type": "flat",
            "base_length_weeks": 6.0,
            "base_depth": 0.18,
            # The only differentiator: confirming volume (>=1.4) => entry-ready.
            "breakout_volume_ratio": 1.5 if entry_ready else 1.0,
            "dist_above_pivot": 0.02,
            "dist_above_sma_200": 0.11,
            "climax_advance": 0.10,
            "prior_trend_weeks": 10.0,
            "gap_above_pivot": 0.0,
            "recent_short_lived_catalyst": False,
        }
    )
    return base


def test_entry_ready_only_filters_before_per_sector_cap(_no_reference_thresholds, monkeypatch):
    # One sector, cap of 1 slot. HIGH scores higher but is NOT entry-ready; LOW
    # scores lower but IS entry-ready. Without the pre-cap filter the cap would
    # award the slot to HIGH and the downstream entry-ready filter would then drop
    # it, yielding ZERO entry-ready names — fewer than the narrow run surfaces.
    monkeypatch.setitem(
        midterm.PARAMETERS,
        "max_per_sector",
        StrategyParameter(default=1, type="int", description="Max candidates per sector"),
    )
    universe = pd.DataFrame(
        [
            _entry_row("HIGH", ret=0.50, entry_ready=False),
            _entry_row("LOW", ret=0.30, entry_ready=True),
        ]
    )

    expanded = universe.copy()
    expanded.attrs["expanded_coverage"] = True
    expanded.attrs["entry_ready_only"] = True
    result = midterm.rules(expanded)
    # The entry-ready name wins the single slot; the higher-scoring not-ready name
    # never evicts it.
    assert result["ticker"].tolist() == ["LOW"]


def test_expanded_without_entry_ready_only_keeps_top_scored(_no_reference_thresholds, monkeypatch):
    # Same fixture, but entry_ready_only OFF: behaviour is unchanged — the cap
    # awards its single slot to the highest-scoring name regardless of readiness.
    monkeypatch.setitem(
        midterm.PARAMETERS,
        "max_per_sector",
        StrategyParameter(default=1, type="int", description="Max candidates per sector"),
    )
    universe = pd.DataFrame(
        [
            _entry_row("HIGH", ret=0.50, entry_ready=False),
            _entry_row("LOW", ret=0.30, entry_ready=True),
        ]
    )
    expanded = universe.copy()
    expanded.attrs["expanded_coverage"] = True
    result = midterm.rules(expanded)
    assert result["ticker"].tolist() == ["HIGH"]


def test_proximity_essential_gate_excludes_regardless_of_expanded(_no_reference_thresholds):
    universe = pd.DataFrame(
        [
            _rules_row("NEAR", "Technology", 100.0, 101.0, 0.30, 10_000_000, 0.3, 2.0, 90.0, 0.5),
            # FAR is well below its 52-week high -> fails the essential proximity gate.
            _rules_row("FAR", "Technology", 80.0, 120.0, 0.30, 10_000_000, 0.3, 2.0, 70.0, 0.5),
        ]
    )
    expanded = universe.copy()
    expanded.attrs["expanded_coverage"] = True
    tiered = midterm.rules(expanded)
    assert tiered["ticker"].tolist() == ["NEAR"]
