"""Contract tests for POST /pipeline/board (Feature 016, T005/T009).

The heavy analyze layer (universe snapshot + EDGAR overlay + external prices) is
stubbed so the test is deterministic; ``size_position`` and ``aggregate_exposure``
run for real (invariant 5), and holdings are derived server-side (never sent in
the request body).
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.src.api import analyze as analyze_mod
from backend.src.api import pipeline as pipeline_mod
from backend.src.api.app import app

CLIENT = TestClient(app, raise_server_exceptions=True)

_BOARD_BODY = {
    "tickers": ["NVDA", "MSFT", "UNKNOWN"],
    "total_capital": "100000.00",
    "available_cash": "25000.00",
    "caps": {"per_position_cap_pct": 0.10, "per_sector_cap_pct": 0.25},
}


def _analysis(ticker: str, *, state: str, reward_distance: float) -> SimpleNamespace:
    return SimpleNamespace(
        ticker=ticker,
        sector="Technology",
        entry="50.00",
        stop_loss="44.00",
        current_price="50.00",
        atr=2.0,
        risk_distance=6.0,
        reward_distance=reward_distance,
        entry_timing=SimpleNamespace(state=state),
    )


def _fake_compute(ticker, strategy="midterm_52w_high_momentum", as_of=None, market_universe=None):
    symbol = ticker.strip().upper()
    if symbol == "NVDA":
        return _analysis(symbol, state="entry_ready", reward_distance=12.0)  # r2r 2.0
    if symbol == "MSFT":
        return _analysis(symbol, state="not_entry_ready", reward_distance=6.0)  # r2r 1.0
    raise HTTPException(status_code=404, detail="Ticker not found in current universe snapshot")


class _FakeRegime:
    regime = "Trending up"

    def model_dump(self, mode=None):
        return {"regime": self.regime, "rule_summary": "SPY above its 200-day SMA"}


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pipeline_mod, "compute_candidate_result", _fake_compute)
    monkeypatch.setattr(analyze_mod, "_market_universe", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(pipeline_mod, "current_regime_response", lambda *a, **k: _FakeRegime())
    yield


def _enable(monkeypatch):
    monkeypatch.setenv("SCREENER_PIPELINE_ENABLED", "1")


def _post():
    return CLIENT.post("/pipeline/board", json=_BOARD_BODY)


def test_404_when_flag_off(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_PIPELINE_ENABLED", "0")
    assert _post().status_code == 404


def test_422_for_non_momentum_slug(monkeypatch) -> None:
    _enable(monkeypatch)
    body = {**_BOARD_BODY, "strategy_slug": "midterm_value_composite"}
    resp = CLIENT.post("/pipeline/board", json=body)
    assert resp.status_code == 422
    assert "momentum" in resp.json()["detail"].lower()


def test_200_shape_and_envelope(monkeypatch) -> None:
    _enable(monkeypatch)
    resp = _post()
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "items",
        "regime",
        "regime_allows_new_entries",
        "heat_ceiling_pct",
        "heat_headroom_pct",
        "available_cash",
        "personal_use_directive",
        "data_as_of",
        "disclaimer",
    ):
        assert key in body
    assert len(body["items"]) == 3
    assert body["disclaimer"]
    assert body["available_cash"] == "25000.00"


def test_fit_ranked_and_facts_wired(monkeypatch) -> None:
    _enable(monkeypatch)
    body = _post().json()
    tickers = [item["ticker"] for item in body["items"]]
    # NVDA (strong) ranks above MSFT (blocked); UNKNOWN (skipped) sinks last.
    assert tickers == ["NVDA", "MSFT", "UNKNOWN"]

    nvda = body["items"][0]
    assert nvda["entry_timing_state"] == "entry_ready"
    assert nvda["fit"]["fit_band"] == "strong_fit"
    assert nvda["fit"]["failed_facts"] == []
    # Facts derive from a real size_position result.
    assert nvda["sizing_preview"]["suggested_shares"] > 0
    assert nvda["sizing_preview"]["binding_constraint"] == "risk_target"
    assert nvda["sizing_preview"]["reward_to_risk"] == 2.0
    assert nvda["fit"]["facts"]["entry_ready"] is True

    msft = body["items"][1]
    assert msft["fit"]["fit_band"] == "blocked"
    assert "entry_ready" in msft["fit"]["failed_facts"]


def test_per_ticker_fail_soft(monkeypatch) -> None:
    _enable(monkeypatch)
    body = _post().json()
    skipped = next(item for item in body["items"] if item["ticker"] == "UNKNOWN")
    assert skipped["skipped_reason"]
    assert skipped["fit"] is None
    assert skipped["sizing_preview"] is None


def _strip_timestamps(items: list[dict]) -> list[dict]:
    """Drop the nested SizingResponse envelope timestamp so determinism compares
    the fit/sizing math, not per-call wall-clock envelope fields."""
    for item in items:
        preview = item.get("sizing_preview")
        if preview:
            preview.pop("data_as_of", None)
    return items


def test_determinism(monkeypatch) -> None:
    _enable(monkeypatch)
    first = _strip_timestamps(_post().json()["items"])
    second = _strip_timestamps(_post().json()["items"])
    assert first == second


def test_directive_absent_when_flag_off(monkeypatch) -> None:
    # Default path (personal-use flag unset): the optional directive field must
    # be omitted entirely, not merely null — leakage-detectable (SC-006).
    _enable(monkeypatch)
    monkeypatch.delenv("SCREENER_PERSONAL_USE_DIRECTIVE", raising=False)
    body = _post().json()
    assert body["personal_use_directive"] is False
    for item in body["items"]:
        if item["fit"] is not None:
            assert "directive_label" not in item["fit"]


def test_directive_present_when_personal_use_on(monkeypatch) -> None:
    _enable(monkeypatch)
    monkeypatch.setenv("SCREENER_PERSONAL_USE_DIRECTIVE", "1")
    body = _post().json()
    assert body["personal_use_directive"] is True
    nvda = body["items"][0]
    assert nvda["fit"]["directive_label"] == "consider_entry"


def test_no_directive_under_hosted_mode(monkeypatch) -> None:
    _enable(monkeypatch)
    # Personal-use flag ON but hosted mode force-OFFs directive framing.
    monkeypatch.setenv("SCREENER_PERSONAL_USE_DIRECTIVE", "1")
    monkeypatch.setenv("SCREENER_HOSTED_MODE", "1")
    monkeypatch.setenv("SCREENER_OWNER_SECRET", "s3cret")
    resp = CLIENT.post(
        "/pipeline/board", json=_BOARD_BODY, headers={"x-owner-secret": "s3cret"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["personal_use_directive"] is False
    for item in body["items"]:
        if item["fit"] is not None:
            assert "directive_label" not in item["fit"]
