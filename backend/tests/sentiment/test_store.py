from __future__ import annotations

from datetime import UTC, datetime

from backend.src.models.sentiment import (
    BudgetState,
    NarrativeSource,
    SelectionOrigin,
    SentimentLabel,
    SentimentReport,
)
from backend.src.sentiment.store import CapturedReportStore


def _report(fingerprint: str = "sha256:test") -> SentimentReport:
    return SentimentReport(
        ticker="nvda",
        origin=SelectionOrigin.SCREENER,
        label=SentimentLabel.POSITIVE,
        label_basis="Lexicon score +1",
        narrative="Recent sources describe stronger demand.",
        narrative_source=NarrativeSource.TEMPLATE,
        budget_state=BudgetState.OK,
        sources=[],
        fingerprint=fingerprint,
    )


def test_store_serves_byte_identical_artifact(tmp_path):
    store = CapturedReportStore(tmp_path / "reports.sqlite")
    report = _report()
    store.put(report, captured_at=datetime(2026, 7, 2, tzinfo=UTC))

    first = store.get(report.fingerprint)
    second = store.get(report.fingerprint)

    assert first == second == report
    assert first.model_dump_json() == second.model_dump_json()


def test_store_stays_under_cache_path(tmp_path):
    store = CapturedReportStore(tmp_path / "cache" / "reports.sqlite")
    store.put(_report())

    assert (tmp_path / "cache" / "reports.sqlite").exists()
    assert not (tmp_path / "reports.sqlite").exists()
