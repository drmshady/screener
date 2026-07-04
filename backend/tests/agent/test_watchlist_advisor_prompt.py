from __future__ import annotations

import pytest

from backend.src.agent.advisor_prompt import (
    _candidate_summary_block,
    build_watchlist_advisor_prompt,
    load_survivorship_status,
)
from backend.src.models.strategy import AnalyzeResponse, GateResult
from backend.src.sentiment.narrative import validate_no_directive_language
from backend.src.strategies._registry import registry
from backend.src import strategies as _strategies  # noqa: F401 - registers strategies
from backend.tests.sentiment.conftest import make_normal_report

_SENTIMENT_HEADING = "### External context — sentiment & narrative"
_DISCLAIMER = (
    "This product is for informational purposes only and does not constitute "
    "financial advice. It does not place trades."
)


def _result(ticker: str, *, selected: bool = True) -> AnalyzeResponse:
    return AnalyzeResponse(
        ticker=ticker,
        name=f"{ticker} Inc",
        sector="Technology",
        strategy="midterm_52w_high_momentum",
        as_of="2026-06-12",
        would_be_selected=selected,
        current_price="100.00",
        entry="100.00",
        stop_loss="90.00",
        tighter_stop_loss="95.00",
        take_profit="130.00",
        return_12_1=0.4,
        vol_scalar=0.9,
        dist_to_high=0.02,
        atr=3.0,
        gate_results=[
            GateResult(gate="52-week-high proximity", status="pass", detail="1% below high"),
        ],
        material_input_freshness={
            "prices": "2026-06-12",
            "fundamentals": "2026-06-12",
            "regime": "2026-06-12",
        },
        data_as_of="2026-06-12T00:00:00Z",
        disclaimer=_DISCLAIMER,
    )


def _strategy():
    return registry.get("midterm_52w_high_momentum")


def _build(results, *, unresolved=None, sentiment_by_ticker=None, data_as_of="2026-06-12"):
    return build_watchlist_advisor_prompt(
        _strategy(),
        results,
        survivorship=load_survivorship_status(slug="midterm_52w_high_momentum"),
        directive=False,
        regime="Trending up",
        data_as_of=data_as_of,
        disclaimer=_DISCLAIMER,
        unresolved=unresolved,
        sentiment_by_ticker=sentiment_by_ticker,
    )


def test_watchlist_prompt_declaration_once_and_shared_footer_once():
    prompt = _build([_result("NVDA"), _result("FOO")])
    # Strategy declaration appears exactly once (shared header).
    assert prompt.count("## Strategy") == 1
    # One shared honesty footer.
    assert prompt.count("## Honesty & limitations") == 1
    # Each watched name gets its own computed block.
    assert "### NVDA — NVDA Inc" in prompt
    assert "### FOO — FOO Inc" in prompt


def test_watchlist_prompt_embeds_captured_sentiment_when_present():
    report = make_normal_report("NVDA")
    prompt = _build(
        [_result("NVDA"), _result("FOO")],
        sentiment_by_ticker={"NVDA": report},
    )
    # Embedded exactly once, only for the captured name.
    assert prompt.count(_SENTIMENT_HEADING) == 1
    assert "stronger demand" in prompt

    # The un-captured FOO block is byte-identical to the shared block builder's
    # output (no sentiment added when absent).
    foo_block = _candidate_summary_block(
        _result("FOO"),
        sector_gate_on=False,
        material_freshness=None,
        default_as_of="2026-06-12",
    )
    assert foo_block in prompt
    assert _SENTIMENT_HEADING not in foo_block


def test_watchlist_prompt_empty_yields_no_watched_names_body():
    prompt = _build([], data_as_of="2026-06-12")
    assert "## Strategy" in prompt  # declaration still present
    assert _SENTIMENT_HEADING not in prompt
    lower = prompt.lower()
    assert "no watched names" in lower


def test_watchlist_prompt_unresolvable_name_appears_with_no_coverage_note():
    prompt = _build([_result("NVDA")], unresolved=["ZZZZ"])
    assert "### ZZZZ" in prompt
    lower = prompt.lower()
    assert "no coverage" in lower or "not priceable" in lower


def test_watchlist_prompt_is_deterministic_and_non_directive():
    report = make_normal_report("NVDA")
    a = _build([_result("NVDA"), _result("FOO")], sentiment_by_ticker={"NVDA": report})
    b = _build([_result("NVDA"), _result("FOO")], sentiment_by_ticker={"NVDA": report})
    # No wall-clock in the body → byte-identical re-render (FR-007).
    assert a == b

    # Every app-authored line passes the no-directive lint (FR-006). Skip the
    # indented verbatim source bullets and the captured narrative line (quoted
    # third-party / capture-time material, linted at capture).
    for line in a.splitlines():
        if line.startswith("  - ") or line.startswith("- Narrative ("):
            continue
        validate_no_directive_language(line)
