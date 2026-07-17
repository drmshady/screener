"""Delivery Run Record persistence for the daily portfolio brief (feature 018).

Stores `brief_runs.json` under `SCREENER_DATA_DIR` (next to `portfolio_state.json`),
keyed by the target session (the snapshot `data_as_of`). Powers idempotency
(FR-010) and `GET /brief/status` (FR-014).

Idempotency is keyed on the target session — not on durable storage — so
at-most-once delivery holds even if the file is ephemeral across a factory rebuild
(research Decision 2): a rebuild only happens when a *new* session is baked, which
is a different key, so a lost record never causes a duplicate for the same session.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..models.brief import BriefDeliveryRecord, DeliveryStatus

ROOT = Path(__file__).resolve().parents[3]


def _runs_path() -> Path:
    base = os.getenv("SCREENER_DATA_DIR")
    data_dir = Path(base) if base else (ROOT / "backend" / "data")
    return data_dir / "brief_runs.json"


def _load_all() -> list[BriefDeliveryRecord]:
    path = _runs_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    records: list[BriefDeliveryRecord] = []
    for row in raw or []:
        try:
            records.append(BriefDeliveryRecord.model_validate(row))
        except Exception:
            continue
    return records


def record_run(record: BriefDeliveryRecord) -> None:
    """Append a run record; atomic tmp-then-replace write (like portfolio_store)."""
    path = _runs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    records = _load_all()
    records.append(record)
    payload = [r.model_dump(mode="json") for r in records]
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)  # atomic-ish swap


def load_last_delivered(target_session: str) -> BriefDeliveryRecord | None:
    """Return the most-recent DELIVERED record for the session, else None.

    Only `delivered` records satisfy the idempotency short-circuit — a prior
    `skipped`/`failed` run for the same session must not suppress a real send.
    """
    match: BriefDeliveryRecord | None = None
    for rec in _load_all():
        if rec.target_session == target_session and rec.status is DeliveryStatus.DELIVERED:
            match = rec  # last one wins (records are append-ordered)
    return match


def load_last_run() -> BriefDeliveryRecord | None:
    """Return the most-recently recorded run of any status (for GET /brief/status)."""
    records = _load_all()
    return records[-1] if records else None
