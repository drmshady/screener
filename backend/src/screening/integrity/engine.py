"""Strategy-agnostic output-contract evaluation engine (feature 008,
output-contract.schema.md, FR-001).

``evaluate_contract`` runs every invariant of a strategy's
:class:`OutputContract` against every returned candidate row plus that row's
precomputed series-integrity ``signals`` (Decision 7). It has **no per-strategy
branching** — adding or altering a contract never touches this engine.

Guarantees (output-contract.schema.md):
  * pure / deterministic — no network, no wall-clock;
  * never raises on a single bad row — a predicate that errors flags that row
    rather than crashing the screen (US1 "the run does not crash");
  * never drops a row (flag-not-exclude, FR-017) and never mutates the caller's
    DataFrame in place.

Output: a copy of ``results_df`` with two added columns —
``data_integrity_warnings`` (list of candidate-severity
:class:`ContractViolation`) and ``data_suspect`` (bool). Aggregate-severity
breaches are returned separately in ``df.attrs["integrity_notes"]`` for the
caller to append to ``data_notes`` (FR-004).
"""
from __future__ import annotations

from typing import List, Optional

import pandas as pd

from backend.src.screening.integrity.contract import ContractViolation, OutputContract


def evaluate_contract(
    results_df: pd.DataFrame,
    contract: OutputContract,
    *,
    snapshot_signals: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Annotate ``results_df`` with contract violations.

    ``snapshot_signals`` (optional) carries the per-row series-integrity columns
    (data-model §8); when omitted, the candidate row itself is passed as the
    signals to each predicate. Aligned to ``results_df`` by index.
    """
    df = results_df.copy()

    warnings_col: List[List[ContractViolation]] = []
    suspect_col: List[bool] = []
    integrity_notes: List[str] = []
    aggregate_seen: set[str] = set()

    has_signals = snapshot_signals is not None

    for idx, row in df.iterrows():
        if has_signals and idx in snapshot_signals.index:
            signals = snapshot_signals.loc[idx]
        else:
            signals = row

        row_violations: List[ContractViolation] = []
        suspect = False

        for inv in contract.invariants:
            try:
                satisfied = bool(inv.predicate(row, signals))
            except Exception:
                # A predicate that errors flags the row (it cannot be proven
                # satisfied) rather than crashing the screen.
                satisfied = False

            if satisfied:
                continue

            violation = ContractViolation(
                invariant_name=inv.name,
                family=inv.family,
                figure=inv.figure,
                reason=inv.message,
                severity=inv.severity,
            )

            if inv.severity == "candidate":
                row_violations.append(violation)
                suspect = True
            else:  # aggregate -> recorded once at screen level
                if inv.name not in aggregate_seen:
                    aggregate_seen.add(inv.name)
                    integrity_notes.append(violation.reason)

        warnings_col.append(row_violations)
        suspect_col.append(suspect)

    # object dtype so each cell holds a Python list of violation objects.
    df["data_integrity_warnings"] = pd.Series(warnings_col, index=df.index, dtype=object)
    df["data_suspect"] = pd.Series(suspect_col, index=df.index, dtype=bool)
    df.attrs["integrity_notes"] = integrity_notes

    return df
