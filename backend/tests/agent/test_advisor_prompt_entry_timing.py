from __future__ import annotations

import pytest

from backend.src.agent.advisor_prompt import build_screen_advisor_prompt
from backend.src.models.strategy import (
    Candidate,
    Disqualifier,
    EntryComponent,
    EntryDiagnostics,
    EntryTimingClassification,
    GateResult,
    ScreenResult,
)

FAIL_SURV = {"confirmed": True, "passed": False, "note": "no delisted tickers in the free bundle"}


def _entry_timing() -> EntryTimingClassification:
    """A NOT-entry-ready momentum classification: one failing component plus a
    triggered (non-forcing) short-lived-catalyst caution."""
    return EntryTimingClassification(
        state="not_entry_ready",
        components=[
            EntryComponent(name="pivot_proximity", status="pass", value=0.02, reason="near pivot"),
            EntryComponent(name="trend", status="pass", value=1.0, reason="above 200-day SMA"),
            EntryComponent(
                name="volume_confirmation", status="fail", value=1.10, reason="weak-volume breakout"
            ),
            EntryComponent(name="base_maturity", status="pass", value=9.0, reason="mature base"),
            EntryComponent(name="base_depth", status="pass", value=0.18, reason="base depth in range"),
            EntryComponent(
                name="not_extended", status="pass", value=0.12, reason="not extended from SMA-200"
            ),
        ],
        disqualifiers=[
            Disqualifier(
                name="climax_top",
                triggered=False,
                value=None,
                reason="no climax-top exhaustion signal",
                forces_not_entry_ready=True,
            ),
            Disqualifier(
                name="huge_gap",
                triggered=False,
                value=None,
                reason="no gap-extension signal",
                forces_not_entry_ready=True,
            ),
            Disqualifier(
                name="short_lived_catalyst",
                triggered=True,
                value=None,
                reason="elevated post-catalyst pullback risk",
                forces_not_entry_ready=False,
            ),
        ],
        diagnostics=EntryDiagnostics(
            pivot=152.30,
            base_type="cup_with_handle",
            base_length_weeks=9.0,
            base_depth=0.18,
            breakout_volume_ratio=1.10,
            dist_above_pivot=0.02,
            dist_above_sma_200=0.12,
        ),
        summary="weak-volume breakout; elevated post-catalyst pullback risk",
    )


def _candidate(ticker: str, rank: int, *, entry_timing: EntryTimingClassification | None) -> Candidate:
    return Candidate(
        ticker=ticker,
        name=f"{ticker} Inc",
        sector="Technology",
        strategy_slug="midterm_52w_high_momentum",
        current_price="150.00",
        entry="150.00",
        stop_loss="142.00",
        take_profit="174.00",
        rank=rank,
        score=round(1.0 / rank, 4),
        return_12_1=0.5 / rank,
        vol_scalar=0.9,
        dist_to_high=0.01 * rank,
        atr=3.0,
        reason="matched",
        gate_results=[
            GateResult(gate="52-week-high proximity", status="pass", detail="1.0% below high")
        ],
        recent_8k_count_30d=0,
        entry_timing=entry_timing,
    )


def _screen(cands: list[Candidate]) -> ScreenResult:
    return ScreenResult(
        id="screen-1",
        strategy_slug="midterm_52w_high_momentum",
        as_of_date="2026-06-27",
        parameters_snapshot={},
        filters_snapshot={},
        candidate_count=len(cands),
        candidates=cands,
        computed_at="2026-06-27T00:00:00Z",
        data_as_of="2026-06-27T00:00:00Z",
        disclaimer="This product is for informational purposes only and does not constitute financial advice. It does not place trades.",
        regime="Trending up",
    )


def test_entry_timing_block_present_for_momentum(midterm_strategy):
    screen = _screen([_candidate("AAA", 1, entry_timing=_entry_timing())])
    prompt = build_screen_advisor_prompt(screen, midterm_strategy, survivorship=FAIL_SURV)

    # Overall state + summary
    assert "NOT-ENTRY-READY" in prompt
    assert "weak-volume breakout" in prompt
    # Each component status surfaced
    assert "volume_confirmation=FAIL" in prompt
    assert "pivot_proximity=PASS" in prompt
    # Cited to its sources, framed as a STATE not a command
    assert "Minervini 2013" in prompt
    assert "Faber 2007" in prompt
    assert "not a directive" in prompt
    # Triggered short-lived-catalyst caution described as risk, never an instruction
    assert "short_lived_catalyst" in prompt
    assert "describes risk" in prompt
    # Base/pivot diagnostics carry the hard numbers
    assert "cup_with_handle" in prompt
    assert "152.30" in prompt
    assert "1.10x" in prompt  # breakout volume ratio


def test_entry_timing_block_zero_directive(midterm_strategy):
    screen = _screen([_candidate("AAA", 1, entry_timing=_entry_timing())])
    prompt = build_screen_advisor_prompt(screen, midterm_strategy, survivorship=FAIL_SURV)
    et_lines = [ln for ln in prompt.splitlines() if "entry" in ln.lower() and "timing" in ln.lower()]
    block = "\n".join(
        ln for ln in prompt.splitlines()
        if ln.strip().startswith("- Entry-timing")
        or ln.strip().startswith("- Components")
        or ln.strip().startswith("- Disqualifiers")
        or ln.strip().startswith("- Base/pivot")
        or ln.strip().startswith("- Note: entry-undetermined")
    )
    assert et_lines, "expected an entry-timing line in the prompt"
    for banned in ("buy", "sell", "recommended", "strong buy", "should buy"):
        assert banned not in block.lower()


def test_no_entry_timing_section_when_absent(midterm_strategy):
    # Default-off / non-momentum payloads (entry_timing=None) add no section.
    screen = _screen([_candidate("AAA", 1, entry_timing=None)])
    prompt = build_screen_advisor_prompt(screen, midterm_strategy, survivorship=FAIL_SURV)
    assert "Entry-timing" not in prompt


def test_research_and_arabic_summary_instructions_present(midterm_strategy):
    screen = _screen([_candidate("AAA", 1, entry_timing=_entry_timing())])
    prompt = build_screen_advisor_prompt(screen, midterm_strategy, survivorship=FAIL_SURV)
    # News + analyst web-search instructions
    assert "Search recent NEWS" in prompt
    assert "ANALYST opinion" in prompt
    # Cross-candidate comparison
    assert "COMPARE the candidates" in prompt
    # Brief Arabic summary of the strongest names
    assert "ARABIC" in prompt
    assert "العربية" in prompt
    # News must never overwrite a computed gate (rule #9)
    assert "never overwrite a computed gate" in prompt


def test_research_instructions_stay_neutral_when_directive_off(midterm_strategy):
    screen = _screen([_candidate("AAA", 1, entry_timing=_entry_timing())])
    prompt = build_screen_advisor_prompt(
        screen, midterm_strategy, survivorship=FAIL_SURV, directive=False
    )
    # Non-directive framing for "best": research, not a buy list.
    assert "strongest screen matches for further research" in prompt
    for banned in ("buy", "sell", "recommended", "strong buy"):
        assert banned not in prompt.lower()


def test_research_instructions_directive_when_enabled(midterm_strategy):
    screen = _screen([_candidate("AAA", 1, entry_timing=_entry_timing())])
    prompt = build_screen_advisor_prompt(
        screen, midterm_strategy, survivorship=FAIL_SURV, directive=True
    )
    assert "best-to-worst to act on now" in prompt
    assert "ARABIC" in prompt
