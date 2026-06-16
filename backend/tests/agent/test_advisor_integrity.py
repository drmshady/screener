from __future__ import annotations

import pytest
from backend.src.agent.advisor_prompt import (
    build_advisor_prompt,
    build_screen_advisor_prompt,
)
from backend.src.models.strategy import DataIntegrityWarning, ScreenResult, Candidate

FAIL_SURV = {"confirmed": True, "passed": False, "note": "no delisted tickers"}

def test_prompt_includes_integrity_warning_for_flagged_candidate(sample_result, midterm_strategy):
    # Add a data integrity warning to the sample result
    sample_result.data_suspect = True
    sample_result.data_integrity_warnings = [
        DataIntegrityWarning(
            figure="return_12_1",
            rule="value_domain",
            reason="momentum figure +221% is outside the 120% plausibility bound"
        )
    ]
    
    prompt = build_advisor_prompt(
        sample_result, midterm_strategy, survivorship=FAIL_SURV
    )
    
    # Verify the warning reason travels verbatim into the prompt
    assert "momentum figure +221% is outside the 120% plausibility bound" in prompt
    assert "DATA INTEGRITY WARNING" in prompt or "integrity" in prompt.lower()


def test_batch_prompt_includes_integrity_warning_for_flagged_candidate(sample_result, midterm_strategy):
    # Create a dummy ScreenResult with one flagged candidate
    flagged_candidate = Candidate(
        ticker="BELFB",
        name="Bel Fuse Inc.",
        sector="Electronic Components",
        current_price="65.00",
        entry="65.00",
        stop_loss="58.50",
        take_profit="84.50",
        rank=1,
        score=0.85,
        reason="Match",
        data_suspect=True,
        data_integrity_warnings=[
            DataIntegrityWarning(
                figure="52w_high",
                rule="coherence",
                reason="52w-high 45.00 is below current price 65.00"
            )
        ],
        gate_results=sample_result.gate_results
    )
    
    screen = ScreenResult(
        id="test-id",
        strategy_slug="midterm_52w_high_momentum",
        as_of_date="2026-06-12",
        parameters_snapshot={},
        filters_snapshot={},
        candidate_count=1,
        candidates=[flagged_candidate],
        computed_at="2026-06-12T12:00:00Z",
        data_as_of="2026-06-12",
        disclaimer="Disclaimer",
    )
    
    prompt = build_screen_advisor_prompt(
        screen, midterm_strategy, survivorship=FAIL_SURV
    )
    
    # Verify the warning reason travels verbatim into the batch prompt
    assert "52w-high 45.00 is below current price 65.00" in prompt


def test_prompt_omits_integrity_block_for_clean_candidate(sample_result, midterm_strategy):
    # sample_result has no integrity warnings by default
    prompt = build_advisor_prompt(
        sample_result, midterm_strategy, survivorship=FAIL_SURV
    )
    
    # Should not contain integrity warning language
    assert "DATA INTEGRITY WARNING" not in prompt
    assert "integrity" not in prompt.lower() or "survivorship status" in prompt.lower()
