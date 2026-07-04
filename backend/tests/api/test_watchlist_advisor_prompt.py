from __future__ import annotations

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.src.api import portfolio as portfolio_api
from backend.src.api.app import app
from backend.src.models.strategy import AnalyzeResponse, GateResult
from backend.tests.sentiment.conftest import make_normal_report

client = TestClient(app)

_SENTIMENT_HEADING = "### External context — sentiment & narrative"
_ENDPOINT = "/portfolio/watchlist/advisor-prompt"


@pytest.fixture(autouse=True)
def _no_export_generation(monkeypatch):
    """Feature 017 extension: the watchlist export now GENERATES sentiment on
    demand. These reuse-only shape/embedding tests stub generation OFF; the
    generate-once-then-reuse behavior lives in test_export_sentiment_generation.py."""
    monkeypatch.setattr(portfolio_api, "_generate_sentiment", lambda *a, **k: None)
_DISCLAIMER = (
    "This product is for informational purposes only and does not constitute "
    "financial advice. It does not place trades."
)


def _result(ticker: str) -> AnalyzeResponse:
    return AnalyzeResponse(
        ticker=ticker,
        name=f"{ticker} Inc",
        sector="Technology",
        strategy="midterm_52w_high_momentum",
        as_of="2026-06-12",
        would_be_selected=True,
        current_price="100.00",
        entry="100.00",
        stop_loss="90.00",
        tighter_stop_loss="95.00",
        take_profit="130.00",
        return_12_1=0.4,
        vol_scalar=0.9,
        dist_to_high=0.02,
        atr=3.0,
        gate_results=[
            GateResult(gate="52-week-high proximity", status="pass", detail="1% below high"),
        ],
        material_input_freshness={
            "prices": "2026-06-12",
            "fundamentals": "2026-06-12",
            "regime": "2026-06-12",
        },
        data_as_of="2026-06-12T00:00:00Z",
        disclaimer=_DISCLAIMER,
    )


@pytest.fixture
def stub_compute(monkeypatch):
    def fake_compute(ticker, strategy="midterm_52w_high_momentum", as_of=None, market_universe=None):
        symbol = ticker.strip().upper()
        if symbol == "ZZZZ":
            raise HTTPException(status_code=404, detail=f"Not enough data to analyze {symbol}")
        return _result(symbol)

    monkeypatch.setattr(portfolio_api, "compute_candidate_result", fake_compute)
    # Avoid the heavy real universe build in the endpoint's shared-universe path.
    monkeypatch.setattr(portfolio_api, "_market_universe", lambda *a, **k: pd.DataFrame())
    return fake_compute


@pytest.fixture
def seeded_store(monkeypatch, tmp_path):
    from backend.src.sentiment.store import CapturedReportStore

    store = CapturedReportStore(tmp_path / "reports.sqlite")
    store.put(make_normal_report("NVDA"))
    monkeypatch.setattr(portfolio_api, "CapturedReportStore", lambda: store)
    return store


def test_watchlist_export_shape_and_embedding(stub_compute, seeded_store):
    resp = client.post(
        _ENDPOINT,
        json={"strategy_slug": "midterm_52w_high_momentum", "tickers": ["NVDA", "MSFT"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body) >= {
        "strategy",
        "watched_count",
        "personal_use_directive",
        "prompt",
        "data_as_of",
        "disclaimer",
    }
    assert body["strategy"] == "midterm_52w_high_momentum"
    assert body["watched_count"] == 2
    assert body["data_as_of"] and body["disclaimer"]

    prompt = body["prompt"]
    assert prompt.count("## Strategy") == 1
    assert prompt.count("## Honesty & limitations") == 1
    # Sentiment embedded once, only for the captured NVDA name.
    assert prompt.count(_SENTIMENT_HEADING) == 1
    assert "stronger demand" in prompt


def test_unknown_strategy_slug_returns_422(stub_compute):
    resp = client.post(
        _ENDPOINT, json={"strategy_slug": "does_not_exist", "tickers": ["NVDA"]}
    )
    assert resp.status_code == 422, resp.text


def test_empty_tickers_returns_200_with_zero_count(stub_compute):
    resp = client.post(
        _ENDPOINT, json={"strategy_slug": "midterm_52w_high_momentum", "tickers": []}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["watched_count"] == 0
    assert "no watched names" in body["prompt"].lower()


def test_unresolvable_ticker_still_appears(stub_compute, seeded_store):
    resp = client.post(
        _ENDPOINT,
        json={"strategy_slug": "midterm_52w_high_momentum", "tickers": ["NVDA", "ZZZZ"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["watched_count"] == 2
    prompt = body["prompt"]
    assert "### ZZZZ" in prompt
    lower = prompt.lower()
    assert "no coverage" in lower or "not priceable" in lower


def test_reexport_is_byte_identical(stub_compute, seeded_store):
    payload = {"strategy_slug": "midterm_52w_high_momentum", "tickers": ["NVDA", "MSFT"]}
    first = client.post(_ENDPOINT, json=payload).json()["prompt"]
    second = client.post(_ENDPOINT, json=payload).json()["prompt"]
    assert first == second


def test_export_never_triggers_generation(monkeypatch, stub_compute, seeded_store):
    from backend.src.sentiment import narrative as narrative_mod
    from backend.src.sentiment import scorer as scorer_mod
    from backend.src.sentiment import sources as sources_mod

    def _boom(*a, **k):  # pragma: no cover - only fires on regression
        raise AssertionError("watchlist export must not generate sentiment")

    monkeypatch.setattr(sources_mod, "collect_sources", _boom)
    monkeypatch.setattr(scorer_mod, "score_texts", _boom)
    monkeypatch.setattr(narrative_mod, "build_template_narrative", _boom)

    resp = client.post(
        _ENDPOINT,
        json={"strategy_slug": "midterm_52w_high_momentum", "tickers": ["NVDA"]},
    )
    assert resp.status_code == 200, resp.text
