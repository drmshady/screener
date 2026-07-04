from __future__ import annotations

from backend.src.agent.advisor_prompt import _sentiment_section
from backend.src.sentiment.narrative import validate_no_directive_language
from backend.tests.sentiment.conftest import (
    make_no_signal_report,
    make_normal_report,
    make_stale_source_report,
    make_template_only_report,
)

_HEADING = "### External context — sentiment & narrative"


def test_normal_report_renders_label_narrative_risk_and_sources():
    section = _sentiment_section(make_normal_report("NVDA"))
    assert _HEADING in section
    assert "POSITIVE" in section
    # narrative present
    assert "stronger demand" in section
    # narrative-risk reading present
    assert "30" in section and "Contained" in section
    assert "earnings beat" in section
    # dated source with publisher; no bare title without date
    assert "Fixture News" in section
    assert "2026-07-01" in section
    # no wall-clock / captured_at leaks into the body (FR-007)
    assert "captured_at" not in section
    assert "2026-07-02" not in section  # the fixture's captured_at date


def test_no_signal_report_prints_status_and_fabricates_no_narrative():
    report = make_no_signal_report("ZZZZ")
    section = _sentiment_section(report)
    assert _HEADING in section
    lower = section.lower()
    assert "no signal" in lower or "no_signal" in lower
    # the resolution status is surfaced
    assert "no_signal" in lower
    # nothing invented — there is no model/template narrative line
    assert "Narrative (model)" not in section
    assert "Narrative (template)" not in section


def test_template_only_report_reflects_budget_state():
    section = _sentiment_section(make_template_only_report("AMAT"))
    assert _HEADING in section
    lower = section.lower()
    assert "template" in lower
    assert "budget_exhausted" in lower or "budget exhausted" in lower


def test_stale_source_is_marked():
    section = _sentiment_section(make_stale_source_report("ROST"))
    assert "stale" in section.lower()


def test_section_is_deterministic():
    a = _sentiment_section(make_normal_report("NVDA"))
    b = _sentiment_section(make_normal_report("NVDA"))
    assert a == b


def test_every_rendered_report_passes_no_directive_lint():
    for report in (
        make_normal_report("NVDA"),
        make_no_signal_report("ZZZZ"),
        make_template_only_report("AMAT"),
        make_stale_source_report("ROST"),
    ):
        # must not raise DirectiveLanguageError (FR-006)
        validate_no_directive_language(_sentiment_section(report))
