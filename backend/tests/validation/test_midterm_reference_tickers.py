from __future__ import annotations

from backend.src.strategies import midterm_52w_high_momentum as midterm

from .conftest import first_rejecting_gate


def _first_gates(frozen_snapshot) -> dict[str, str | None]:
    """First-rejecting hard gate per ticker on the frozen prepared universe.

    Data-driven and ticker-agnostic: nothing here names a particular stock, so
    benign EOD price drift never breaks the correctness floor — only a genuine
    gate-logic defect can.
    """
    df = frozen_snapshot.us_prepared
    return {
        str(t): first_rejecting_gate(df[df["ticker"] == t].iloc[0], frozen_snapshot)
        for t in df["ticker"].astype(str)
    }


def test_every_candidate_clears_every_hard_gate(frozen_snapshot) -> None:
    """FR-006 correctness floor: every selected candidate clears every hard gate.

    A name returned by the live momentum ``rules()`` must have no first-rejecting
    gate. A candidate that secretly fails a hard gate would be a correctness
    defect (a leaked rejection).
    """
    first_gates = _first_gates(frozen_snapshot)
    candidates = set(midterm.rules(frozen_snapshot.us)["ticker"].astype(str))
    assert candidates, "expected a non-empty candidate set on the frozen snapshot"
    leaked = {t: first_gates[t] for t in candidates if first_gates.get(t) is not None}
    assert not leaked, f"candidates that fail a hard gate: {leaked}"


def test_every_candidate_is_within_the_proximity_band(frozen_snapshot) -> None:
    """Every candidate sits within the 52-week-high proximity band.

    Verifies the proximity gate against the declared default (untouched); names
    that drift outside the band are correctly excluded, no matter which they are.
    """
    df = frozen_snapshot.us_prepared
    prox = midterm.PARAMETERS["proximity_pct"].default
    candidates = set(midterm.rules(frozen_snapshot.us)["ticker"].astype(str))
    outside = {
        t: float(df[df["ticker"] == t].iloc[0]["dist_to_high"])
        for t in candidates
        if float(df[df["ticker"] == t].iloc[0]["dist_to_high"]) > prox
    }
    assert not outside, f"candidates outside the proximity band (<= {prox}): {outside}"


def test_candidates_are_a_subset_of_hard_gate_survivors(frozen_snapshot) -> None:
    """Candidates are a subset of the clean hard-gate survivors.

    Downstream selection (sector-strength gate, ranking) may only ever *remove*
    clean names — it must never admit a name that fails a hard gate.
    """
    first_gates = _first_gates(frozen_snapshot)
    clean = {t for t, gate in first_gates.items() if gate is None}
    candidates = set(midterm.rules(frozen_snapshot.us)["ticker"].astype(str))
    assert candidates <= clean, (
        f"candidates failing a hard gate: {sorted(candidates - clean)}"
    )


def test_proximity_and_quality_gates_actually_reject(frozen_snapshot) -> None:
    """Both the data-volatile proximity gate and the fundamental quality gate
    demonstrably fire on the real universe — some name is rejected first at
    proximity and some name is rejected first at quality."""
    rejected_at = set(_first_gates(frozen_snapshot).values())
    assert "proximity" in rejected_at, "expected at least one proximity rejection"
    assert "quality" in rejected_at, "expected at least one quality rejection"
