"""T008 [US1] — the momentum pilot declares its output contract (FR-003).

Written FIRST: must FAIL before ``midterm_52w_high_momentum.OUTPUT_CONTRACT``
exists (T012).

Asserts the contract declares all six FR-003 invariant families (coherence, gate,
score, level, value_domain, series) — plus the identity/share-class guard and the
aggregate flag-count note — with the correct severities (candidate vs aggregate).
"""
from __future__ import annotations

from backend.src.screening.integrity.contract import OutputContract
from backend.src.strategies import midterm_52w_high_momentum as mom
from backend.src.strategies._registry import registry


def test_strategy_exposes_output_contract_object():
    contract = mom.OUTPUT_CONTRACT
    assert isinstance(contract, OutputContract)
    assert contract.strategy_slug == "midterm_52w_high_momentum"
    assert contract.invariants  # non-empty


def test_registered_strategy_carries_the_contract():
    s = registry.get("midterm_52w_high_momentum")
    assert s is not None
    assert s.output_contract is mom.OUTPUT_CONTRACT


def test_declares_all_six_fr003_families():
    families = {inv.family for inv in mom.OUTPUT_CONTRACT.invariants}
    assert {
        "coherence",
        "gate",
        "score",
        "level",
        "value_domain",
        "series",
    } <= families
    # plus the share-class identity guard (FR-014)
    assert "identity" in families


def test_severities_are_candidate_except_the_flag_count_note():
    by_name = {inv.name: inv for inv in mom.OUTPUT_CONTRACT.invariants}
    # Every concrete figure guard is candidate-severity (demotes + warns).
    for name in (
        "coherence.dist_to_high",
        "coherence.entry_eq_close",
        "gate.proximity",
        "score.reproduces",
        "level.ordering",
        "level.r_multiple",
        "value_domain.finite",
        "value_domain.positive",
        "value_domain.return_plausible",
        "value_domain.high_plausible",
        "series.dates_ok",
        "series.no_unexplained_jump",
        "series.seam_consistent",
        "series.seam_unverified",
        "identity.single_share_class",
    ):
        assert name in by_name, f"missing invariant {name}"
        assert by_name[name].severity == "candidate"

    assert "aggregate.flag_count" in by_name
    assert by_name["aggregate.flag_count"].severity == "aggregate"


def test_every_invariant_has_an_actionable_message():
    for inv in mom.OUTPUT_CONTRACT.invariants:
        assert inv.message.strip()
        if inv.severity == "candidate":
            # operator-facing, ends with the verify-before-acting intent
            assert "verify before acting" in inv.message.lower()
