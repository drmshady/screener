from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ..models.sentiment import SentimentReport

DEFAULT_STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "cache" / "reports.sqlite"


class CapturedReportStore:
    def __init__(self, path: str | Path = DEFAULT_STORE_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def get(self, fingerprint: str) -> SentimentReport | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT artifact_json FROM sentiment_reports WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        if row is None:
            return None
        return SentimentReport.model_validate_json(row[0])

    def latest_for_ticker(self, ticker: str) -> SentimentReport | None:
        """Return the most-recently captured report for `ticker`, or None.

        Matches the model's upper-case normalization so lookups are
        case-insensitive. Uses the `(ticker, captured_at)` index; never reads
        wall-clock into anything the export renders (feature 017 Decision 1/2)."""
        key = ticker.strip().upper()
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT artifact_json FROM sentiment_reports
                WHERE ticker = ?
                ORDER BY captured_at DESC
                LIMIT 1
                """,
                (key,),
            ).fetchone()
        if row is None:
            return None
        return SentimentReport.model_validate_json(row[0])

    def put(self, report: SentimentReport, *, captured_at: datetime | None = None) -> None:
        captured = (captured_at or datetime.now(UTC)).isoformat()
        artifact = report.model_dump_json()
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sentiment_reports(fingerprint, artifact_json, captured_at, ticker)
                VALUES (?, ?, ?, ?)
                """,
                (report.fingerprint, artifact, captured, report.ticker),
            )
            conn.commit()

    def _init(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sentiment_reports (
                    fingerprint TEXT PRIMARY KEY,
                    artifact_json TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    ticker TEXT
                )
                """
            )
            # Additive migration for pre-existing (feature-014) stores that lack
            # the ticker column: add it, backfill from artifact_json once, then
            # index it. Backward-compatible.
            cols = [row[1] for row in conn.execute("PRAGMA table_info(sentiment_reports)").fetchall()]
            if "ticker" not in cols:
                conn.execute("ALTER TABLE sentiment_reports ADD COLUMN ticker TEXT")
                self._backfill_ticker(conn)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reports_ticker "
                "ON sentiment_reports(ticker, captured_at)"
            )
            conn.commit()

    @staticmethod
    def _backfill_ticker(conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            "SELECT fingerprint, artifact_json FROM sentiment_reports WHERE ticker IS NULL"
        ).fetchall()
        for fingerprint, artifact_json in rows:
            try:
                ticker = str(json.loads(artifact_json).get("ticker", "")).strip().upper()
            except Exception:
                ticker = ""
            if ticker:
                conn.execute(
                    "UPDATE sentiment_reports SET ticker = ? WHERE fingerprint = ?",
                    (ticker, fingerprint),
                )
