from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from backend.src.models.sentiment import (
    BudgetState,
    NarrativeSource,
    SelectionOrigin,
    SentimentLabel,
    SentimentReport,
)
from backend.src.sentiment.store import CapturedReportStore


def _report(ticker: str, fingerprint: str) -> SentimentReport:
    return SentimentReport(
        ticker=ticker,
        origin=SelectionOrigin.SCREENER,
        label=SentimentLabel.POSITIVE,
        label_basis="Lexicon score +1",
        narrative=f"{ticker} recent sourced context.",
        narrative_source=NarrativeSource.TEMPLATE,
        budget_state=BudgetState.OK,
        sources=[],
        fingerprint=fingerprint,
    )


def test_put_populates_ticker_column(tmp_path):
    store = CapturedReportStore(tmp_path / "reports.sqlite")
    store.put(_report("nvda", "sha256:a"))

    with sqlite3.connect(store.path) as conn:
        rows = conn.execute(
            "SELECT ticker FROM sentiment_reports WHERE fingerprint = ?", ("sha256:a",)
        ).fetchall()
    # ticker is normalized to upper-case by the model validator.
    assert rows == [("NVDA",)]


def test_latest_for_ticker_returns_most_recent(tmp_path):
    store = CapturedReportStore(tmp_path / "reports.sqlite")
    store.put(_report("NVDA", "sha256:old"), captured_at=datetime(2026, 7, 1, tzinfo=UTC))
    store.put(_report("NVDA", "sha256:new"), captured_at=datetime(2026, 7, 3, tzinfo=UTC))
    store.put(_report("AMD", "sha256:amd"), captured_at=datetime(2026, 7, 2, tzinfo=UTC))

    latest = store.latest_for_ticker("NVDA")
    assert latest is not None
    assert latest.fingerprint == "sha256:new"
    # case-insensitive match
    assert store.latest_for_ticker("nvda").fingerprint == "sha256:new"


def test_latest_for_ticker_none_when_absent(tmp_path):
    store = CapturedReportStore(tmp_path / "reports.sqlite")
    store.put(_report("NVDA", "sha256:a"))
    assert store.latest_for_ticker("TSLA") is None


def test_migration_adds_ticker_column_and_backfills_legacy_rows(tmp_path):
    path = tmp_path / "reports.sqlite"
    # Simulate a pre-existing (feature-014) schema with NO ticker column.
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE sentiment_reports (
                fingerprint TEXT PRIMARY KEY,
                artifact_json TEXT NOT NULL,
                captured_at TEXT NOT NULL
            )
            """
        )
        legacy = _report("LEGACY", "sha256:legacy")
        conn.execute(
            "INSERT INTO sentiment_reports(fingerprint, artifact_json, captured_at) VALUES (?, ?, ?)",
            (legacy.fingerprint, legacy.model_dump_json(), datetime(2026, 6, 1, tzinfo=UTC).isoformat()),
        )
        conn.commit()

    # Opening the store runs the migration.
    store = CapturedReportStore(path)

    with sqlite3.connect(path) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(sentiment_reports)").fetchall()]
        assert "ticker" in cols
        idx = conn.execute("PRAGMA index_list(sentiment_reports)").fetchall()
        assert any("ticker" in str(row) for row in idx)
        backfilled = conn.execute(
            "SELECT ticker FROM sentiment_reports WHERE fingerprint = ?", ("sha256:legacy",)
        ).fetchone()
    assert backfilled == ("LEGACY",)
    assert store.latest_for_ticker("LEGACY").fingerprint == "sha256:legacy"
    # Sanity: artifact still parses (backfill did not corrupt the row).
    assert json.loads(store.get("sha256:legacy").model_dump_json())["ticker"] == "LEGACY"
