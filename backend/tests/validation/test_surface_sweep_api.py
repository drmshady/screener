from __future__ import annotations

from fastapi.testclient import TestClient

from backend.src.api.app import app


def _assert_provenance(payload: dict) -> None:
    assert payload.get("data_as_of")
    assert payload.get("disclaimer")


def test_backend_surface_sweep_api() -> None:
    client = TestClient(app)
    screen = client.post(
        "/strategies/midterm_52w_high_momentum/run",
        json={
            "parameters": {"regime_gate": False, "refresh_events": False},
            "filters": {"shariah_only": True, "exclude_earnings_within_days": 0},
            "shariah_overrides": {
                "active_sources": [
                    "spus_holdings",
                    "spwo_holdings",
                    "spre_holdings",
                    "spte_holdings",
                    "halal_terminal",
                ]
            },
        },
    )
    assert screen.status_code == 200
    screen_payload = screen.json()
    _assert_provenance(screen_payload)
    assert screen_payload["candidate_count"] > 0
    candidate = None
    for row in screen_payload["candidates"]:
        detail_probe = client.get(f"/candidates/{row['ticker']}")
        if detail_probe.status_code == 200:
            candidate = row
            break
    assert candidate is not None

    surfaces = {
        "candidate_detail": client.get(f"/candidates/{candidate['ticker']}"),
        "single_ticker_analysis": client.get(f"/analyze/{candidate['ticker']}"),
        "backtest_view": client.get("/strategies/midterm_52w_high_momentum/backtest"),
        "market_regime": client.get("/regime"),
        "shariah_filter": client.get(f"/shariah/status/{candidate['ticker']}"),
        "events_overlay": client.get(f"/events/ticker/{candidate['ticker']}"),
        "portfolio_sizing": client.post(
            "/sizing",
            json={
                "candidate_ticker": candidate["ticker"],
                "entry": candidate["entry"],
                "candidate_sector": candidate["sector"],
                "total_capital": "10000",
                "holdings": [],
                "caps": {"per_position_cap_pct": 0.10, "per_sector_cap_pct": 0.25},
            },
        ),
    }
    for response in surfaces.values():
        assert response.status_code == 200
        _assert_provenance(response.json())

    detail = surfaces["candidate_detail"].json()
    analyze = surfaces["single_ticker_analysis"].json()
    assert detail["ticker"] == analyze["ticker"] == candidate["ticker"]
    assert detail["sector"] == analyze["sector"] == candidate["sector"]
    assert detail["current_price"] == analyze["current_price"] == candidate["current_price"]

    sizing = surfaces["portfolio_sizing"].json()
    assert sizing["caps_respected"] is True
    assert sizing["suggested_shares"] > 0
    assert "cap" in sizing["reasoning"].lower()


def test_edge_cases_are_explicit() -> None:
    client = TestClient(app)
    zero = client.post(
        "/strategies/midterm_52w_high_momentum/run",
        json={
            "parameters": {
                "regime_gate": False,
                "liquidity_min_price": 1_000_000,
                "refresh_events": False,
            },
            "filters": {"exclude_earnings_within_days": 0},
        },
    )
    assert zero.status_code == 200
    assert zero.json()["candidate_count"] == 0
    assert zero.json()["data_notes"]

    meta = client.get("/meta")
    assert meta.status_code == 200
    assert meta.json()["sources"]

    saudi = client.get("/analyze/2222.SR")
    assert saudi.status_code == 200
    assert any(
        gate["gate"] == "Low asset growth" and gate["status"] == "skipped"
        for gate in saudi.json()["gate_results"]
    )
    assert "Saudi" in " ".join(saudi.json()["data_notes"])

    out_of_universe = client.get("/analyze/AAPL")
    assert out_of_universe.status_code == 200
    assert "compliant US universe" in " ".join(out_of_universe.json()["data_notes"])
