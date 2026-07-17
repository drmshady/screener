"""Feature 018 T012 — GET /brief/status contract (contracts/brief-run.md).

Status is readable even when the feature is OFF, so the owner can confirm it is
off. Every response carries `data_as_of` + `disclaimer`.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.src.api.app import app

CLIENT = TestClient(app, raise_server_exceptions=True)


def test_status_flag_off_returns_enabled_false(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SCREENER_BRIEF_ENABLED", raising=False)  # default OFF
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    resp = CLIENT.get("/brief/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["last_run"] is None
    assert "data_as_of" in body and "disclaimer" in body


def test_status_flag_on_returns_enabled_true(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SCREENER_BRIEF_ENABLED", "1")
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    resp = CLIENT.get("/brief/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["last_run"] is None  # nothing recorded yet
