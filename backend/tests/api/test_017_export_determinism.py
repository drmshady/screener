"""T026 / FR-007 / SC-003 / SC-005 — cross-surface determinism + source
traceability for the three sentiment-enriched exports.

On an unchanged snapshot with a fixed captured `SentimentReport`, each of the
three exports (screen, portfolio holdings, watchlist) must re-render
byte-identically (FR-007/SC-003). And every embedded sentiment claim must be
traceable to a listed, dated source (SC-005): the rendered section carries the
captured source's publisher + ISO date and its verbatim title.

Reuses the per-story test helpers so the fixtures stay in one place.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.src.api import portfolio as portfolio_api
from backend.src.api import strategies as strategies_api
from backend.src.api.app import app
from backend.tests.api.test_portfolio_advisor_prompt_sentiment import _holding
from backend.tests.api.test_screen_advisor_prompt_sentiment import _screen
from backend.tests.api.test_watchlist_advisor_prompt import _result as _watch_result
from backend.src.models.portfolio import PortfolioTotals
from backend.tests.sentiment.conftest import make_normal_report

client = TestClient(app)

_SENTIMENT_HEADING = "### External context — sentiment & narrative"
_SOURCE = make_normal_report("NVDA").sources[0]


@pytest.fixture(autouse=True)
def _no_export_generation(monkeypatch):
    """Determinism here is about REUSE of captured reports; stub the feature-017
    on-demand generation OFF so un-captured tickers stay section-free and no live
    provider is hit. Generation determinism (generate-once-then-reuse) is covered
    in test_export_sentiment_generation.py."""
    monkeypatch.setattr(portfolio_api, "_generate_sentiment", lambda *a, **k: None)


@pytest.fixture
def store(monkeypatch, tmp_path):
    from backend.src.sentiment.store import CapturedReportStore

    s = CapturedReportStore(tmp_path / "reports.sqlite")
    s.put(make_normal_report("NVDA"))
    monkeypatch.setattr(strategies_api, "CapturedReportStore", lambda: s)
    monkeypatch.setattr(portfolio_api, "CapturedReportStore", lambda: s)
    return s


def _assert_traceable(section: str) -> None:
    """Every embedded sentiment claim maps to a listed dated source (SC-005)."""
    assert "- Sources (" in section
    publisher = _SOURCE.publisher
    date = _SOURCE.published_at.date().isoformat()
    # A dated source bullet: "  - <publisher>, YYYY-MM-DD — <title>"
    assert re.search(rf"  - {re.escape(publisher)}, {re.escape(date)} — ", section)
    assert _SOURCE.title in section


def _sentiment_section(prompt: str) -> str:
    start = prompt.index(_SENTIMENT_HEADING)
    return prompt[start:]


def test_screen_export_deterministic_and_traceable(monkeypatch, store):
    monkeypatch.setattr(strategies_api, "run_strategy", lambda *a, **k: _screen())
    first = client.post("/strategies/midterm_52w_high_momentum/advisor-prompt", json={})
    second = client.post("/strategies/midterm_52w_high_momentum/advisor-prompt", json={})
    assert first.status_code == 200 and second.status_code == 200
    p1 = first.json()["prompt"]
    assert p1 == second.json()["prompt"]
    _assert_traceable(_sentiment_section(p1))


def test_portfolio_export_deterministic_and_traceable(monkeypatch, store):
    holdings = [_holding("NVDA"), _holding("FOO")]
    totals = PortfolioTotals(
        total_invested="11000.00",
        total_capital_at_risk="1000.00",
        total_capital_at_risk_pct=0.09,
    )
    monkeypatch.setattr(
        portfolio_api,
        "_assemble_holdings",
        lambda body: (holdings, totals, "2026-06-12T00:00:00Z", []),
    )
    payload = {"total_capital": "100000"}
    first = client.post("/portfolio/holdings/advisor-prompt", json=payload)
    second = client.post("/portfolio/holdings/advisor-prompt", json=payload)
    assert first.status_code == 200 and second.status_code == 200
    p1 = first.json()["prompt"]
    assert p1 == second.json()["prompt"]
    _assert_traceable(_sentiment_section(p1))


def test_watchlist_export_deterministic_and_traceable(monkeypatch, store):
    def fake_compute(ticker, strategy="midterm_52w_high_momentum", as_of=None, market_universe=None):
        symbol = ticker.strip().upper()
        if symbol == "ZZZZ":
            raise HTTPException(status_code=404, detail="no data")
        return _watch_result(symbol)

    monkeypatch.setattr(portfolio_api, "compute_candidate_result", fake_compute)
    monkeypatch.setattr(portfolio_api, "_market_universe", lambda *a, **k: pd.DataFrame())
    payload = {"strategy_slug": "midterm_52w_high_momentum", "tickers": ["NVDA", "MSFT"]}
    first = client.post("/portfolio/watchlist/advisor-prompt", json=payload)
    second = client.post("/portfolio/watchlist/advisor-prompt", json=payload)
    assert first.status_code == 200 and second.status_code == 200
    p1 = first.json()["prompt"]
    assert p1 == second.json()["prompt"]
    _assert_traceable(_sentiment_section(p1))
