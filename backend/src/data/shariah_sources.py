from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = ROOT / "backend" / "data" / "catalog.db"
DEFAULT_MANIFEST_PATH = ROOT / "backend" / "data" / "manifest.json"


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def normalize_ticker(value: Any) -> str:
    ticker = str(value or "").strip().upper()
    return ticker.replace("/", ".")


def parse_source_as_of(value: Any) -> str:
    if value in (None, ""):
        return utc_now_iso()
    text = str(value).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return (
                parsed.astimezone(timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (
            parsed.astimezone(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except ValueError:
        return utc_now_iso()


def ensure_shariah_table(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        rows = conn.execute("PRAGMA table_info(shariah_sources)").fetchall()
        if rows:
            pk_columns = [
                row[1]
                for row in sorted(
                    (row for row in rows if row[5]), key=lambda row: row[5]
                )
            ]
            if pk_columns != ["ticker", "source_name"]:
                conn.execute("DROP TABLE shariah_sources")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shariah_sources (
                ticker TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_as_of TEXT NOT NULL,
                source_url TEXT NOT NULL,
                PRIMARY KEY (ticker, source_name)
            )
            """)
        conn.commit()


def replace_source_rows(
    source_name: str,
    rows: Iterable[dict[str, Any]],
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
    manifest_metadata: dict[str, Any] | None = None,
) -> int:
    materialized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        ticker = normalize_ticker(row.get("ticker"))
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        materialized.append(
            {
                "ticker": ticker,
                "source_name": source_name,
                "source_kind": row.get("source_kind") or "external",
                "source_as_of": parse_source_as_of(row.get("source_as_of")),
                "source_url": str(row.get("source_url") or ""),
            }
        )

    path = Path(db_path)
    ensure_shariah_table(path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "DELETE FROM shariah_sources WHERE source_name = ?", (source_name,)
        )
        conn.executemany(
            """
            INSERT OR REPLACE INTO shariah_sources
            (ticker, source_name, source_kind, source_as_of, source_url)
            VALUES (:ticker, :source_name, :source_kind, :source_as_of, :source_url)
            """,
            materialized,
        )
        conn.commit()

    update_manifest_source(
        source_name,
        row_count=len(materialized),
        source_as_of=max(
            (row["source_as_of"] for row in materialized), default=utc_now_iso()
        ),
        source_url=materialized[0]["source_url"] if materialized else "",
        manifest_path=manifest_path,
        metadata=manifest_metadata,
    )
    return len(materialized)


def upsert_source_row(
    row: dict[str, Any],
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    ensure_shariah_table(db_path)
    normalized = {
        "ticker": normalize_ticker(row.get("ticker")),
        "source_name": row.get("source_name"),
        "source_kind": row.get("source_kind") or "external",
        "source_as_of": parse_source_as_of(row.get("source_as_of")),
        "source_url": str(row.get("source_url") or ""),
    }
    if not normalized["ticker"] or not normalized["source_name"]:
        return
    with sqlite3.connect(Path(db_path)) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO shariah_sources
            (ticker, source_name, source_kind, source_as_of, source_url)
            VALUES (:ticker, :source_name, :source_kind, :source_as_of, :source_url)
            """,
            normalized,
        )
        conn.commit()


def load_source_rows(
    active_sources: Iterable[str],
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, list[dict[str, Any]]]:
    sources = [source for source in active_sources if source]
    if not sources:
        return {}
    ensure_shariah_table(db_path)
    placeholders = ",".join("?" for _ in sources)
    with sqlite3.connect(Path(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT ticker, source_name, source_kind, source_as_of, source_url
            FROM shariah_sources
            WHERE source_name IN ({placeholders})
            """,
            sources,
        ).fetchall()
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_ticker.setdefault(row["ticker"], []).append(dict(row))
    return by_ticker


def load_manifest(manifest_path: Path | str = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    path = Path(manifest_path)
    if not path.exists():
        return {"sources": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"sources": {}}


def update_manifest_source(
    source_name: str,
    *,
    row_count: int,
    source_as_of: str,
    source_url: str,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
    metadata: dict[str, Any] | None = None,
) -> None:
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(path)
    payload: dict[str, Any] = {
        "kind": "shariah",
        "source_as_of": parse_source_as_of(source_as_of),
        "refresh_interval_days": 7,
        "source_url": source_url,
        "last_row_count": row_count,
    }
    if metadata:
        payload.update(metadata)
    manifest.setdefault("sources", {})[source_name] = payload
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
