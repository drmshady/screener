"""Feature 018 T035 — CI brief-trigger automation guards.

Mirrors the feature-011 automation tests: the workflow gates the brief-trigger step
on a real publish, but `POST /brief/run` is the defense-in-depth backstop. These
exercise the backend guards a spurious/re-triggered call still hits — idempotency
across a re-triggered session (FR-010) and the non-trading-day skip (FR-011,
SC-008) — so at-most-one, never-misleading delivery holds independent of CI gating.
"""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from backend.src.api import brief as brief_api
from backend.src.api.app import app

CLIENT = TestClient(app, raise_server_exceptions=True)


def _enable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SCREENER_BRIEF_ENABLED", "1")
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SCREENER_BRIEF_RECIPIENT", "owner@example.com")


def test_retriggered_session_sends_at_most_once(monkeypatch, tmp_path) -> None:
    _enable(monkeypatch, tmp_path)
    monkeypatch.setattr(brief_api, "_target_session", lambda: date(2026, 7, 8))  # Wed

    sends: list[int] = []
    monkeypatch.setattr(
        brief_api.brief_email, "send_brief", lambda *a, **k: sends.append(1) or 1
    )

    first = CLIENT.post("/brief/run", json={}).json()
    second = CLIENT.post("/brief/run", json={}).json()

    assert first["status"] == "delivered"
    assert second["status"] == "delivered"
    assert len(sends) == 1  # re-trigger for the same session sent no second email


def test_non_trading_day_is_skipped_never_sent(monkeypatch, tmp_path) -> None:
    _enable(monkeypatch, tmp_path)
    monkeypatch.setattr(brief_api, "_target_session", lambda: date(2026, 7, 4))  # Sat

    sends: list[int] = []
    monkeypatch.setattr(
        brief_api.brief_email, "send_brief", lambda *a, **k: sends.append(1) or 1
    )

    resp = CLIENT.post("/brief/run", json={}).json()
    assert resp["status"] == "skipped"
    assert resp["record"]["status"] == "skipped"
    assert len(sends) == 0  # never a misleading "today" brief on a non-trading day
