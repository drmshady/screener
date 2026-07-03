"""Golden-fixture tests for the pure fit synthesis (Feature 016, T004/T007).

``score_fit`` is a pure function over independent boolean facts; these fixtures
pin the deterministic weighted score, the band derivation, ``failed_facts``, the
neutral rationale, and the gated directive vocabulary. No I/O, no flags.
"""

from __future__ import annotations

import re

from backend.src.models.pipeline import FitFacts
from backend.src.pipeline.fit import FIT_WEIGHTS, score_fit

# Directive verbs the neutral rationale must never contain (Playwright lints the
# same class of words on the reworked home).
_DIRECTIVE_VERB = re.compile(
    r"\b(buy|sell|take|pass|hold off|size down|recommend|strong buy)\b", re.IGNORECASE
)


def _all(value: bool) -> FitFacts:
    return FitFacts(
        entry_ready=value,
        meaningful_size_survives=value,
        heat_headroom_ok=value,
        sector_room_ok=value,
        not_overconcentrated=value,
        regime_allows_entries=value,
        reward_to_risk_ok=value,
        cash_sufficient=value,
    )


def test_weights_sum_to_100() -> None:
    assert sum(FIT_WEIGHTS.values()) == 100


def test_all_pass_is_strong_fit() -> None:
    result = score_fit(_all(True))
    assert result.score == 100
    assert result.fit_band == "strong_fit"
    assert result.failed_facts == []
    assert not _DIRECTIVE_VERB.search(result.rationale)
    # Directive omitted unless explicitly requested.
    assert result.directive_label is None


def test_single_nonblocking_fail_is_partial_fit() -> None:
    facts = _all(True).model_copy(update={"reward_to_risk_ok": False})
    result = score_fit(facts)
    assert result.score == 100 - FIT_WEIGHTS["reward_to_risk_ok"]  # 88
    assert result.fit_band == "partial_fit"
    assert result.failed_facts == ["reward_to_risk_ok"]
    assert "reward-to-risk" in result.rationale
    assert not _DIRECTIVE_VERB.search(result.rationale)


def test_blocking_fact_collapses_band_regardless_of_score() -> None:
    # Only entry_ready fails: every other (heavily weighted) fact passes, but a
    # blocking fact forces "blocked" so a high score can never be presented.
    facts = _all(True).model_copy(update={"entry_ready": False})
    result = score_fit(facts)
    assert result.score == 100 - FIT_WEIGHTS["entry_ready"]  # 75
    assert result.fit_band == "blocked"
    assert result.failed_facts == ["entry_ready"]


def test_all_blocked() -> None:
    result = score_fit(_all(False))
    assert result.score == 0
    assert result.fit_band == "blocked"
    assert len(result.failed_facts) == len(FIT_WEIGHTS)
    assert not _DIRECTIVE_VERB.search(result.rationale)


def test_directive_label_only_when_requested() -> None:
    assert score_fit(_all(True), directive=True).directive_label == "consider_entry"
    assert score_fit(_all(False), directive=True).directive_label == "pass"
    partial = _all(True).model_copy(update={"reward_to_risk_ok": False})
    assert score_fit(partial, directive=True).directive_label == "size_down"


def test_deterministic_stable_output() -> None:
    facts = _all(True).model_copy(update={"sector_room_ok": False})
    first = score_fit(facts)
    second = score_fit(facts)
    assert first.model_dump() == second.model_dump()
    # failed_facts preserves the documented weight order (stable tie-break key).
    assert first.failed_facts == ["sector_room_ok"]
