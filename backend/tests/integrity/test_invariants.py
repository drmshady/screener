"""T007 [US1] — reusable invariant builders (FR-003, FR-005).

Written FIRST: must FAIL before ``integrity/invariants.py`` exists (T011).

One case per invariant family (momentum-contract.md): coherence, gate, score,
level, value_domain, series, identity. Each family asserts:
  * the predicate is SATISFIED (True) on a clean row — no false positive (SC-002);
  * the predicate FIRES (False) on a corrupted row.

Predicates are pure ``(row, signals) -> bool``; here we exercise them directly so
the builders are unit-tested independently of the engine (T006) and any strategy
(T012/T014). Rows/signals are pandas Series, matching the live ``df.iterrows()``
shape the engine feeds them.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.src.screening.integrity.invariants import (
    aggregate_flag_count,
    coherence_dist_to_high,
    coherence_entry_eq_close,
    gate_satisfied,
    identity_single_share_class,
    level_sanity,
    score_reproduces,
    series_integrity,
    value_domain_bounded,
    value_domain_finite,
    value_domain_high_plausible,
    value_domain_positive,
    value_domain_realized_vol_floor,
    value_domain_return_plausible,
)


def _row(**over) -> pd.Series:
    base = dict(
        ticker="AAA",
        close=100.0,
        **{"52w_high": 104.0},
        dist_to_high=0.04,
        entry=100.0,
        return_12_1=0.30,
        vol_scalar=1.0,
        atr=2.0,
        score=0.30 * 1.0 / (1.0 + 0.04),
        stop_loss=92.0,
        take_profit=124.0,
    )
    base.update(over)
    return pd.Series(base)


def _signals(**over) -> pd.Series:
    base = dict(
        series_dates_ok=True,
        series_max_session_move=0.05,
        seam_consistent=True,
        corporate_action_in_window=False,
        share_class_consistent=True,
    )
    base.update(over)
    return pd.Series(base)


# --- coherence ------------------------------------------------------------

def test_coherence_dist_to_high_pass_and_fire():
    inv = coherence_dist_to_high()
    assert inv.family == "coherence" and inv.severity == "candidate"
    assert inv.predicate(_row(), _signals()) is True
    # dist_to_high inconsistent with (52w_high - close)/close
    bad = _row(dist_to_high=0.40)
    assert inv.predicate(bad, _signals()) is False


def test_coherence_entry_eq_close_pass_and_fire():
    inv = coherence_entry_eq_close()
    assert inv.predicate(_row(), _signals()) is True
    assert inv.predicate(_row(entry=120.0), _signals()) is False


# --- gate satisfaction ----------------------------------------------------

def test_gate_satisfied_pass_and_fire():
    inv = gate_satisfied(
        name="gate.proximity",
        figure="dist_to_high",
        column="dist_to_high",
        threshold=0.05,
        message="listed but does not satisfy the proximity gate — verify before acting",
    )
    assert inv.family == "gate"
    assert inv.predicate(_row(dist_to_high=0.04), _signals()) is True
    # listed-but-doesn't-actually-pass (US1-AC3)
    assert inv.predicate(_row(dist_to_high=0.09), _signals()) is False


# --- score reproduction ---------------------------------------------------

def test_score_reproduces_pass_and_fire():
    def _expected(row, signals):
        return float(row["return_12_1"]) * float(row["vol_scalar"]) / (
            1.0 + float(row["dist_to_high"])
        )

    inv = score_reproduces(compute=_expected, rel_tol=1e-3)
    assert inv.family == "score"
    assert inv.predicate(_row(), _signals()) is True
    # score does not reproduce its declared formula
    assert inv.predicate(_row(score=999.0), _signals()) is False


# --- level sanity ---------------------------------------------------------

def test_level_sanity_ordering_and_r_multiple():
    invs = level_sanity(r_multiple=4.0)
    by_name = {i.name: i for i in invs}
    ordering = by_name["level.ordering"]
    r_mult = by_name["level.r_multiple"]
    assert ordering.family == "level" and r_mult.family == "level"

    # clean: 0 < 92 < 100 < 132 and (132-100)/(100-92) == 4.0
    clean = _row(stop_loss=92.0, entry=100.0, take_profit=132.0)
    assert ordering.predicate(clean, _signals()) is True
    assert r_mult.predicate(clean, _signals()) is True

    # broken ordering: stop above entry
    assert ordering.predicate(_row(stop_loss=110.0), _signals()) is False
    # broken r-multiple: take_profit not 4R away
    assert r_mult.predicate(_row(stop_loss=92.0, entry=100.0, take_profit=108.0), _signals()) is False


# --- value domain ---------------------------------------------------------

def test_value_domain_finite_pass_and_fire():
    inv = value_domain_finite(["close", "52w_high", "return_12_1", "atr", "score"])
    assert inv.family == "value_domain"
    assert inv.predicate(_row(), _signals()) is True
    assert inv.predicate(_row(return_12_1=float("nan")), _signals()) is False
    assert inv.predicate(_row(close=np.inf), _signals()) is False


def test_value_domain_positive_pass_and_fire():
    inv = value_domain_positive(["close", "atr"])
    assert inv.predicate(_row(), _signals()) is True
    assert inv.predicate(_row(close=0.0), _signals()) is False
    assert inv.predicate(_row(atr=-1.0), _signals()) is False


def test_value_domain_return_plausible_pass_and_fire():
    inv = value_domain_return_plausible(lower=-0.95, upper=9.0)
    assert inv.figure == "return_12_1"
    assert inv.predicate(_row(return_12_1=0.30), _signals()) is True
    # the BELFB-like +221% spurious return
    assert inv.predicate(_row(return_12_1=2.21 * 100), _signals()) is False
    assert inv.predicate(_row(return_12_1=-0.99), _signals()) is False


def test_value_domain_high_plausible_pass_and_fire():
    inv = value_domain_high_plausible(h_max=12.0)
    assert inv.figure == "52w_high"
    assert inv.predicate(_row(), _signals()) is True
    # 52w high below close is impossible by construction
    assert inv.predicate(_row(**{"52w_high": 50.0}), _signals()) is False
    # absurdly high
    assert inv.predicate(_row(**{"52w_high": 100.0 * 50}), _signals()) is False


def test_value_domain_bounded_is_reusable_symmetric_guard():
    # The generic guard the value strategy reuses (FR-006): |figure| > limit fires.
    inv = value_domain_bounded(
        name="value_domain.book_to_market",
        figure="book_to_market",
        limit=25.0,
        message="book/market implausibly large — market cap is not trustworthy; verify before acting",
    )
    assert inv.family == "value_domain"
    assert inv.predicate(pd.Series({"book_to_market": 0.9}), pd.Series(dtype=object)) is True
    assert inv.predicate(pd.Series({"book_to_market": 257.0}), pd.Series(dtype=object)) is False
    # missing value is not this invariant's concern (fail-open)
    assert inv.predicate(pd.Series({"book_to_market": None}), pd.Series(dtype=object)) is True


def test_value_domain_realized_vol_floor_pass_and_fire():
    inv = value_domain_realized_vol_floor(min_annualized_vol=0.08)
    assert inv.family == "value_domain" and inv.severity == "candidate"
    assert inv.figure == "vol_scalar"

    # Normal-vol momentum name: ~30% annualized realized vol -> satisfied.
    normal = pd.Series(np.random.default_rng(0).normal(0, 0.30 / np.sqrt(252), 126))
    assert inv.predicate(_row(daily_returns=normal), _signals()) is True

    # EA-like pin: ~6% annualized realized vol -> fires.
    pinned = pd.Series(np.random.default_rng(1).normal(0, 0.06 / np.sqrt(252), 126))
    assert inv.predicate(_row(daily_returns=pinned), _signals()) is False

    # No returns window: a vol_scalar saturated at its cap is the pin signal.
    assert inv.predicate(_row(vol_scalar=2.0), _signals()) is False
    # No returns window + unsaturated scalar -> fail-open (no false positive).
    assert inv.predicate(_row(vol_scalar=1.0), _signals()) is True


# --- series integrity -----------------------------------------------------

def test_series_integrity_reads_signals_and_defaults_safe():
    invs = series_integrity(jump_max=0.40)
    by_name = {i.name: i for i in invs}
    dates = by_name["series.dates_ok"]
    jump = by_name["series.no_unexplained_jump"]
    seam = by_name["series.seam_consistent"]
    assert all(i.family == "series" for i in invs)

    # clean signals -> all satisfied
    assert dates.predicate(_row(), _signals()) is True
    assert jump.predicate(_row(), _signals()) is True
    assert seam.predicate(_row(), _signals()) is True

    # corrupted signals -> fire
    assert dates.predicate(_row(), _signals(series_dates_ok=False)) is False
    assert jump.predicate(_row(), _signals(series_max_session_move=0.80)) is False
    assert seam.predicate(_row(), _signals(seam_consistent=False)) is False

    # a known corporate action explains a large jump -> no false positive (FR-015)
    assert (
        jump.predicate(
            _row(),
            _signals(series_max_session_move=0.80, corporate_action_in_window=True),
        )
        is True
    )

    # US1 testable before US3: missing signal columns default safe (no false flag)
    empty = pd.Series(dtype=object)
    assert dates.predicate(_row(), empty) is True
    assert jump.predicate(_row(), empty) is True
    assert seam.predicate(_row(), empty) is True


def test_seam_tristate_separates_inconsistent_from_unverified():
    by_name = {i.name: i for i in series_integrity()}
    strong = by_name["series.seam_consistent"]
    soft = by_name["series.seam_unverified"]
    assert soft.family == "series" and soft.severity == "candidate"

    # consistent -> neither fires
    sig_ok = _signals(seam_consistent=True, seam_overlap_found=True)
    assert strong.predicate(_row(), sig_ok) is True
    assert soft.predicate(_row(), sig_ok) is True

    # overlap found but inconsistent -> STRONG fires, soft does not
    sig_inc = _signals(seam_consistent=False, seam_overlap_found=True)
    assert strong.predicate(_row(), sig_inc) is False
    assert soft.predicate(_row(), sig_inc) is True

    # no overlap to verify -> SOFT fires, strong does not
    sig_unv = _signals(seam_consistent=False, seam_overlap_found=False)
    assert strong.predicate(_row(), sig_unv) is True
    assert soft.predicate(_row(), sig_unv) is False

    # legacy row (no overlap signal) -> strong fires, soft satisfied (back-compat)
    sig_legacy = _signals(seam_consistent=False)
    assert strong.predicate(_row(), sig_legacy) is False
    assert soft.predicate(_row(), sig_legacy) is True


# --- identity -------------------------------------------------------------

def test_identity_single_share_class_pass_and_fire():
    inv = identity_single_share_class()
    assert inv.family == "identity"
    assert inv.predicate(_row(), _signals()) is True
    assert inv.predicate(_row(), _signals(share_class_consistent=False)) is False
    # default-safe when the signal is absent
    assert inv.predicate(_row(), pd.Series(dtype=object)) is True


# --- aggregate ------------------------------------------------------------

def test_aggregate_flag_count_is_aggregate_severity():
    inv = aggregate_flag_count()
    assert inv.severity == "aggregate"
