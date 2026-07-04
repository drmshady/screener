from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.src.models.sentiment import (
    BudgetState,
    NarrativeRisk,
    NarrativeSource,
    SelectionOrigin,
    SentimentLabel,
    SentimentReport,
    SourceClass,
    SourceItem,
)
from backend.src.sentiment.store import CapturedReportStore


def _source(ticker: str, *, is_stale: bool = False) -> SourceItem:
    return SourceItem(
        id=f"fixture:{ticker}:1",
        source_class=SourceClass.NEWS,
        title=f"{ticker} raises guidance after strong demand",
        publisher="Fixture News",
        published_at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        reference_url=f"https://example.test/{ticker}",
        is_stale=is_stale,
    )


def make_normal_report(ticker: str = "NVDA") -> SentimentReport:
    """A fully-populated captured report: positive label, model narrative, a
    narrative-risk reading, and one dated source."""
    return SentimentReport(
        ticker=ticker,
        origin=SelectionOrigin.SCREENER,
        label=SentimentLabel.POSITIVE,
        label_basis="Lexicon score +1.00 from 2 positive and 0 negative term hits.",
        sentiment_composite=0.42,
        narrative_risk=NarrativeRisk(
            score=30, label="Contained", signals=["earnings beat", "raised guidance"]
        ),
        narrative=f"{ticker} recent sourced context describes stronger demand and a raised outlook.",
        narrative_source=NarrativeSource.MODEL,
        budget_state=BudgetState.OK,
        source_classes_present=["news"],
        source_classes_omitted=["filing_8k", "earnings", "analyst_opinion", "social"],
        sources=[_source(ticker)],
        fingerprint=f"sha256:{ticker.lower()}-normal",
    )


def make_no_signal_report(ticker: str = "ZZZZ") -> SentimentReport:
    """A captured report that resolved to no signal (no qualifying sources)."""
    return SentimentReport(
        ticker=ticker,
        origin=SelectionOrigin.MANUAL,
        label=SentimentLabel.NO_SIGNAL,
        label_basis="",
        narrative="",
        narrative_source=NarrativeSource.ABSENT,
        budget_state=BudgetState.UNAVAILABLE,
        source_classes_present=[],
        source_classes_omitted=["news", "filing_8k", "earnings", "analyst_opinion", "social"],
        sources=[],
        fingerprint=f"sha256:{ticker.lower()}-nosignal",
        resolution="no_signal",
    )


def make_template_only_report(ticker: str = "AMAT") -> SentimentReport:
    """A captured report where the paid narrative model was unavailable / budget
    exhausted, so a deterministic template narrative was used."""
    return SentimentReport(
        ticker=ticker,
        origin=SelectionOrigin.SCREENER,
        label=SentimentLabel.MIXED,
        label_basis="Lexicon score +0.10 from mixed term hits.",
        sentiment_composite=0.05,
        narrative=f"{ticker} recent sourced context: Fixture News on 2026-07-01: {ticker} update.",
        narrative_source=NarrativeSource.TEMPLATE,
        budget_state=BudgetState.BUDGET_EXHAUSTED,
        source_classes_present=["news"],
        source_classes_omitted=["filing_8k", "earnings", "analyst_opinion", "social"],
        sources=[_source(ticker)],
        fingerprint=f"sha256:{ticker.lower()}-template",
    )


def make_stale_source_report(ticker: str = "ROST") -> SentimentReport:
    """A captured report whose sources are flagged stale."""
    return SentimentReport(
        ticker=ticker,
        origin=SelectionOrigin.HOLDING,
        label=SentimentLabel.NEGATIVE,
        label_basis="Lexicon score -0.80 from 0 positive and 2 negative term hits.",
        sentiment_composite=-0.80,
        narrative_risk=NarrativeRisk(score=72, label="Elevated", signals=["guidance cut"]),
        narrative=f"{ticker} recent sourced context notes softer guidance; sources are stale.",
        narrative_source=NarrativeSource.TEMPLATE,
        budget_state=BudgetState.OK,
        source_classes_present=["news"],
        source_classes_omitted=["filing_8k", "earnings", "analyst_opinion", "social"],
        sources=[_source(ticker, is_stale=True)],
        fingerprint=f"sha256:{ticker.lower()}-stale",
    )


@pytest.fixture
def seeded_report_store(tmp_path):
    """A temporary `CapturedReportStore` seeded with four captured artifacts
    (normal, no-signal, template-only/budget-exhausted, stale-source) reused
    across store, agent, and API tests."""
    store = CapturedReportStore(tmp_path / "cache" / "reports.sqlite")
    reports = {
        "NVDA": make_normal_report("NVDA"),
        "ZZZZ": make_no_signal_report("ZZZZ"),
        "AMAT": make_template_only_report("AMAT"),
        "ROST": make_stale_source_report("ROST"),
    }
    for offset, report in enumerate(reports.values()):
        store.put(report, captured_at=datetime(2026, 7, 2, 0, offset, tzinfo=UTC))
    return store, reports
