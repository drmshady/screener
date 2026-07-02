from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.src.models.sentiment import SourceClass, SourceItem
from backend.src.sentiment.narrative import (
    DirectiveLanguageError,
    build_template_narrative,
    validate_no_directive_language,
)


def test_template_narrative_is_pure_and_sourced():
    sources = [
        SourceItem(
            id="a",
            source_class=SourceClass.NEWS,
            title="Revenue outlook improves",
            publisher="Example Wire",
            published_at=datetime(2026, 7, 1, tzinfo=UTC),
        )
    ]

    first = build_template_narrative("NVDA", sources)
    second = build_template_narrative("NVDA", sources)

    assert first == second
    assert "Example Wire" in first
    assert "2026-07-01" in first


def test_no_directive_validation_rejects_model_output():
    with pytest.raises(DirectiveLanguageError):
        validate_no_directive_language("This is a strong buy after the news.")


def test_template_narrative_quotes_directive_headlines_without_crashing():
    # Analyst-heavy names (AMAT/BELFB) surface headlines like "... to Buy". These
    # are attributed third-party quotes, not the app's advice, and must render --
    # not raise DirectiveLanguageError and blank the whole report.
    sources = [
        SourceItem(
            id="a",
            source_class=SourceClass.ANALYST_OPINION,
            title="Roth Capital main to Buy",
            publisher="Roth Capital",
            published_at=datetime(2026, 6, 20, tzinfo=UTC),
        ),
        SourceItem(
            id="b",
            source_class=SourceClass.NEWS,
            title="New Strong Buy Stocks for June",
            publisher="Yahoo",
            published_at=datetime(2026, 6, 19, tzinfo=UTC),
        ),
    ]

    narrative = build_template_narrative("AMAT", sources)

    assert "Roth Capital main to Buy" in narrative
    assert narrative.startswith("AMAT recent sourced context:")
