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


def test_holdings_levels_response_has_both_bases_and_is_deterministic(monkeypatch) -> None:
    def fake_snapshot(ticker: str, as_of: str | None = None):
        if ticker == "SPUS":
            raise ValueError("No OHLCV data available for SPUS")
        return _snapshot(ticker, 125.0 if as_of is None else 97.0), "2026-06-30T21:00:00Z", []

    monkeypatch.setattr(holding_levels, "build_single_ticker_snapshot", fake_snapshot)

    import_response = CLIENT.post("/portfolio/import", json={"rows": _rows()})
    assert import_response.status_code == 200

    first = CLIENT.post("/portfolio/holdings", json={"total_capital": "100000"})
    second = CLIENT.post("/portfolio/holdings", json={"total_capital": "100000"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()

    body = first.json()
    assert body["data_as_of"] == "2026-06-30T21:00:00Z"
    assert body["disclaimer"]

    by_ticker = {holding["ticker"]: holding for holding in body["holdings"]}
    assert by_ticker["SPUS"]["priceable"] is False
    assert by_ticker["SPUS"]["levels"] is None
    assert by_ticker["SPUS"]["risk"] is None
    assert by_ticker["SPUS"]["data_notes"]

    msft = by_ticker["MSFT"]
    assert msft["priceable"] is True
    assert msft["levels"]["original_plan"]["entry"] == "407.60"
    assert msft["levels"]["current_condition"]["entry"] == "407.60"
    assert msft["levels"]["original_plan"]["levels_state"] in {"ok", "insufficient_data"}
    assert msft["unrealized_pl"] is not None
    assert msft["risk"] is not None
    assert msft["risk"]["actual_capital_at_risk"] >= "0.00"
    assert msft["risk"]["per_trade_risk_budget"] == "1000.00"
    assert body["totals"]["total_capital_at_risk"] >= "0.00"
