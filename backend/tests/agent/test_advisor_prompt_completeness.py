from __future__ import annotations

from backend.src.agent.advisor_prompt import build_advisor_prompt
from backend.src.models.strategy import DataIntegrityWarning

FAIL_SURV = {
    "confirmed": True,
    "passed": False,
    "note": "no delisted tickers in the free bundle",
}


def test_prompt_is_complete_neutral_integrity_verbatim_and_deterministic(
    sample_result, midterm_strategy
):
    warning = "momentum figure +221% is outside the 120% plausibility bound"
    sample_result.data_suspect = True
    sample_result.data_integrity_warnings = [
        DataIntegrityWarning(
            figure="return_12_1",
            rule="value_domain.return_plausible",
            reason=warning,
        )
    ]
    sample_result.material_input_freshness = {
        "prices": "2026-06-12",
        "fundamentals": "2026-05-31",
        "regime": "2026-06-11",
    }

    first = build_advisor_prompt(
        sample_result,
        midterm_strategy,
        survivorship=FAIL_SURV,
        regime="Trending up",
    )
    second = build_advisor_prompt(
        sample_result,
        midterm_strategy,
        survivorship=FAIL_SURV,
        regime="Trending up",
    )

    assert first == second
    assert warning in first
    assert "DATA INTEGRITY WARNING" in first
    assert "survivorship" in first.lower()
    assert "optimistic" in first.lower()
    assert "no delisted tickers" in first
    assert "Prices data_as_of: 2026-06-12" in first
    assert "Fundamentals data_as_of: 2026-05-31" in first
    assert "Regime as-of: 2026-06-11" in first
    for forbidden in ("buy", "sell", "recommended", "strong buy"):
        assert forbidden not in first.lower()
