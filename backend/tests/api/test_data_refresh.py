from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.src.api import data
from backend.src.api.app import app


client = TestClient(app)


def test_post_data_refresh_is_incremental_capped_and_advances_manifest(
    tmp_path: Path, monkeypatch
):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"sources": {}}), encoding="utf-8")
    tickers = [f"T{i:04d}" for i in range(1201)]
    calls: dict[str, object] = {}

    monkeypatch.setattr(data, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(data, "_resolve_tickers", lambda req: tickers)
    def fake_fetch(names, history_days):
        calls["fetch"] = {"count": len(names), "history_days": history_days}
        return pd.DataFrame()

    monkeypatch.setattr(data, "fetch_incremental_ohlcv", fake_fetch)
    monkeypatch.setattr(data, "save_prices", lambda frame: calls.setdefault("saved", True))
    monkeypatch.setattr(data, "clear_snapshot_caches", lambda: calls.setdefault("cleared", True))
    monkeypatch.setattr(
        data,
        "refresh_reference_thresholds",
        lambda: calls.setdefault("thresholds", True),
    )
    monkeypatch.setattr(
        data,
        "load_last_dates",
        lambda names: {name: date(2026, 7, 6) for name in names[:2]},
    )

    response = client.post("/data/refresh", json={"market": "US"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["refreshed_tickers"] == 1200
    assert payload["capped"] is True
    assert payload["latest_bar"] == "2026-07-06"
    assert payload["notices"] == []
    assert calls["fetch"] == {"count": 1200, "history_days": 650}
    assert calls["cleared"] is True
    assert calls["thresholds"] is True
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["sources"]["yfinance"]["last_bar_date_by_ticker"]["T0000"] == "2026-07-06"


def test_post_data_refresh_returns_cached_state_when_source_unreachable(monkeypatch):
    monkeypatch.setattr(data, "_resolve_tickers", lambda req: ["AAPL"])
    monkeypatch.setattr(
        data,
        "fetch_incremental_ohlcv",
        lambda names, history_days: (_ for _ in ()).throw(RuntimeError("network down")),
    )
    monkeypatch.setattr(data, "load_last_dates", lambda names: {"AAPL": date(2026, 7, 2)})
    monkeypatch.setattr(
        data,
        "_update_prices_manifest",
        lambda names: (_ for _ in ()).throw(AssertionError("must not update manifest")),
    )

    response = client.post("/data/refresh", json={"market": "US"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["refreshed_tickers"] == 1
    assert payload["fetched_rows"] == 0
    assert payload["latest_bar"] == "2026-07-02"
    assert payload["notices"]
    assert "cached data remains in use" in payload["notices"][0]
