from __future__ import annotations

from datetime import UTC, datetime

from ..models.sentiment import NarrativeRisk, SourceClass, SourceItem

REGULATORY_TERMS = {"sec", "investigation", "probe", "regulatory", "lawsuit", "fraud", "restatement"}
NEGATIVE_THEMES = {"cut", "cuts", "downgrade", "weak", "miss", "decline", "fraud", "lawsuit", "investigation"}


def assess_narrative_risk(
    sources: list[SourceItem],
    *,
    now: datetime | None = None,
) -> NarrativeRisk:
    now = now or datetime.now(UTC)
    score = 0
    signals: list[str] = []
    titles = [source.title.lower() for source in sources]
    regulatory_hits = sum(any(term in title for term in REGULATORY_TERMS) for title in titles)
    negative_hits = sum(any(term in title for term in NEGATIVE_THEMES) for title in titles)
    fresh_hits = sum((now - source.published_at).total_seconds() <= 7 * 86400 for source in sources)
    filing_hits = sum(source.source_class == SourceClass.FILING_8K for source in sources)

    if negative_hits >= 2:
        score += 25
        signals.append(f"theme_repetition:{negative_hits}")
    else:
        signals.append("theme_repetition:low")
    if regulatory_hits:
        score += min(35, 15 + regulatory_hits * 10)
        signals.append(f"regulatory_severity:{regulatory_hits}")
    else:
        signals.append("regulatory_severity:none")
    if fresh_hits >= 3:
        score += 15
        signals.append("news_velocity:fresh_cluster")
    if filing_hits:
        score += 10
        signals.append(f"filing_8k:{filing_hits}")

    score = max(0, min(100, score))
    return NarrativeRisk(score=score, label=_label(score), signals=signals)


def _label(score: int) -> str:
    if score <= 20:
        return "Low narrative activity"
    if score <= 40:
        return "Monitor - mild recurring themes"
    if score <= 60:
        return "Elevated - multiple fresh negative themes across sources"
    if score <= 80:
        return "High - themes repeating and escalating across sources"
    return "Very high narrative risk - repeated regulatory/legal themes escalating across sources"
