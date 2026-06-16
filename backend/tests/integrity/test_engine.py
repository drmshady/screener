"""T005 [Foundational] — strategy-agnostic contract engine (data-model §1-§3,
output-contract.schema.md).

Written FIRST: must FAIL before ``integrity/engine.py`` exists (T006).

A toy contract over a small DataFrame must:
  * flag dirty rows with per-row ``ContractViolation`` lists + ``data_suspect``;
  * leave clean rows untouched — no false positives (SC-002);
  * route aggregate-severity breaches to ``df.attrs["integrity_notes"]``,
    separate from per-candidate warnings (T006);
  * flag (not crash) a row whose predicate raises (US1 "the run does not crash");
  * be deterministic — same input -> identical warning set (FR-024/SC-005), the
    observable proxy for "no re-fetch / no I/O / no wall-clock".
"""
from __future__ import annotations

import pandas as pd

from backend.src.screening.integrity.contract import Invariant, OutputContract
from backend.src.screening.integrity.engine import evaluate_contract


def _positive_close() -> Invariant:
    return Invariant(
        name="value_domain.positive",
        family="value_domain",
        severity="candidate",
        predicate=lambda row, signals: float(row["close"]) > 0,
        figure="close",
        message="close is not positive — verify before acting",
    )


def _entry_eq_close() -> Invariant:
    return Invariant(
        name="coherence.entry_eq_close",
        family="coherence",
        severity="candidate",
        predicate=lambda row, signals: abs(float(row["entry"]) - float(row["close"])) <= 0.01,
        figure="entry",
        message="entry does not equal close — verify before acting",
    )


def _toy_contract() -> OutputContract:
    return OutputContract(
        strategy_slug="toy",
        invariants=[_positive_close(), _entry_eq_close()],
    )


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ticker": "AAA", "close": 10.0, "entry": 10.0},  # clean
            {"ticker": "BBB", "close": -1.0, "entry": -1.0},  # close not positive
            {"ticker": "CCC", "close": 20.0, "entry": 25.0},  # entry != close
        ]
    )


def test_clean_row_raises_no_warning():
    out = evaluate_contract(_frame(), _toy_contract())
    aaa = out.loc[out["ticker"] == "AAA"].iloc[0]
    assert aaa["data_suspect"] is False or aaa["data_suspect"] == False  # noqa: E712
    assert list(aaa["data_integrity_warnings"]) == []


def test_dirty_rows_flagged_with_specific_violation():
    out = evaluate_contract(_frame(), _toy_contract())

    bbb = out.loc[out["ticker"] == "BBB"].iloc[0]
    assert bool(bbb["data_suspect"]) is True
    bbb_v = list(bbb["data_integrity_warnings"])
    assert len(bbb_v) == 1
    assert bbb_v[0].invariant_name == "value_domain.positive"
    assert bbb_v[0].figure == "close"
    assert bbb_v[0].severity == "candidate"

    ccc = out.loc[out["ticker"] == "CCC"].iloc[0]
    assert bool(ccc["data_suspect"]) is True
    ccc_v = list(ccc["data_integrity_warnings"])
    assert len(ccc_v) == 1
    assert ccc_v[0].invariant_name == "coherence.entry_eq_close"


def test_no_false_positive_on_all_clean_frame():
    df = pd.DataFrame(
        [
            {"ticker": "AAA", "close": 10.0, "entry": 10.0},
            {"ticker": "DDD", "close": 30.0, "entry": 30.0},
        ]
    )
    out = evaluate_contract(df, _toy_contract())
    assert not out["data_suspect"].any()
    assert all(len(list(v)) == 0 for v in out["data_integrity_warnings"])


def test_aggregate_severity_routes_to_integrity_notes_not_rows():
    contract = OutputContract(
        strategy_slug="toy",
        invariants=[
            Invariant(
                name="aggregate.always_fails",
                family="value_domain",
                severity="aggregate",
                predicate=lambda row, signals: False,
                figure=None,
                message="aggregate breach noted once",
            )
        ],
    )
    out = evaluate_contract(_frame(), contract)
    # No per-candidate warnings for an aggregate invariant.
    assert not out["data_suspect"].any()
    assert all(len(list(v)) == 0 for v in out["data_integrity_warnings"])
    # Recorded once at screen level.
    notes = out.attrs.get("integrity_notes", [])
    assert len(notes) == 1
    assert "aggregate breach noted once" in notes[0]


def test_erroring_predicate_flags_row_without_crashing():
    def _boom(row, signals):  # noqa: ANN001
        raise ValueError("predicate blew up")

    contract = OutputContract(
        strategy_slug="toy",
        invariants=[
            Invariant(
                name="value_domain.finite",
                family="value_domain",
                severity="candidate",
                predicate=_boom,
                figure="close",
                message="figure could not be validated — verify before acting",
            )
        ],
    )
    out = evaluate_contract(_frame(), contract)  # must not raise
    assert out["data_suspect"].all()
    assert all(len(list(v)) == 1 for v in out["data_integrity_warnings"])


def test_deterministic_warning_set_across_runs():
    a = evaluate_contract(_frame(), _toy_contract())
    b = evaluate_contract(_frame(), _toy_contract())
    a_set = [
        (t, tuple(v.invariant_name for v in vs))
        for t, vs in zip(a["ticker"], a["data_integrity_warnings"])
    ]
    b_set = [
        (t, tuple(v.invariant_name for v in vs))
        for t, vs in zip(b["ticker"], b["data_integrity_warnings"])
    ]
    assert a_set == b_set


def test_does_not_mutate_input_frame():
    df = _frame()
    before_cols = list(df.columns)
    evaluate_contract(df, _toy_contract())
    assert list(df.columns) == before_cols  # no in-place column added
