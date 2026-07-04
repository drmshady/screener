"""Feature 017 extension — on-demand sentiment generation in the portfolio +
watchlist exports (generate-once-then-reuse), while the screener export stays
strictly reuse-only.

Owner decision: a generated advisor prompt should embed sentiment even for names
that were never captured before. The portfolio/watchlist exports therefore
GENERATE + capture a report on first export and REUSE it thereafter (so
re-export is deterministic and paid calls stay within the monthly budget). The
screener export never generates (a full screen can be 30-50 names).

Generation is exercised through the module-level `_generate_sentiment`
indirection so tests never hit live providers.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.src.api import portfolio as portfolio_api
from backend.src.api import strategies as strategies_api
from backend.src.api.app import app
from backend.src.models.portfolio import PortfolioTotals
from backend.tests.api.test_portfolio_advisor_prompt_sentiment import _holding
from backend.tests.api.test_screen_advisor_prompt_sentiment import _screen
from backend.tests.api.test_watchlist_advisor_prompt import _result as _watch_result
from backend.tests.sentiment.conftest import make_normal_report

client = TestClient(app)

_SENTIMENT_HEADING = "### External context — sentiment & narrative"


@pytest.fixture
def store(monkeypatch, tmp_path):
    """An EMPTY temp store wired into both API modules — nothing is pre-captured,
    so any embedded sentiment must have been generated on demand."""
    from backend.src.sentiment.store import CapturedReportStore

    s = CapturedReportStore(tmp_path / "reports.sqlite")
    monkeypatch.setattr(portfolio_api, "CapturedReportStore", lambda: s)
    monkeypatch.setattr(strategies_api, "CapturedReportStore", lambda: s)
    return s


@pytest.fixture
def capturing_generator(monkeypatch):
    """Stub `_generate_sentiment` to produce a deterministic report AND persist
    it into the passed store (mirroring real generate-and-capture), counting
    calls so we can prove generate-once-then-reuse."""
    calls: list[str] = []

    def fake_generate(ticker, origin, store, budget):
        calls.append(ticker)
        report = make_normal_report(ticker)
        store.put(report)
        return report

    monkeypatch.setattr(portfolio_api, "_generate_sentiment", fake_generate)
    return calls


@pytest.fixture
def stub_holdings(monkeypatch):
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
    return holdings, totals


@pytest.fixture
def stub_compute(monkeypatch):
    def fake_compute(ticker, strategy="midterm_52w_high_momentum", as_of=None, market_universe=None):
        symbol = ticker.strip().upper()
        if symbol == "ZZZZ":
            raise HTTPException(status_code=404, detail="no data")
        return _watch_result(symbol)

    monkeypatch.setattr(portfolio_api, "compute_candidate_result", fake_compute)
    monkeypatch.setattr(portfolio_api, "_market_universe", lambda *a, **k: pd.DataFrame())
    return fake_compute


# ---------------------------------------------------------------------------
# Portfolio export: generate on demand, then reuse.
# ---------------------------------------------------------------------------


def test_portfolio_export_generates_missing_sentiment_then_reuses(
    stub_holdings, store, capturing_generator
):
    first = client.post("/portfolio/holdings/advisor-prompt", json={"total_capital": "100000"})
    assert first.status_code == 200, first.text
    p1 = first.json()["prompt"]
    # Both holdings had NO captured report -> both generated once.
    assert sorted(capturing_generator) == ["FOO", "NVDA"]
    assert p1.count(_SENTIMENT_HEADING) == 2

    # Second export reuses the now-stored reports: no further generation, and the
    # prompt is byte-identical (deterministic after first capture).
    second = client.post("/portfolio/holdings/advisor-prompt", json={"total_capital": "100000"})
    assert second.status_code == 200
    assert sorted(capturing_generator) == ["FOO", "NVDA"]  # unchanged
    assert second.json()["prompt"] == p1


def test_portfolio_export_failsoft_when_generation_raises(monkeypatch, stub_holdings, store):
    def boom(ticker, origin, store, budget):
        raise RuntimeError("provider down")

    monkeypatch.setattr(portfolio_api, "_generate_sentiment", boom)
    resp = client.post("/portfolio/holdings/advisor-prompt", json={"total_capital": "100000"})
    assert resp.status_code == 200, resp.text
    # Generation failed for every name -> no section embedded, export still works.
    assert _SENTIMENT_HEADING not in resp.json()["prompt"]


def test_portfolio_export_no_generation_when_flag_off(monkeypatch, stub_holdings, store):
    monkeypatch.setattr(portfolio_api, "sentiment_export_generation", lambda: False)

    def boom(*a, **k):  # pragma: no cover - only fires on regression
        raise AssertionError("generation must not run when the flag is OFF")

    monkeypatch.setattr(portfolio_api, "_generate_sentiment", boom)
    resp = client.post("/portfolio/holdings/advisor-prompt", json={"total_capital": "100000"})
    assert resp.status_code == 200, resp.text
    assert _SENTIMENT_HEADING not in resp.json()["prompt"]


# ---------------------------------------------------------------------------
# Watchlist export: generate on demand.
# ---------------------------------------------------------------------------


def test_watchlist_export_generates_missing_sentiment(stub_compute, store, capturing_generator):
    resp = client.post(
        "/portfolio/watchlist/advisor-prompt",
        json={"strategy_slug": "midterm_52w_high_momentum", "tickers": ["NVDA", "MSFT"]},
    )
    assert resp.status_code == 200, resp.text
    prompt = resp.json()["prompt"]
    assert sorted(capturing_generator) == ["MSFT", "NVDA"]
    assert prompt.count(_SENTIMENT_HEADING) == 2


# ---------------------------------------------------------------------------
# Screener export stays reuse-only: never generates, even with an empty store.
# ---------------------------------------------------------------------------


def test_screener_export_never_generates(monkeypatch, store):
    monkeypatch.setattr(strategies_api, "run_strategy", lambda *a, **k: _screen())

    from backend.src.sentiment import narrative as narrative_mod
    from backend.src.sentiment import scorer as scorer_mod
    from backend.src.sentiment import sources as sources_mod

    def boom(*a, **k):  # pragma: no cover - only fires on regression
        raise AssertionError("screener export must never generate sentiment")

    monkeypatch.setattr(sources_mod, "collect_sources", boom)
    monkeypatch.setattr(scorer_mod, "score_texts", boom)
    monkeypatch.setattr(narrative_mod, "build_template_narrative", boom)

    resp = client.post("/strategies/midterm_52w_high_momentum/advisor-prompt", json={})
    assert resp.status_code == 200, resp.text
    # Empty store + reuse-only screener -> no section, and no generation attempted.
    assert _SENTIMENT_HEADING not in resp.json()["prompt"]
