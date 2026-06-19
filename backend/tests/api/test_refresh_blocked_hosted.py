from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.src.api import data


def _hosted_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "1")
    monkeypatch.setenv("SCREENER_OWNER_SECRET", "owner-secret")
    monkeypatch.setenv("SCREENER_FRONTEND_ORIGIN", "https://owner.example")
    from backend.src.api.app import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def test_refresh_blocked_and_no_ingest_in_hosted_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _must_not_run(*args, **kwargs):
        raise AssertionError("heavy ingest must not run in hosted mode")

    monkeypatch.setattr(data, "fetch_incremental_ohlcv", _must_not_run)
    client = _hosted_client(monkeypatch)

    response = client.post(
        "/data/refresh",
        json={"market": "US"},
        headers={"X-Owner-Secret": "owner-secret"},
    )

    assert response.status_code == 409
    detail = response.json()["detail"].lower()
    assert "republish" in detail or "local" in detail


def test_freshness_still_available_in_hosted_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _hosted_client(monkeypatch)

    response = client.get(
        "/data/freshness", headers={"X-Owner-Secret": "owner-secret"}
    )

    assert response.status_code == 200
    assert "sources" in response.json()


def test_refresh_active_in_local_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "0")
    monkeypatch.delenv("SCREENER_OWNER_SECRET", raising=False)
    monkeypatch.setattr(data, "_resolve_tickers", lambda req: ["AAPL"])
    monkeypatch.setattr(
        data, "fetch_incremental_ohlcv", lambda names, history_days=650: pd.DataFrame()
    )
    monkeypatch.setattr(data, "_update_prices_manifest", lambda names: None)
    monkeypatch.setattr(data, "clear_snapshot_caches", lambda: None)
    monkeypatch.setattr(data, "refresh_reference_thresholds", lambda: None)
    monkeypatch.setattr(data, "load_last_dates", lambda names: {})

    from backend.src.api.app import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post("/data/refresh", json={"tickers": ["AAPL"]})

    assert response.status_code == 200
    assert response.json()["refreshed_tickers"] == 1
