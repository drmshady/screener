"""T030: Contract tests for POST/DELETE /portfolio/transactions.

Tests written FIRST (TDD): these should FAIL until the routes are implemented.

Covers (per contracts/portfolio-transactions.md):
  1. Validation reuse — an invalid manual row is rejected like an invalid import row.
  2. Aggregation parity — a buy + partial sell aggregate to the same holding as import (SC-010).
  3. Retention — appended transactions persist in the blob and survive a state round-trip.
  4. Delete corrects — deleting re-aggregates; unknown id -> 404.
  5. Envelope — data_as_of + disclaimer on every response.
  6. Secondary import intact — POST /portfolio/import still works (regression).
"""
from __future__ import annotations

from decimal import Decimal
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from backend.src.api.app import app
from backend.src.portfolio.aggregation import aggregate
from backend.src.models.portfolio import Transaction

CLIENT = TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def isolated_portfolio_state(tmp_path, monkeypatch):
    """Each test gets its own SCREENER_DATA_DIR so the portfolio state is isolated."""
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    yield


def _buy(source_row: int = 1) -> dict:
    return {
        "ticker": "AAPL",
        "action": "buy",
        "quantity": "10",
        "price": "180.00",
        "trade_date": "2026-06-01",
        "fees": "1.00",
        "source_row": source_row,
    }


def _sell(source_row: int = 2) -> dict:
    return {
        "ticker": "AAPL",
        "action": "sell",
        "quantity": "4",
        "price": "210.00",
        "trade_date": "2026-06-20",
        "source_row": source_row,
    }


# ---------------------------------------------------------------------------
# Happy path + envelope
# ---------------------------------------------------------------------------

def test_record_transactions_returns_200_with_counts() -> None:
    response = CLIENT.post("/portfolio/transactions", json={"rows": [_buy(), _sell()]})
    assert response.status_code == 200
    body = response.json()
    assert body["accepted_count"] == 2
    assert body["duplicate_count"] == 0
    assert body["rejected"] == []
    assert body["transactions_total"] == 2


def test_response_has_envelope() -> None:
    body = CLIENT.post("/portfolio/transactions", json={"rows": [_buy()]}).json()
    assert body["data_as_of"]
    assert body["disclaimer"]


# ---------------------------------------------------------------------------
# 1. Validation reuse
# ---------------------------------------------------------------------------

def test_invalid_manual_row_rejected_like_import() -> None:
    bad = {**_buy(), "trade_date": "not-a-date"}
    body = CLIENT.post("/portfolio/transactions", json={"rows": [bad]}).json()
    assert body["accepted_count"] == 0
    assert len(body["rejected"]) == 1
    assert "date" in body["rejected"][0]["reason"].lower()


def test_dividend_row_rejected_as_unsupported() -> None:
    div = {**_buy(), "action": "div"}
    body = CLIENT.post("/portfolio/transactions", json={"rows": [div]}).json()
    assert body["accepted_count"] == 0
    assert len(body["rejected"]) == 1


def test_malformed_body_returns_422() -> None:
    assert CLIENT.post("/portfolio/transactions", json={"rows": "nope"}).status_code == 422
    assert CLIENT.post("/portfolio/transactions", json={}).status_code == 422


# ---------------------------------------------------------------------------
# 2. Aggregation parity (SC-010) + 3. retention across state round-trip
# ---------------------------------------------------------------------------

def test_aggregation_parity_with_import() -> None:
    """A buy + partial sell recorded in-app aggregate to the expected holding —
    identical to the shared import/aggregation path."""
    CLIENT.post("/portfolio/transactions", json={"rows": [_buy(), _sell()]})

    # Retained transactions survive the state round-trip.
    state = CLIENT.get("/portfolio/state").json()["state"]
    raw_txns = state["transactions"]
    assert len(raw_txns) == 2

    holdings = aggregate([Transaction.model_validate(t) for t in raw_txns])
    assert len(holdings) == 1
    h = holdings[0]
    assert h.ticker == "AAPL"
    assert h.net_quantity == Decimal("6")  # 10 bought - 4 sold
    assert h.avg_cost == Decimal("180.00")  # sells do not move avg cost
    assert h.cost_basis == Decimal("1080.00")  # 6 * 180
    # realized = (210 - 180) * 4 - 0 fee on the sell = 120.00
    assert h.realized_pl == Decimal("120.00")
    assert h.status == "open"


def test_duplicate_manual_row_deduplicated() -> None:
    CLIENT.post("/portfolio/transactions", json={"rows": [_buy()]})
    body = CLIENT.post("/portfolio/transactions", json={"rows": [_buy()]}).json()
    assert body["accepted_count"] == 0
    assert body["duplicate_count"] == 1
    assert body["transactions_total"] == 1


# ---------------------------------------------------------------------------
# 4. Delete corrects / unknown id -> 404
# ---------------------------------------------------------------------------

def test_delete_transaction_reaggregates() -> None:
    CLIENT.post("/portfolio/transactions", json={"rows": [_buy(), _sell()]})
    state = CLIENT.get("/portfolio/state").json()["state"]
    txn_id = state["transactions"][1]["id"]  # the sell

    response = CLIENT.delete(f"/portfolio/transactions/{quote(txn_id, safe='')}")
    assert response.status_code == 200
    assert response.json()["transactions_total"] == 1

    remaining = CLIENT.get("/portfolio/state").json()["state"]["transactions"]
    assert len(remaining) == 1
    assert remaining[0]["action"] == "buy"


def test_delete_unknown_id_returns_404() -> None:
    CLIENT.post("/portfolio/transactions", json={"rows": [_buy()]})
    response = CLIENT.delete("/portfolio/transactions/does-not-exist")
    assert response.status_code == 404


def test_delete_response_has_envelope() -> None:
    CLIENT.post("/portfolio/transactions", json={"rows": [_buy()]})
    txn_id = CLIENT.get("/portfolio/state").json()["state"]["transactions"][0]["id"]
    body = CLIENT.delete(f"/portfolio/transactions/{quote(txn_id, safe='')}").json()
    assert body["data_as_of"]
    assert body["disclaimer"]


# ---------------------------------------------------------------------------
# 6. Secondary import intact (regression)
# ---------------------------------------------------------------------------

def test_import_endpoint_still_works() -> None:
    rows = [
        {
            "Date": "28/7/2025",
            "Type": "Buy",
            "Stock": "SPUS",
            "Transacted Units": "10",
            "Transacted Price (per unit)": "$30.50",
            "Fees": "$0.00",
            "source_row": 2,
        }
    ]
    response = CLIENT.post("/portfolio/import", json={"rows": rows})
    assert response.status_code == 200
    assert response.json()["accepted_count"] == 1


def test_manual_and_import_share_transaction_store() -> None:
    """Manual entry appends to the same retained list the import writes to."""
    CLIENT.post("/portfolio/transactions", json={"rows": [_buy()]})
    import_rows = [
        {
            "Date": "1/6/2026",
            "Type": "Buy",
            "Stock": "MSFT",
            "Transacted Units": "5",
            "Transacted Price (per unit)": "$400.00",
            "source_row": 9,
        }
    ]
    body = CLIENT.post("/portfolio/import", json={"rows": import_rows}).json()
    assert body["transactions_total"] == 2  # manual AAPL + imported MSFT
