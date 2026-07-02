from __future__ import annotations

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

    def put(self, report: SentimentReport, *, captured_at: datetime | None = None) -> None:
        captured = (captured_at or datetime.now(UTC)).isoformat()
        artifact = report.model_dump_json()
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sentiment_reports(fingerprint, artifact_json, captured_at)
                VALUES (?, ?, ?)
                """,
                (report.fingerprint, artifact, captured),
            )
            conn.commit()

    def _init(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sentiment_reports (
                    fingerprint TEXT PRIMARY KEY,
                    artifact_json TEXT NOT NULL,
                    captured_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
