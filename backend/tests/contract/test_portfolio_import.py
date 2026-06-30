"""T007: Contract tests for POST /portfolio/import.

Tests written FIRST (TDD): these should FAIL until the endpoint is implemented.

Covers (per contracts/portfolio-import.md):
  - 200 on all-accepted
  - 200 on partial success (mix of valid + rejected rows)
  - accepted_count / duplicate_count / rejected / transactions_total in response
  - 422 only on malformed body (rows not a list)
  - Idempotent re-import: second identical POST = all duplicates, portfolio unchanged
  - data_as_of + disclaimer present on every response
  - Owner-only gate is inherited (tested implicitly via test client which bypasses hosted gate)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.src.api.app import app

FIXTURES = Path(__file__).resolve().parents[1] / "portfolio" / "fixtures"

CLIENT = TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def isolated_portfolio_state(tmp_path, monkeypatch):
    """Each test gets its own SCREENER_DATA_DIR so the portfolio state is isolated."""
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    yield


def _valid_rows() -> list[dict]:
    """Three valid canonical rows ready to POST."""
    return [
        {
            "Date": "28/7/2025",
            "Type": "Buy",
            "Stock": "SPUS",
            "Transacted Units": "10",
            "Transacted Price (per unit)": "$30.50",
            "Fees": "$0.00",
            "source_row": 2,
        },
        {
            "Date": "15/8/2025",
            "Type": "Buy",
            "Stock": "MSFT",
            "Transacted Units": "5",
            "Transacted Price (per unit)": "$400.00",
            "Fees": "$1.00",
            "source_row": 3,
        },
        {
            "Date": "20/9/2025",
            "Type": "Buy",
            "Stock": "AMZN",
            "Transacted Units": "8",
            "Transacted Price (per unit)": "$1,025.32",
            "Fees": "$2.50",
            "source_row": 4,
        },
    ]


def _mixed_rows() -> list[dict]:
    """Two valid rows + one row with an unparseable date (will be rejected)."""
    rows = _valid_rows()[:2]
    rows.append({
        "Date": "not-a-date",
        "Type": "Buy",
        "Stock": "TSLA",
        "Transacted Units": "5",
        "Transacted Price (per unit)": "$190.00",
        "Fees": "$0.00",
        "source_row": 5,
    })
    return rows


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_import_all_valid_returns_200() -> None:
    response = CLIENT.post("/portfolio/import", json={"rows": _valid_rows()})
    assert response.status_code == 200


def test_import_accepted_count_matches_valid_rows() -> None:
    rows = _valid_rows()
    response = CLIENT.post("/portfolio/import", json={"rows": rows})
    body = response.json()
    assert body["accepted_count"] == len(rows)
    assert body["duplicate_count"] == 0
    assert body["rejected"] == []
    assert body["transactions_total"] == len(rows)


def test_import_partial_success_returns_200() -> None:
    """Mix of valid + invalid rows → 200 (not 422); partial success is success."""
    response = CLIENT.post("/portfolio/import", json={"rows": _mixed_rows()})
    assert response.status_code == 200


def test_import_partial_success_counts() -> None:
    rows = _mixed_rows()  # 2 valid + 1 bad date
    response = CLIENT.post("/portfolio/import", json={"rows": rows})
    body = response.json()
    assert body["accepted_count"] == 2
    assert body["duplicate_count"] == 0
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["source_row"] == 5
    assert "date" in body["rejected"][0]["reason"].lower()
    assert body["transactions_total"] == 2


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_reimport_same_rows_all_duplicates() -> None:
    """Second identical POST = all duplicates; portfolio unchanged."""
    rows = _valid_rows()
    r1 = CLIENT.post("/portfolio/import", json={"rows": rows})
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["accepted_count"] == 3
    assert b1["duplicate_count"] == 0

    r2 = CLIENT.post("/portfolio/import", json={"rows": rows})
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["accepted_count"] == 0
    assert b2["duplicate_count"] == 3
    assert b2["transactions_total"] == 3  # unchanged after re-import


def test_reimport_portfolio_total_unchanged() -> None:
    """Re-importing does not double-count the portfolio."""
    rows = _valid_rows()
    CLIENT.post("/portfolio/import", json={"rows": rows})
    r2 = CLIENT.post("/portfolio/import", json={"rows": rows})
    assert r2.json()["transactions_total"] == len(rows)


def test_import_subset_then_full_adds_new_only() -> None:
    """First import 2 rows; second import all 3 → only 1 new."""
    rows = _valid_rows()
    r1 = CLIENT.post("/portfolio/import", json={"rows": rows[:2]})
    assert r1.json()["accepted_count"] == 2

    r2 = CLIENT.post("/portfolio/import", json={"rows": rows})
    b2 = r2.json()
    assert b2["accepted_count"] == 1
    assert b2["duplicate_count"] == 2
    assert b2["transactions_total"] == 3


def test_reimport_after_adding_identical_row_adds_only_one_new_occurrence() -> None:
    """A later byte-identical row must not rename and re-add the original transaction."""
    row = _valid_rows()[0]

    r1 = CLIENT.post("/portfolio/import", json={"rows": [row]})
    assert r1.status_code == 200
    assert r1.json()["accepted_count"] == 1

    r2 = CLIENT.post("/portfolio/import", json={"rows": [row, {**row, "source_row": 9}]})
    assert r2.status_code == 200
    body = r2.json()
    assert body["accepted_count"] == 1
    assert body["duplicate_count"] == 1
    assert body["transactions_total"] == 2


# ---------------------------------------------------------------------------
# Malformed body → 422
# ---------------------------------------------------------------------------

def test_missing_rows_field_returns_422() -> None:
    response = CLIENT.post("/portfolio/import", json={"sheet_id": "abc"})
    assert response.status_code == 422


def test_rows_not_a_list_returns_422() -> None:
    response = CLIENT.post("/portfolio/import", json={"rows": "not-a-list"})
    assert response.status_code == 422


def test_empty_body_returns_422() -> None:
    response = CLIENT.post("/portfolio/import", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# data_as_of + disclaimer on every response
# ---------------------------------------------------------------------------

def test_response_has_data_as_of() -> None:
    response = CLIENT.post("/portfolio/import", json={"rows": _valid_rows()})
    body = response.json()
    assert "data_as_of" in body
    assert body["data_as_of"]  # non-empty


def test_response_has_disclaimer() -> None:
    response = CLIENT.post("/portfolio/import", json={"rows": _valid_rows()})
    body = response.json()
    assert "disclaimer" in body
    assert body["disclaimer"]  # non-empty


# ---------------------------------------------------------------------------
# sheet_id + sheet_range stored
# ---------------------------------------------------------------------------

def test_sheet_id_and_range_optional() -> None:
    """Endpoint accepts and does not reject optional sheet metadata."""
    response = CLIENT.post(
        "/portfolio/import",
        json={
            "rows": _valid_rows(),
            "sheet_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789ABCDEF",
            "sheet_range": "Transactions!A1:G",
        },
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Full fixture round-trip
# ---------------------------------------------------------------------------

def test_full_sheet_fixture_import() -> None:
    """Import the real-sheet fixture via the endpoint; 8 accepted + 1 Div rejected."""
    fixture = json.loads((FIXTURES / "transactions_sheet.values.json").read_text())
    values = fixture["values"]
    headers = values[0]
    rows = []
    for i, row_vals in enumerate(values[1:], start=2):
        row = dict(zip(headers, row_vals))
        row["source_row"] = i
        rows.append(row)

    response = CLIENT.post(
        "/portfolio/import",
        json={
            "rows": rows,
            "sheet_id": fixture["sheet_id"],
            "sheet_range": fixture["sheet_range"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted_count"] == 8
    assert len(body["rejected"]) == 1
    assert body["transactions_total"] == 8
