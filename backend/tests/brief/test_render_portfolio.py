"""Feature 018 T015 (US1) — renderer determinism + disclosures.

Same snapshot ⇒ identical rendered text + `content_hash` (SC-005, `generated_at`
excluded); `data_as_of` + `disclaimer` always present (FR-008); active
staleness/integrity warnings surfaced verbatim.
"""
from __future__ import annotations

from decimal import Decimal

from backend.src.brief import render
from backend.src.lib.disclaimer import DISCLAIMER_TEXT
from backend.src.models.brief import (
    AttentionItem,
    AttentionReason,
    BriefModel,
    HoldingLine,
    PortfolioStatusSection,
    RecommendationItem,
    SourceSignal,
    SubjectKind,
)


def _recs() -> list[RecommendationItem]:
    return [
        RecommendationItem(
            rank=i + 1,
            subject="portfolio",
            subject_kind=SubjectKind.PORTFOLIO,
            reason="No actionable signal.",
            source_signal=SourceSignal.PORTFOLIO_ACTION,
            text="No action indicated at this time.",
        )
        for i in range(5)
    ]


def _brief(generated_at: str, *, warnings: list[str] | None = None) -> BriefModel:
    section = PortfolioStatusSection(
        total_value=Decimal("2000"),
        total_pnl=Decimal("200"),
        heat_ceiling_pct=1.0,
        heat_headroom_pct=0.8,
        holdings=[
            HoldingLine(
                ticker="AAA",
                quantity=Decimal("10"),
                avg_cost=Decimal("95"),
                current_price=Decimal("100"),
                unrealized_pnl=Decimal("50"),
                unrealized_pnl_pct=0.05,
                status="owned",
            )
        ],
        attention=[
            AttentionItem(
                ticker="AAA",
                reason_code=AttentionReason.STOP_PROXIMITY,
                detail="within 2% of stop",
                severity=10,
            )
        ],
    )
    return BriefModel(
        target_session="2026-07-08",
        generated_at=generated_at,
        portfolio=section,
        recommendations=_recs(),
        data_as_of="2026-07-08",
        warnings=warnings or [],
    )


def test_render_returns_subject_text_html() -> None:
    subject, text, html = render.render_brief(_brief("2026-07-08T10:00:00Z"))
    assert "2026-07-08" in subject
    assert isinstance(text, str) and isinstance(html, str)
    assert "<" in html and ">" in html


def test_disclaimer_and_data_as_of_always_present() -> None:
    _subject, text, html = render.render_brief(_brief("2026-07-08T10:00:00Z"))
    assert DISCLAIMER_TEXT in text
    assert "2026-07-08" in text
    assert DISCLAIMER_TEXT in html


def test_render_deterministic_excludes_generated_at() -> None:
    a = render.render_brief(_brief("2026-07-08T10:00:00Z"))
    b = render.render_brief(_brief("2026-07-08T23:59:59Z"))
    # generated_at differs but the rendered content must be identical (SC-005).
    assert a == b


def test_warnings_surfaced_verbatim() -> None:
    warning = "SPY 200-day SMA input is unavailable; regime gate fails open."
    _subject, text, _html = render.render_brief(_brief("2026-07-08T10:00:00Z", warnings=[warning]))
    assert warning in text
