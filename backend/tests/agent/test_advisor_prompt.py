from __future__ import annotations

from backend.src.agent.advisor_prompt import (
    build_advisor_prompt,
    build_screen_advisor_prompt,
)
from backend.src.models.strategy import Candidate, GateResult, ScreenResult

FAIL_SURV = {
    "confirmed": True,
    "passed": False,
    "note": "no delisted tickers in the free bundle",
}


def test_single_prompt_names_each_material_input_freshness(
    sample_result, midterm_strategy
):
    sample_result.material_input_freshness = {
        "prices": "2026-06-12",
        "fundamentals": "2026-05-31",
        "regime": "2026-06-11",
    }

    prompt = build_advisor_prompt(
        sample_result,
        midterm_strategy,
        survivorship=FAIL_SURV,
        regime="Trending up",
    )

    assert "Prices data_as_of: 2026-06-12" in prompt
    assert "Fundamentals data_as_of: 2026-05-31" in prompt
    assert "Regime as-of: 2026-06-11" in prompt
    assert "Material input freshness: prices 2026-06-12; fundamentals 2026-05-31; regime 2026-06-11." in prompt


def test_batch_prompt_names_each_material_input_freshness(midterm_strategy):
    candidate = Candidate(
        ticker="AAA",
        name="AAA Inc",
        sector="Technology",
        current_price="100.00",
        entry="100.00",
        stop_loss="90.00",
        take_profit="130.00",
        rank=1,
        score=1.0,
        reason="matched",
        gate_results=[
            GateResult(gate="52-week-high proximity", status="pass", detail="near high")
        ],
    )
    screen = ScreenResult(
        id="screen-1",
        strategy_slug="midterm_52w_high_momentum",
        as_of_date="2026-06-12",
        parameters_snapshot={},
        filters_snapshot={},
        candidate_count=1,
        candidates=[candidate],
        computed_at="2026-06-12T00:00:00Z",
        data_as_of="2026-06-12T00:00:00Z",
        disclaimer="This product is for informational purposes only.",
        regime="Trending up",
        material_input_freshness={
            "prices": "2026-06-12",
            "fundamentals": "2026-05-31",
            "regime": "2026-06-11",
        },
    )

    prompt = build_screen_advisor_prompt(
        screen, midterm_strategy, survivorship=FAIL_SURV
    )

    assert "Prices data_as_of: 2026-06-12" in prompt
    assert "Fundamentals data_as_of: 2026-05-31" in prompt
    assert "Regime as-of: 2026-06-11" in prompt
    assert "Material input freshness: prices 2026-06-12; fundamentals 2026-05-31; regime 2026-06-11." in prompt
