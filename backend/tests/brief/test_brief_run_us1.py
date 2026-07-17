"""Feature 018 T016 (US1) — end-to-end POST /brief/run status section.

dry_run returns the assembled brief with the full portfolio-status section, five
recommendations, `data_as_of` + disclaimer; the empty-portfolio case delivers
explicit empty copy (never a silent failure); a second non-dry call for the same
session is idempotent (FR-010) and sends no second email.
"""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from backend.src.api import brief as brief_api
from backend.src.api.app import app

CLIENT = TestClient(app, raise_server_exceptions=True)


def test_empty_portfolio_dry_run_is_explicit(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SCREENER_BRIEF_ENABLED", "1")
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    resp = CLIENT.post("/brief/run", json={"dry_run": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dry_run"
    brief = body["brief"]
    assert brief["portfolio"]["is_empty"] is True
    assert len(brief["recommendations"]) == 5
    assert body["data_as_of"] and body["disclaimer"]


def test_dry_run_is_deterministic(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SCREENER_BRIEF_ENABLED", "1")
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    first = CLIENT.post("/brief/run", json={"dry_run": True}).json()["brief"]
    second = CLIENT.post("/brief/run", json={"dry_run": True}).json()["brief"]
    first.pop("generated_at", None)
    second.pop("generated_at", None)
    assert first == second


def test_second_call_same_session_is_idempotent(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SCREENER_BRIEF_ENABLED", "1")
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SCREENER_BRIEF_RECIPIENT", "owner@example.com")
    # Fix the target to a known completed US trading day (2026-07-08 is a Wed).
    monkeypatch.setattr(brief_api, "_target_session", lambda: date(2026, 7, 8))

    sends: list[int] = []

    def _fake_send(subject, text_body, html_body, **kwargs) -> int:
        sends.append(1)
        return 1

    monkeypatch.setattr(brief_api.brief_email, "send_brief", _fake_send)

    first = CLIENT.post("/brief/run", json={}).json()
    assert first["status"] == "delivered"
    assert len(sends) == 1

    second = CLIENT.post("/brief/run", json={}).json()
    assert second["status"] == "delivered"
    # No second email: the delivered record short-circuits the send (FR-010).
    assert len(sends) == 1
    assert second["record"]["content_hash"] == first["record"]["content_hash"]
