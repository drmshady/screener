from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.src.agent.advisor_prompt import _holding_block
from backend.src.api import portfolio as portfolio_api
from backend.src.api.app import app
from backend.src.models.portfolio import (
    HoldingLevels,
    HoldingRisk,
    LevelBlock,
    PortfolioHolding,
    PortfolioTotals,
)
from backend.tests.sentiment.conftest import make_normal_report

client = TestClient(app)

_SENTIMENT_HEADING = "### External context — sentiment & narrative"


@pytest.fixture(autouse=True)
def _no_export_generation(monkeypatch):
    """Feature 017 extension: the portfolio/watchlist exports now GENERATE
    sentiment on demand for names with no captured report. These are the
    reuse-only tests, so stub generation OFF here (absent-report blocks must
    stay byte-identical); the generate-once-then-reuse behavior is covered in
    test_export_sentiment_generation.py."""
    monkeypatch.setattr(portfolio_api, "_generate_sentiment", lambda *a, **k: None)


def _level_block() -> LevelBlock:
    return LevelBlock(
        entry=Decimal("100.00"),
        stop_loss=Decimal("90.00"),
        tighter_stop_loss=Decimal("95.00"),
        take_profit=Decimal("130.00"),
        risk_distance=Decimal("10.00"),
        reward_distance=Decimal("30.00"),
        reward_ceiling_basis="3R",
        bounds_applied=["risk_floor"],
        levels_state="ok",
        rationale="Bounded levels derived from ATR and horizon.",
        distance_to_stop_pct=-0.18,
        distance_to_target_pct=0.18,
        status="holding",
    )


def _holding(ticker: str) -> PortfolioHolding:
    return PortfolioHolding(
        ticker=ticker,
        net_quantity=Decimal("50"),
        avg_cost=Decimal("100.00"),
        cost_basis=Decimal("5000.00"),
        earliest_buy_date="2025-07-28",
        most_recent_buy_date="2025-10-09",
        realized_pl=Decimal("0.00"),
        status="open",
        priceable=True,
        sector="Technology",
        current_price=Decimal("110.00"),
        unrealized_pl=Decimal("500.00"),
        unrealized_pl_pct=0.10,
        data_notes=[],
        data_as_of="2026-06-12T00:00:00Z",
        levels=HoldingLevels(
            original_plan=_level_block(),
            current_condition=_level_block(),
        ),
        risk=HoldingRisk(
            recommended_shares=40,
            recommended_value=Decimal("4400.00"),
            actual_shares=Decimal("50"),
            actual_value=Decimal("5500.00"),
            actual_capital_at_risk=Decimal("500.00"),
            actual_capital_at_risk_pct=0.05,
            per_trade_risk_budget=Decimal("100.00"),
            over_risk=True,
            binding_constraint="per_trade_budget",
            sizing_reasoning="Risk-per-trade target binds before the position cap.",
            fail_open=False,
        ),
    )


@pytest.fixture
def stub_holdings(monkeypatch):
    holdings = [_holding("NVDA"), _holding("FOO")]
    totals = PortfolioTotals(
        total_invested=Decimal("11000.00"),
        total_capital_at_risk=Decimal("1000.00"),
        total_capital_at_risk_pct=0.09,
    )
    monkeypatch.setattr(
        portfolio_api,
        "_assemble_holdings",
        lambda body: (holdings, totals, "2026-06-12T00:00:00Z", []),
    )
    return holdings, totals


@pytest.fixture
def seeded_store(monkeypatch, tmp_path):
    from backend.src.sentiment.store import CapturedReportStore

    store = CapturedReportStore(tmp_path / "reports.sqlite")
    store.put(make_normal_report("NVDA"))
    monkeypatch.setattr(portfolio_api, "CapturedReportStore", lambda: store)
    return store


def test_portfolio_export_embeds_sentiment_and_leaves_absent_byte_identical(
    stub_holdings, seeded_store
):
    resp = client.post(
        "/portfolio/holdings/advisor-prompt", json={"total_capital": "100000"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    prompt = body["prompt"]

    # embedded exactly once, in the captured (NVDA) holding's block
    assert prompt.count(_SENTIMENT_HEADING) == 1
    assert "stronger demand" in prompt

    # the un-captured FOO holding's block is byte-identical to today's builder output
    foo = stub_holdings[0][1]
    baseline_block = _holding_block(foo)
    assert baseline_block in prompt
    assert _SENTIMENT_HEADING not in baseline_block

    # disclosure envelope preserved (FR-015)
    assert body["data_as_of"] and body["disclaimer"]

    # re-export is byte-identical (FR-007)
    again = client.post(
        "/portfolio/holdings/advisor-prompt", json={"total_capital": "100000"}
    )
    assert again.json()["prompt"] == prompt


def test_portfolio_export_failsoft_and_never_generates(
    monkeypatch, stub_holdings, tmp_path
):
    from backend.src.sentiment.store import CapturedReportStore

    store = CapturedReportStore(tmp_path / "reports.sqlite")
    store.put(make_normal_report("NVDA"))

    # NVDA raises on lookup -> that section omitted, export still succeeds (FR-010)
    real_lookup = store.latest_for_ticker

    def flaky_lookup(ticker: str):
        if ticker.upper() == "NVDA":
            raise RuntimeError("boom")
        return real_lookup(ticker)

    monkeypatch.setattr(store, "latest_for_ticker", flaky_lookup)
    monkeypatch.setattr(portfolio_api, "CapturedReportStore", lambda: store)

    # spy: export must NEVER trigger source collection / scoring / generation (FR-009)
    from backend.src.sentiment import narrative as narrative_mod
    from backend.src.sentiment import scorer as scorer_mod
    from backend.src.sentiment import sources as sources_mod

    def _boom(*a, **k):  # pragma: no cover - only fires on regression
        raise AssertionError("export must not generate sentiment")

    monkeypatch.setattr(sources_mod, "collect_sources", _boom)
    monkeypatch.setattr(scorer_mod, "score_texts", _boom)
    monkeypatch.setattr(narrative_mod, "build_template_narrative", _boom)

    resp = client.post(
        "/portfolio/holdings/advisor-prompt", json={"total_capital": "100000"}
    )
    assert resp.status_code == 200, resp.text
    prompt = resp.json()["prompt"]
    # NVDA's section was dropped by the fail-soft; no section at all embedded
    assert _SENTIMENT_HEADING not in prompt
