from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.src.models.sentiment import SourceClass, SourceItem
from backend.src.sentiment.composite import recency_weighted_composite


def _source(age_days: int, score: float) -> SourceItem:
    return SourceItem(
        id=f"n-{age_days}",
        source_class=SourceClass.NEWS,
        title="headline",
        published_at=datetime(2026, 7, 2, tzinfo=UTC) - timedelta(days=age_days),
        score=score,
    )


def test_composite_renormalizes_missing_windows():
    now = datetime(2026, 7, 2, tzinfo=UTC)
    value = recency_weighted_composite([_source(2, 0.6), _source(20, -0.2)], now=now)

    assert round(value, 4) == 0.3882


def test_composite_returns_none_without_scores():
    now = datetime(2026, 7, 2, tzinfo=UTC)
    assert recency_weighted_composite([], now=now) is None
