"""Feature 018 T012 — POST /brief/run contract skeleton (contracts/brief-run.md).

Phase-2 scope: flag-off ⇒ 404; owner-secret dependency enforced in hosted mode;
`BriefRunResponse` shape with `data_as_of` + `disclaimer`. The full
delivered/idempotent/skipped/determinism behaviours are exercised by the US1 tests
(T016) once assemble/render are wired.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.src.api.app import app

CLIENT = TestClient(app, raise_server_exceptions=True)


def test_run_404_when_flag_off(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SCREENER_BRIEF_ENABLED", raising=False)  # default OFF
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    resp = CLIENT.post("/brief/run", json={})
    assert resp.status_code == 404


def test_dry_run_returns_brief_run_response_shape(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SCREENER_BRIEF_ENABLED", "1")
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    resp = CLIENT.post("/brief/run", json={"dry_run": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dry_run"
    assert "target_session" in body
    assert "data_as_of" in body and "disclaimer" in body
    # dry_run returns the assembled brief and writes no record.
    assert body["record"] is None
    assert body["brief"] is not None
    # Exactly five recommendations always (SC-003).
    assert len(body["brief"]["recommendations"]) == 5


def test_owner_secret_enforced_in_hosted_mode(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SCREENER_BRIEF_ENABLED", "1")
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "1")
    monkeypatch.setenv("SCREENER_OWNER_SECRET", "sekret")

    # Missing / wrong owner secret ⇒ 401 (global gate middleware).
    unauth = CLIENT.post("/brief/run", json={"dry_run": True})
    assert unauth.status_code == 401

    # Correct secret ⇒ passes the gate (200 dry_run).
    ok = CLIENT.post(
        "/brief/run", json={"dry_run": True}, headers={"X-Owner-Secret": "sekret"}
    )
    assert ok.status_code == 200
