from __future__ import annotations

from pathlib import Path

from backend.src.agent.advisor_prompt import (
    build_advisor_prompt,
    load_survivorship_status,
)

FAIL_SURV = {"confirmed": True, "passed": False, "note": "no delisted tickers in the free bundle"}
PASS_SURV = {"confirmed": True, "passed": True, "note": "delisted coverage present"}


# --- US1: complete prompt ---------------------------------------------------


def test_prompt_contains_candidate_identity_levels_and_gates(sample_result, midterm_strategy):
    prompt = build_advisor_prompt(
        sample_result, midterm_strategy, survivorship=FAIL_SURV, regime="Trending up"
    )
    # identity
    assert "TEST" in prompt and "Test Corp" in prompt and "Technology" in prompt
    # every gate appears with its status tag
    assert "52-week-high proximity" in prompt
    assert "[PASS]" in prompt and "[FAIL]" in prompt and "[SKIPPED]" in prompt
    # levels + reward:risk (130-100)/(100-90) = 3.00R
    assert "100.00" in prompt and "90.00" in prompt and "130.00" in prompt
    assert "3.00R" in prompt
    # regime + favorability (Trending up -> Favorable)
    assert "Trending up" in prompt and "Favorable" in prompt
    # as-of + disclaimer
    assert "2026-06-12" in prompt
    assert "informational purposes only" in prompt


def test_prompt_includes_ranking_inputs_and_fundamentals(sample_result, midterm_strategy):
    prompt = build_advisor_prompt(
        sample_result, midterm_strategy, survivorship=FAIL_SURV, regime="Trending up"
    )
    # ranking inputs the advisor needs to actually rank
    assert "Ranking inputs:" in prompt
    assert "12-1 momentum" in prompt and "vol_scalar" in prompt and "dist_to_high" in prompt
    # raw fundamentals behind the quality/tilt gates
    assert "Fundamentals:" in prompt
    assert "D/E" in prompt and "ATR" in prompt and "gp/assets" in prompt
    # strategy context explains the score formula + per-sector cap
    assert "return_12_1 × vol_scalar" in prompt
    assert "per sector" in prompt


def test_prompt_is_deterministic_and_has_no_wallclock(sample_result, midterm_strategy):
    a = build_advisor_prompt(sample_result, midterm_strategy, survivorship=FAIL_SURV, regime="Range-bound")
    b = build_advisor_prompt(sample_result, midterm_strategy, survivorship=FAIL_SURV, regime="Range-bound")
    assert a == b
    # The body's only date is the snapshot's date (YYYY-MM-DD); no wall-clock time.
    assert "T00:00:00Z" not in a  # the full ISO data_as_of must not leak in
    assert "Data freshness: end-of-day, as of 2026-06-12." in a


# --- US3: honesty -----------------------------------------------------------


def test_honesty_block_warns_when_survivorship_fails(sample_result, midterm_strategy):
    prompt = build_advisor_prompt(sample_result, midterm_strategy, survivorship=FAIL_SURV)
    lower = prompt.lower()
    assert "survivorship" in lower
    assert "optimistic" in lower
    assert "no delisted tickers" in lower


def test_skipped_gates_are_distinguished_from_passes(sample_result, midterm_strategy):
    prompt = build_advisor_prompt(sample_result, midterm_strategy, survivorship=FAIL_SURV)
    # the skipped gate is flagged inline as not a real pass ...
    assert "not a real pass" in prompt
    # ... and called out in the honesty block's data-gaps line
    assert "Low asset growth" in prompt
    assert "did NOT" in prompt or "did not" in prompt.lower()
    assert "informational purposes only" in prompt


def test_unconfirmed_when_artifact_missing(sample_result, midterm_strategy, tmp_path):
    status = load_survivorship_status(tmp_path / "does-not-exist.json")
    assert status["confirmed"] is False
    prompt = build_advisor_prompt(sample_result, midterm_strategy, survivorship=status)
    assert "UNCONFIRMED" in prompt
    assert "passes its survivorship" not in prompt


def test_real_artifact_currently_fails_survivorship():
    # Anchored to the committed artifact: survivorship_bias.passed is false today.
    status = load_survivorship_status()
    assert status["confirmed"] is True
    assert status["passed"] is False


# --- US2: self-containment + drift -----------------------------------------


def test_prompt_is_self_contained(sample_result, midterm_strategy):
    prompt = build_advisor_prompt(sample_result, midterm_strategy, survivorship=FAIL_SURV)
    assert midterm_strategy.name in prompt
    assert midterm_strategy.citation in prompt  # "George & Hwang (2004)"
    assert midterm_strategy.timeframe in prompt
    hold = midterm_strategy.holding_period_days
    assert f"{hold['min']}" in prompt and f"{hold['max']}" in prompt


def test_every_declared_modification_appears(sample_result, midterm_strategy):
    prompt = build_advisor_prompt(sample_result, midterm_strategy, survivorship=FAIL_SURV)
    for mod in midterm_strategy.modifications:
        assert mod.name in prompt, f"modification missing from prompt: {mod.name}"
        assert mod.citation in prompt, f"citation missing from prompt: {mod.citation}"
