"""The value strategy is discoverable via /strategies with full metadata (FR-010)."""
from fastapi.testclient import TestClient

from backend.src.api.app import app

client = TestClient(app)


def test_listing_includes_value_strategy_with_declaration():
    resp = client.get("/strategies")
    assert resp.status_code == 200
    strategies = {s["slug"]: s for s in resp.json()["strategies"]}
    assert "midterm_value_composite" in strategies
    s = strategies["midterm_value_composite"]
    assert s["timeframe"] == "Mid-term"
    assert "Piotroski" in (s["citation"] + " " + " ".join(
        m["citation"] for m in s["modifications"]
    ))
    assert s["holding_period_days"]["min"] and s["holding_period_days"]["max"]
    assert s["regime_favorability"]
    assert s["parameters"]
    # Every modification carries its own citation (FR-002).
    assert all(m["citation"] for m in s["modifications"])


def test_get_single_value_strategy():
    resp = client.get("/strategies/midterm_value_composite")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Mid-Term Value Composite"
    cite = body["citation"].lower()
    assert "fama" in cite or "lakonishok" in cite
