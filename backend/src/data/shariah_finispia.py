from __future__ import annotations

import csv
import json
import os
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from .shariah_sources import DEFAULT_DB_PATH, DEFAULT_MANIFEST_PATH, replace_source_rows

FINISPIA_SOURCE_NAME = "finispia"

COMPLIANT_VALUES = {
    "compliant",
    "halal",
    "pass",
    "passed",
    "approved",
    "yes",
    "true",
    "1",
}


def _load_export_text(path_or_url: str | None = None) -> tuple[str, str]:
    source = (
        path_or_url
        or os.getenv("FINISPIA_EXPORT_PATH")
        or os.getenv("FINISPIA_EXPORT_URL")
    )
    if not source:
        raise RuntimeError(
            "Set FINISPIA_EXPORT_PATH or FINISPIA_EXPORT_URL to import Finispia rows"
        )
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        response = httpx.get(source, timeout=60, follow_redirects=True)
        response.raise_for_status()
        return response.text, source
    path = Path(source)
    return path.read_text(encoding="utf-8"), path.resolve().as_uri()


def _iter_records(text: str) -> list[dict[str, Any]]:
    stripped = text.lstrip("\ufeff").strip()
    if not stripped:
        return []
    if stripped[0] in "[{":
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            payload = (
                payload.get("results")
                or payload.get("data")
                or payload.get("rows")
                or []
            )
        if not isinstance(payload, list):
            raise ValueError("Finispia JSON export must contain a list of rows")
        return [row for row in payload if isinstance(row, dict)]
    return list(csv.DictReader(StringIO(stripped)))


def _compliant(row: dict[str, Any]) -> bool:
    for key in ("is_compliant", "compliant", "halal", "passed"):
        if key in row:
            value = row[key]
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in COMPLIANT_VALUES
    for key in ("status", "verdict", "result", "shariah_status", "compliance_status"):
        if key in row and str(row[key]).strip().lower() in COMPLIANT_VALUES:
            return True
    return False


def fetch_finispia_export(path_or_url: str | None = None) -> list[dict[str, Any]]:
    text, source_url = _load_export_text(path_or_url)
    rows: list[dict[str, Any]] = []
    for row in _iter_records(text):
        ticker = (
            row.get("ticker")
            or row.get("symbol")
            or row.get("Symbol")
            or row.get("Ticker")
        )
        if ticker and _compliant(row):
            rows.append(
                {
                    "ticker": ticker,
                    "source_name": FINISPIA_SOURCE_NAME,
                    "source_kind": "external",
                    "source_as_of": row.get("source_as_of")
                    or row.get("last_checked_at")
                    or row.get("date"),
                    "source_url": source_url,
                }
            )
    return rows


def seed_finispia_export(
    *,
    path_or_url: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
) -> int:
    rows = fetch_finispia_export(path_or_url)
    return replace_source_rows(
        FINISPIA_SOURCE_NAME,
        rows,
        db_path=db_path,
        manifest_path=manifest_path,
        manifest_metadata={
            "display_name": "Finispia",
            "refresh_interval_days": 7,
            "notes": "Imported from a user-provided Finispia export path or URL. No public stable bulk endpoint is hardcoded.",
        },
    )


if __name__ == "__main__":
    count = seed_finispia_export()
    print(f"Seeded {count} Finispia compliant rows")
