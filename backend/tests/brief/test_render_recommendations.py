"""Feature 018 T029 (US3) — recommendation render + directive gating.

Neutral path: no-directive lint on every rendered recommendation line (SC-004).
Directive path: direct wording is allowed AND each directive item carries its
citation(s), with `data_as_of` + the non-advice disclaimer still present (FR-007).
"""
from __future__ import annotations

from decimal import Decimal

from backend.src.brief import recommend, render
from backend.src.lib.disclaimer import DISCLAIMER_TEXT
from backend.src.models.brief import (
    AttentionItem,
    AttentionReason,
    BriefModel,
    HoldingLine,
    PortfolioStatusSection,
)


def _section() -> PortfolioStatusSection:
    return PortfolioStatusSection(
        total_value=Decimal("1000"),
        heat_ceiling_pct=1.0,
        heat_headroom_pct=0.5,
        holdings=[
            HoldingLine(ticker="ATN", quantity=Decimal("10"), avg_cost=Decimal("95"), status="managing")
        ],
        attention=[
            AttentionItem(
                ticker="ATN",
                reason_code=AttentionReason.RISK_BREACH,
                detail="capital at risk exceeds the per-trade budget",
                severity=100,
            )
        ],
        is_empty=False,
    )


def _brief(*, directive: bool, citations: list[str]) -> BriefModel:
    section = _section()
    recs = recommend.select_recommendations(
        section, [], directive=directive, held_tickers=["ATN"], citations=citations
    )
    return BriefModel(
        target_session="2026-07-08",
        portfolio=section,
        recommendations=recs,
        directive=directive,
        data_as_of="2026-07-08",
        citations=citations if any(r.citations for r in recs) else [],
    )


def test_neutral_render_passes_no_directive_lint() -> None:
    # render_brief re-asserts the lint internally; it must not raise.
    _subject, text, _html = render.render_brief(_brief(directive=False, citations=["George & Hwang (2004)"]))
    assert "candidate for review" in text.lower() or "consider reviewing" in text.lower()
    assert DISCLAIMER_TEXT in text


def test_directive_render_includes_citations_and_disclosures() -> None:
    brief = _brief(directive=True, citations=["George & Hwang (2004)"])
    _subject, text, _html = render.render_brief(brief)
    assert "George & Hwang (2004)" in text
    assert DISCLAIMER_TEXT in text
    assert "Data as of 2026-07-08" in text
