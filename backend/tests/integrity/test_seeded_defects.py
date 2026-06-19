"""T015 [US2] — the seeded-defect suite (the blocking CI gate), FR-008 / SC-001.

Written FIRST: must FAIL before ``integrity/harness.py`` exists (T019).

For each synthetic ``SeededDefect`` class the harness injects the fault into a
copy of a frozen-snapshot fixture, runs the momentum ``OUTPUT_CONTRACT`` through
the strategy-agnostic engine, and asserts the expected invariant family fires —
**100% detection required** (SC-001); a miss is a failing test. The
un-corrupted control copy must raise **zero** data-integrity warnings (SC-002).

The fixture is a small, checked-in, network-free clean candidate frame standing
in for the 2026-06-12 snapshot (fixtures/README.md): every row satisfies every
momentum invariant, so any fired warning is attributable to the injected defect.
"""
from __future__ import annotations

import math

import pandas as pd

from backend.src.screening.integrity.engine import evaluate_contract
from backend.src.screening.integrity.harness import (
    default_seeded_defects,
    run_seeded_defect,
    run_seeded_suite,
)
from backend.src.strategies.midterm_52w_high_momentum import OUTPUT_CONTRACT

# The seven defect classes the harness must catch (data-model §9), each mapped to
# the invariant family that MUST fire (contracts/harness-report.schema.md §2).
_EXPECTED_FAMILY = {
    "corrupted_price": "value_domain",
    "broken_score": "score",
    "stale_but_fresh": "series",
    "nan_field": "value_domain",
    "inconsistent_dist_to_high": "coherence",
    "seam_discontinuity": "series",
    "seam_unverified": "series",
    "share_class_swap": "identity",
    # A price pinned under a pending all-cash acquisition: realized vol collapses,
    # saturating the vol_scalar and inflating the score (the EA defect).
    "pinned_price": "value_domain",
    # A bad-bar jump co-occurring with a routine corporate action elsewhere in the
    # window: the localized jump check must still fire (no window-wide masking).
    "unexplained_jump_with_dividend": "series",
}


def _clean_row(ticker: str, *, close: float, ret: float, atr: float) -> dict:
    """A candidate row that satisfies EVERY momentum invariant.

    Includes the data-model §8 series-integrity signal columns with safe values,
    so the contract's series/identity invariants read them off the row itself
    (evaluate_contract uses the row as its own ``signals`` when none is passed).
    """
    high = round(close / (1 - 0.03), 4)  # 3% below the 52-week high (passes proximity)
    dist = (high - close) / close
    stop = round(close - 3 * atr, 4)  # 3-ATR disaster stop, below entry
    vol_scalar = 1.0
    score = ret * vol_scalar / (1.0 + dist)
    take_profit = close + 3.0 * (close - stop)  # default take_profit_r_multiple = 3.0
    return {
        "ticker": ticker,
        "name": ticker,
        "sector": "Industrials",
        "close": close,
        "52w_high": high,
        "dist_to_high": dist,
        "entry": close,
        "atr": atr,
        "stop_loss": stop,
        "take_profit": take_profit,
        "vol_scalar": vol_scalar,
        "score": score,
        "return_12_1": ret,
        # data-model §8 series-integrity signals (clean defaults)
        "series_dates_ok": True,
        "series_max_session_move": 0.08,
        "seam_consistent": True,
        "seam_factor": 1.0,
        "seam_overlap_found": True,
        "corporate_action_in_window": False,
        "series_max_move_explained": True,
        "adj_close_basis_used": True,
        "share_class_consistent": True,
    }


def _frozen_snapshot() -> pd.DataFrame:
    """A clean stand-in for the 2026-06-12 frozen snapshot top candidates."""
    return pd.DataFrame(
        [
            _clean_row("BELFB", close=120.0, ret=0.18, atr=2.5),
            _clean_row("JBHT", close=180.0, ret=0.22, atr=3.0),
            _clean_row("CW", close=300.0, ret=0.30, atr=4.0),
            _clean_row("IOSP", close=110.0, ret=0.12, atr=2.0),
        ]
    )


def test_control_copy_raises_zero_warnings():
    """SC-002: the un-corrupted snapshot trips no invariant (no false positive)."""
    annotated = evaluate_contract(_frozen_snapshot(), OUTPUT_CONTRACT)
    assert not annotated["data_suspect"].any(), (
        "clean control snapshot must raise no data-integrity warning; offenders: "
        + str(
            [
                (r["ticker"], [v.invariant_name for v in r["data_integrity_warnings"]])
                for _, r in annotated.iterrows()
                if r["data_suspect"]
            ]
        )
    )


def test_default_seeded_defects_cover_all_classes():
    defects = default_seeded_defects("BELFB")
    assert {d.defect_class for d in defects} == set(_EXPECTED_FAMILY)
    for d in defects:
        assert d.expected_family == _EXPECTED_FAMILY[d.defect_class]


def test_every_seeded_defect_class_is_detected():
    """SC-001: 100% of injected defect classes are caught. A miss fails the gate."""
    snapshot = _frozen_snapshot()
    results = run_seeded_suite(snapshot, OUTPUT_CONTRACT, target_ticker="BELFB")
    assert {r.defect_class for r in results} == set(_EXPECTED_FAMILY)
    misses = [r.defect_class for r in results if not r.detected]
    assert misses == [], f"seeded defects NOT detected (CI gate violated): {misses}"
    for r in results:
        assert r.expected_family in r.fired_families, (
            f"{r.defect_class}: expected family {r.expected_family!r} did not fire; "
            f"fired={r.fired_families}"
        )


def test_each_defect_isolated_to_its_target_only():
    """Injecting a defect into one name leaves the other clean names unflagged."""
    snapshot = _frozen_snapshot()
    for defect in default_seeded_defects("BELFB"):
        result = run_seeded_defect(snapshot, OUTPUT_CONTRACT, defect)
        assert result.detected, f"{defect.defect_class} not detected on its target"


def test_nan_field_defect_actually_injects_a_nan():
    """Guard the fixture honesty: the nan_field apply truly produces a NaN."""
    snapshot = _frozen_snapshot()
    defect = next(
        d for d in default_seeded_defects("BELFB") if d.defect_class == "nan_field"
    )
    corrupted = defect.apply(snapshot.copy(deep=True))
    row = corrupted.loc[corrupted["ticker"] == "BELFB"].iloc[0]
    assert any(
        isinstance(row[c], float) and math.isnan(row[c])
        for c in ("return_12_1", "score", "close")
    )


def test_seeded_injection_does_not_mutate_the_shared_snapshot():
    """Each defect works on a copy; the canonical snapshot is never corrupted."""
    snapshot = _frozen_snapshot()
    before = snapshot.copy(deep=True)
    run_seeded_suite(snapshot, OUTPUT_CONTRACT, target_ticker="BELFB")
    pd.testing.assert_frame_equal(snapshot, before)
