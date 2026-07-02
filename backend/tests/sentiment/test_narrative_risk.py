from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.src.models.sentiment import SourceClass, SourceItem
from backend.src.sentiment.narrative_risk import assess_narrative_risk


def _source(title: str, *, cls: SourceClass = SourceClass.NEWS, age_days: int = 1) -> SourceItem:
    return SourceItem(
        id=title.lower().replace(" ", "-"),
        source_class=cls,
        title=title,
        published_at=datetime(2026, 7, 2, tzinfo=UTC) - timedelta(days=age_days),
        is_stale=False,
    )


def test_risk_uses_feasible_signals_and_neutral_labels():
    risk = assess_narrative_risk(
        [
            _source("SEC investigation expands after restatement"),
            _source("Lawsuit alleges accounting fraud"),
            _source("Company files 8-K about legal proceeding", cls=SourceClass.FILING_8K),
        ],
        now=datetime(2026, 7, 2, tzinfo=UTC),
    )

    assert risk.score >= 60
    assert "regulatory" in " ".join(risk.signals)
    assert "buy" not in risk.label.lower()
    assert "sell" not in risk.label.lower()


def test_risk_omits_unavailable_social_signals():
    risk = assess_narrative_risk([_source("Routine conference presentation")])

    assert all("bot" not in signal and "source_migration" not in signal for signal in risk.signals)
