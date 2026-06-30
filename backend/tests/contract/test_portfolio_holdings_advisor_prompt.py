from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.src.api.app import app
from backend.src.portfolio import holding_levels

CLIENT = TestClient(app, raise_server_exceptions=True)
FIXTURES = Path(__file__).resolve().parents[1] / "portfolio" / "fixtures"


@pytest.fixture(autouse=True)
def isolated_portfolio_state(tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    yield


def _rows() -> list[dict]:
    fixture = json.loads((FIXTURES / "transactions_sheet.values.json").read_text())
    headers = fixture["values"][0]
    rows = []
    for i, row_vals in enumerate(fixture["values"][1:], start=2):
        row = dict(zip(headers, row_vals))
        row["source_row"] = i
        rows.append(row)
    return rows


def _snapshot(ticker: str, close: float = 125.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": ticker,
                "name": ticker,
                "sector": "Information Technology",
                "close": close,
                "atr": 5.0,
                "sma_200": 92.0,
                "contraction_low_20": 91.0,
            }
        ]
    )


@pytest.fixture(autouse=True)
def _stub_snapshot(monkeypatch):
    def fake_snapshot(ticker: str, as_of: str | None = None):
        if ticker == "SPUS":
            raise ValueError("No OHLCV data available for SPUS")
        return _snapshot(ticker, 125.0 if as_of is None else 97.0), "2026-06-30T21:00:00Z", []

    monkeypatch.setattr(holding_levels, "build_single_ticker_snapshot", fake_snapshot)


def _import() -> None:
    resp = CLIENT.post("/portfolio/import", json={"rows": _rows()})
    assert resp.status_code == 200


def test_portfolio_prompt_endpoint_returns_prompt() -> None:
    _import()
    resp = CLIENT.post(
        "/portfolio/holdings/advisor-prompt", json={"total_capital": "100000"}
    )
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "strategy",
        "holding_count",
        "personal_use_directive",
        "prompt",
        "data_as_of",
        "disclaimer",
    ):
        assert key in body
    assert isinstance(body["holding_count"], int)
    assert "Holdings (" in body["prompt"]
    assert body["disclaimer"]
    # determinism
    second = CLIENT.post(
        "/portfolio/holdings/advisor-prompt", json={"total_capital": "100000"}
    )
    assert second.json()["prompt"] == body["prompt"]


def test_single_holding_prompt_endpoint_returns_prompt() -> None:
    _import()
    resp = CLIENT.post(
        "/portfolio/holdings/MSFT/advisor-prompt", json={"total_capital": "100000"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "MSFT"
    assert "MSFT" in body["prompt"]
    assert "Held position" in body["prompt"]
    assert body["data_as_of"]
    assert body["disclaimer"]


def test_single_holding_prompt_unknown_ticker_404() -> None:
    _import()
    resp = CLIENT.post(
        "/portfolio/holdings/NOPE/advisor-prompt", json={"total_capital": "100000"}
    )
    assert resp.status_code == 404


def test_prompt_endpoints_reject_unsupported_strategy() -> None:
    _import()
    whole = CLIENT.post(
        "/portfolio/holdings/advisor-prompt",
        json={"total_capital": "100000", "strategy_slug": "midterm_value_composite"},
    )
    assert whole.status_code == 400
    single = CLIENT.post(
        "/portfolio/holdings/MSFT/advisor-prompt",
        json={"total_capital": "100000", "strategy_slug": "midterm_value_composite"},
    )
    assert single.status_code == 400


def test_prompt_directive_flag_reflected(monkeypatch) -> None:
    _import()
    monkeypatch.setenv("SCREENER_PERSONAL_USE_DIRECTIVE", "1")
    resp = CLIENT.post(
        "/portfolio/holdings/advisor-prompt", json={"total_capital": "100000"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["personal_use_directive"] is True
    assert "trim" in body["prompt"].lower() and "exit" in body["prompt"].lower()
