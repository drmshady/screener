from __future__ import annotations

import pytest

from backend.src.portfolio.instruction import derive_instruction

# FR-007: the instruction is deterministic and derived purely from existing
# rule-based signals. The AI sentiment score is context only and must NEVER be
# an accepted/consulted input — enforced structurally by the signature here.


def test_identical_inputs_produce_identical_block() -> None:
    kwargs = dict(
        level_status="holding",
        levels_state="ok",
        distance_to_stop_pct=-0.10,
        heat_headroom_pct=0.42,
        stage="Managing",
        directive_enabled=True,
    )
    first = derive_instruction(**kwargs)
    second = derive_instruction(**kwargs)
    assert first.model_dump() == second.model_dump()


def test_sentiment_score_is_not_an_accepted_input() -> None:
    # A sentiment score must not be consultable — passing one is a TypeError,
    # proving the mapper cannot factor sentiment into the verb (FR-007).
    with pytest.raises(TypeError):
        derive_instruction(
            level_status="holding",
            levels_state="ok",
            distance_to_stop_pct=-0.10,
            heat_headroom_pct=0.42,
            directive_enabled=True,
            sentiment_score=0.9,
        )


def test_verb_independent_of_stage() -> None:
    # Lifecycle stage refines the neutral label but must not change the verb,
    # which stays derived from breach/heat facts (research Decision 2).
    base = dict(
        level_status="stop_breached",
        levels_state="ok",
        distance_to_stop_pct=-0.01,
        heat_headroom_pct=0.5,
        directive_enabled=True,
    )
    assert (
        derive_instruction(stage="Owned", **base).directive
        == derive_instruction(stage="Managing", **base).directive
        == "sell"
    )
