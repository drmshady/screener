"""Advisor-prompt export for the value strategy (FR-016)."""
from backend.src import strategies as _strategies  # noqa: F401
from backend.src.agent.advisor_prompt import (
    _DIRECTIVE_WORDS,
    build_advisor_prompt,
    load_survivorship_status,
)
from backend.src.models.strategy import AnalyzeResponse, GateResult
from backend.src.strategies._registry import registry


def _value_result() -> AnalyzeResponse:
    return AnalyzeResponse(
        ticker="VALU", name="Valu Inc", sector="Tech",
        strategy="midterm_value_composite", as_of="2024-12-31",
        would_be_selected=True, current_price="50.00", entry="50.00",
        stop_loss="45.00", tighter_stop_loss="46.00", take_profit="70.00",
        atr=1.0, debt_to_equity=1.0,
        value_composite=0.82, book_to_market=0.9, earnings_yield=0.12,
        cashflow_yield=0.10, sales_yield=2.0, f_score=8, f_score_evaluable=9,
        gate_results=[
            GateResult(gate="Value composite", status="pass", detail="composite 0.82 >= cut 0.50"),
            GateResult(gate="Piotroski F-Score", status="pass", detail="F-Score 8/9 >= floor 6"),
            GateResult(gate="Leverage sanity", status="pass", detail="debt/equity 1.00 <= 2"),
        ],
        data_notes=[], data_as_of="2024-12-31T21:00:00Z", disclaimer="Not advice.",
    )


def test_prompt_carries_value_citations_and_diagnostics():
    strategy = registry.get("midterm_value_composite")
    prompt = build_advisor_prompt(
        _value_result(), strategy,
        survivorship={"confirmed": True, "passed": False, "note": "stooq has no delisted"},
        regime="Range-bound", directive=False,
    )
    assert "Piotroski" in prompt
    assert ("Fama" in prompt or "Lakonishok" in prompt)
    assert "F-Score" in prompt and "8" in prompt          # value diagnostic surfaced
    assert "composite" in prompt.lower()
    assert "Honesty" in prompt                            # honesty block present
    assert "survivorship" in prompt.lower()


def test_neutral_prompt_has_no_directive_language():
    strategy = registry.get("midterm_value_composite")
    prompt = build_advisor_prompt(
        _value_result(), strategy,
        survivorship={"confirmed": True, "passed": False, "note": ""},
        directive=False,
    ).lower()
    for word in _DIRECTIVE_WORDS:
        assert word not in prompt


def test_survivorship_status_path_is_slug_parameterized():
    # A value-slug lookup must read the value artifact path, not the momentum one.
    status = load_survivorship_status(slug="midterm_value_composite")
    assert "confirmed" in status and "passed" in status
