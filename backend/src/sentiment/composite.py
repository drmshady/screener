from __future__ import annotations

from datetime import UTC, datetime

from ..models.sentiment import SourceItem

WINDOWS = ((1, 0.15), (7, 0.40), (30, 0.25), (90, 0.20))


def recency_weighted_composite(sources: list[SourceItem], *, now: datetime | None = None) -> float | None:
    now = now or datetime.now(UTC)
    scored = [source for source in sources if source.score is not None]
    if not scored:
        return None
    weighted = 0.0
    total_weight = 0.0
    for days, weight in WINDOWS:
        values = [
            float(source.score)
            for source in scored
            if 0 <= (now - source.published_at).total_seconds() <= days * 86400
        ]
        if not values:
            continue
        weighted += weight * (sum(values) / len(values))
        total_weight += weight
    if total_weight == 0:
        return None
    return round(weighted / total_weight, 6)
