from __future__ import annotations

from fastapi.testclient import TestClient

from backend.src.api.app import app

client = TestClient(app)

SLUG = "midterm_52w_high_momentum"


def test_screen_empty_result_returns_explicit_empty_state_payload() -> None:
    resp = client.post(
        f"/strategies/{SLUG}/run",
        json={"parameters": {"liquidity_min_price": 1e12}, "filters": {}},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidate_count"] == 0
    assert body["candidates"] == []
    joined_notes = " ".join(body["data_notes"]).lower()
    assert "empty universe" in joined_notes
    assert "liquidity" in joined_notes
    assert body["data_as_of"]
    assert body["disclaimer"]


def test_missing_material_inputs_are_reported_without_aborting_run() -> None:
    resp = client.post(
        f"/strategies/{SLUG}/run",
        json={
            "parameters": {
                "tickers": ["AAPL", "MSFT"],
                "sector_strength_top_fraction": 1.0,
            },
            "filters": {},
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["candidates"], list)
    assert "disclaimer" in body
    notes = " ".join(body["data_notes"]).lower()
    assert (
        "fundamentals" in notes
        or any(
            "missing" in gate["detail"].lower()
            for candidate in body["candidates"]
            for gate in candidate["gate_results"]
        )
    )
