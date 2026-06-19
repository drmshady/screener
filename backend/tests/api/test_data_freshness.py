from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from backend.src.api import data
from backend.src.api.app import app


client = TestClient(app)


def _write_manifest(path: Path, sources: dict) -> None:
    path.write_text(json.dumps({"sources": sources}, indent=2), encoding="utf-8")


def test_get_data_freshness_contract_no_mutation_and_missing_source(
    tmp_path: Path, monkeypatch
):
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(
        manifest_path,
        {
            "yfinance": {
                "kind": "prices",
                "refresh_interval_days": 0,
                "is_stale": False,
                "source_as_of": "2026-07-02T21:00:00Z",
                "last_bar_date_by_ticker": {"AAPL": "2026-07-02"},
            }
        },
    )
    monkeypatch.setattr(data, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(
        data,
        "_DEFAULT_REQUIRED_FRESHNESS_SOURCES",
        ("yfinance", "sec_edgar_company_tickers"),
    )
    monkeypatch.setattr(
        data,
        "compute_data_freshness",
        lambda **kwargs: __import__(
            "backend.src.data.freshness", fromlist=["compute_data_freshness"]
        ).compute_data_freshness(
            **kwargs, now=datetime(2026, 7, 5, 12, tzinfo=timezone.utc)
        ),
    )
    before = manifest_path.read_text(encoding="utf-8")

    started = time.perf_counter()
    first = client.get("/data/freshness")
    elapsed = time.perf_counter() - started
    second = client.get("/data/freshness")

    assert first.status_code == 200
    assert elapsed < 3
    payload = first.json()
    assert payload["latest_session"] == "2026-07-02"
    assert payload["data_as_of"]
    assert payload["disclaimer"]
    assert payload["sources"] == second.json()["sources"]
    assert manifest_path.read_text(encoding="utf-8") == before

    by_name = {source["source_name"]: source for source in payload["sources"]}
    assert by_name["yfinance"] == {
        "source_name": "yfinance",
        "kind": "prices",
        "data_as_of": "2026-07-02",
        "latest_session": "2026-07-02",
        "sessions_behind": 0,
        "is_stale": False,
        "last_refresh_outcome": "skipped-current",
    }
    assert by_name["sec_edgar_company_tickers"]["data_as_of"] is None
    assert by_name["sec_edgar_company_tickers"]["is_stale"] is True
    assert payload["any_stale"] is True

