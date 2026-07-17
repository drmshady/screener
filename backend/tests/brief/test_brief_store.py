"""Feature 018 T008 — Delivery Run Record store (contracts/email-delivery.md).

`brief_store` persists `brief_runs.json` under `SCREENER_DATA_DIR`, keyed by the
target session (the snapshot `data_as_of`). At most one `delivered` record per
session powers idempotency (FR-010); `load_last_delivered` / `record_run` round-trip
and `content_hash` is preserved for the determinism assertion (SC-005).
"""
from __future__ import annotations

from backend.src.data import brief_store
from backend.src.models.brief import BriefDeliveryRecord, DeliveryStatus


def _record(session: str, status: DeliveryStatus, content_hash: str) -> BriefDeliveryRecord:
    return BriefDeliveryRecord(
        target_session=session,
        status=status,
        recipient="owner@example.com",
        content_hash=content_hash,
        attempts=1,
        directive=False,
    )


def test_record_and_load_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    assert brief_store.load_last_delivered("2026-07-08") is None

    rec = _record("2026-07-08", DeliveryStatus.DELIVERED, "hash-abc")
    brief_store.record_run(rec)

    loaded = brief_store.load_last_delivered("2026-07-08")
    assert loaded is not None
    assert loaded.status is DeliveryStatus.DELIVERED
    assert loaded.content_hash == "hash-abc"
    assert loaded.recipient == "owner@example.com"


def test_only_delivered_records_match_session(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    # A skipped record must NOT satisfy the delivered-idempotency check.
    brief_store.record_run(_record("2026-07-08", DeliveryStatus.SKIPPED, "h1"))
    assert brief_store.load_last_delivered("2026-07-08") is None

    # A failed record likewise does not count as delivered.
    brief_store.record_run(_record("2026-07-08", DeliveryStatus.FAILED, "h2"))
    assert brief_store.load_last_delivered("2026-07-08") is None

    brief_store.record_run(_record("2026-07-08", DeliveryStatus.DELIVERED, "h3"))
    got = brief_store.load_last_delivered("2026-07-08")
    assert got is not None and got.content_hash == "h3"


def test_last_run_is_most_recent_across_sessions(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    assert brief_store.load_last_run() is None

    brief_store.record_run(_record("2026-07-07", DeliveryStatus.DELIVERED, "h-old"))
    brief_store.record_run(_record("2026-07-08", DeliveryStatus.SKIPPED, "h-new"))

    last = brief_store.load_last_run()
    assert last is not None
    assert last.target_session == "2026-07-08"


def test_content_hash_stable_across_reload(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    rec = _record("2026-07-08", DeliveryStatus.DELIVERED, "stable-hash")
    brief_store.record_run(rec)
    first = brief_store.load_last_delivered("2026-07-08")
    second = brief_store.load_last_delivered("2026-07-08")
    assert first is not None and second is not None
    assert first.content_hash == second.content_hash == "stable-hash"
