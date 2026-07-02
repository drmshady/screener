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
