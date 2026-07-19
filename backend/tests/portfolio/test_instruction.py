from __future__ import annotations

import pytest

from backend.src.models.portfolio import InstructionBlock
from backend.src.portfolio.instruction import NEAR_LEVEL_PCT, derive_instruction

# Golden-fixture coverage of every precedence branch in derive_instruction
# (research Decision 2): levels-unavailable guard -> Sell -> Trim -> Hold.
# The mapper is pure presentation over already-computed status facts (FR-013);
# no new indicator/threshold is introduced and the AI sentiment score is never
# an input (FR-007, enforced structurally in test_instruction_determinism.py).


def test_sell_when_current_condition_stop_breached() -> None:
    block = derive_instruction(
        level_status="stop_breached",
        levels_state="ok",
        distance_to_stop_pct=-0.01,
        heat_headroom_pct=0.5,
        directive_enabled=True,
    )
    assert isinstance(block, InstructionBlock)
    assert block.directive == "sell"
    assert block.status_label  # always present
    assert block.rationale
    assert block.inputs.level_status == "stop_breached"
    assert block.inputs.distance_to_stop_pct == -0.01
    assert block.inputs.heat_headroom_pct == 0.5


def test_trim_when_near_stop() -> None:
    block = derive_instruction(
        level_status="holding",
        levels_state="ok",
        distance_to_stop_pct=-0.02,  # within 3% of the stop
        heat_headroom_pct=0.5,
        directive_enabled=True,
    )
    assert block.directive == "trim"


def test_trim_when_heat_ceiling_breached() -> None:
    block = derive_instruction(
        level_status="holding",
        levels_state="ok",
        distance_to_stop_pct=-0.30,  # far from the stop
        heat_headroom_pct=0.0,  # no risk headroom left
        directive_enabled=True,
    )
    assert block.directive == "trim"


def test_hold_when_healthy() -> None:
    block = derive_instruction(
        level_status="holding",
        levels_state="ok",
        distance_to_stop_pct=-0.30,
        heat_headroom_pct=0.5,
        directive_enabled=True,
    )
    assert block.directive == "hold"


def test_hold_when_target_reached() -> None:
    block = derive_instruction(
        level_status="target_reached",
        levels_state="ok",
        distance_to_stop_pct=-0.30,
        heat_headroom_pct=0.5,
        directive_enabled=True,
    )
    assert block.directive == "hold"
    assert "target" in block.status_label.lower()


def test_hold_when_gains_protected() -> None:
    block = derive_instruction(
        level_status="gains_protected",
        levels_state="ok",
        distance_to_stop_pct=-0.30,
        heat_headroom_pct=0.5,
        directive_enabled=True,
    )
    assert block.directive == "hold"


def test_levels_unavailable_yields_no_verb() -> None:
    block = derive_instruction(
        level_status="insufficient_data",
        levels_state="insufficient_data",
        distance_to_stop_pct=None,
        heat_headroom_pct=0.5,
        directive_enabled=True,
    )
    assert block.directive is None
    assert "unavailable" in block.status_label.lower()


def test_levels_unavailable_takes_precedence_over_heat() -> None:
    # Even with the heat ceiling breached, an insufficient-levels holding gets
    # no verb (edge case, FR-004) — the card still renders with a status label.
    block = derive_instruction(
        level_status="insufficient_data",
        levels_state="insufficient_data",
        distance_to_stop_pct=None,
        heat_headroom_pct=0.0,
        directive_enabled=True,
    )
    assert block.directive is None


def test_neutral_status_only_when_directive_disabled() -> None:
    # Carve-out OFF: no verb, but the neutral status/rationale still render
    # (FR-008 — the instruction section is never dropped).
    block = derive_instruction(
        level_status="stop_breached",
        levels_state="ok",
        distance_to_stop_pct=-0.01,
        heat_headroom_pct=0.5,
        directive_enabled=False,
    )
    assert block.directive is None
    assert block.status_label
    assert block.rationale


def test_near_stop_boundary_is_three_percent() -> None:
    assert NEAR_LEVEL_PCT == 0.03
    at_boundary = derive_instruction(
        level_status="holding",
        levels_state="ok",
        distance_to_stop_pct=-0.03,  # exactly 3% counts as near
        heat_headroom_pct=0.5,
        directive_enabled=True,
    )
    assert at_boundary.directive == "trim"
    just_beyond = derive_instruction(
        level_status="holding",
        levels_state="ok",
        distance_to_stop_pct=-0.0301,
        heat_headroom_pct=0.5,
        directive_enabled=True,
    )
    assert just_beyond.directive == "hold"


def test_stage_is_echoed_in_inputs() -> None:
    block = derive_instruction(
        level_status="holding",
        levels_state="ok",
        distance_to_stop_pct=-0.30,
        heat_headroom_pct=0.5,
        stage="Managing",
        directive_enabled=True,
    )
    assert block.inputs.stage == "Managing"
