from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.src.agent.advisor_prompt import _candidate_summary_block
from backend.src.api import strategies as strategies_api
from backend.src.api.app import app
from backend.src.models.strategy import Candidate, GateResult, ScreenResult
from backend.tests.sentiment.conftest import make_normal_report

client = TestClient(app)

_SENTIMENT_HEADING = "### External context — sentiment & narrative"


def _candidate(ticker: str) -> Candidate:
    return Candidate(
        ticker=ticker,
        name=f"{ticker} Inc",
        sector="Technology",
        strategy_slug="midterm_52w_high_momentum",
        current_price="100.00",
        entry="100.00",
        stop_loss="90.00",
        tighter_stop_loss="95.00",
        take_profit="130.00",
        rank=1 if ticker == "NVDA" else 2,
        score=0.5,
        return_12_1=0.4,
        vol_scalar=0.9,
        dist_to_high=0.02,
        atr=3.0,
        reason="matched",
        gate_results=[
            GateResult(gate="52-week-high proximity", status="pass", detail="1% below high"),
        ],
        recent_8k_count_30d=0,
    )


def _screen() -> ScreenResult:
    cands = [_candidate("NVDA"), _candidate("FOO")]
    return ScreenResult(
        id="s1",
        strategy_slug="midterm_52w_high_momentum",
        as_of_date="2026-06-12",
        parameters_snapshot={},
        filters_snapshot={},
        candidate_count=len(cands),
        candidates=cands,
        computed_at="2026-06-12T00:00:00Z",
        data_as_of="2026-06-12T00:00:00Z",
        disclaimer="This product is for informational purposes only and does not constitute financial advice. It does not place trades.",
        regime="Trending up",
    )


@pytest.fixture
def stub_screen(monkeypatch):
    screen = _screen()
    monkeypatch.setattr(strategies_api, "run_strategy", lambda *a, **k: screen)
    return screen


@pytest.fixture
def seeded_store(monkeypatch, tmp_path):
    from backend.src.sentiment.store import CapturedReportStore

    store = CapturedReportStore(tmp_path / "reports.sqlite")
    store.put(make_normal_report("NVDA"))
    monkeypatch.setattr(strategies_api, "CapturedReportStore", lambda: store)
    return store


def test_screen_export_embeds_sentiment_and_leaves_absent_byte_identical(
    stub_screen, seeded_store
):
    resp = client.post("/strategies/midterm_52w_high_momentum/advisor-prompt", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    prompt = body["prompt"]

    # embedded exactly once, in the captured (NVDA) candidate's block
    assert prompt.count(_SENTIMENT_HEADING) == 1
    assert "stronger demand" in prompt

    # the un-captured FOO candidate's block is byte-identical to today's builder output
    foo = stub_screen.candidates[1]
    baseline_block = _candidate_summary_block(
        foo, sector_gate_on=False, material_freshness=None, default_as_of=stub_screen.as_of_date
    )
    assert baseline_block in prompt
    assert _SENTIMENT_HEADING not in baseline_block

    # disclosure envelope preserved (FR-015)
    assert body["data_as_of"] and body["disclaimer"]

    # re-export is byte-identical (FR-007)
    again = client.post("/strategies/midterm_52w_high_momentum/advisor-prompt", json={})
    assert again.json()["prompt"] == prompt


def test_screen_export_failsoft_and_never_generates(monkeypatch, stub_screen, tmp_path):
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
    monkeypatch.setattr(strategies_api, "CapturedReportStore", lambda: store)

    # spy: the export path must NEVER trigger source collection / scoring / generation (FR-009)
    from backend.src.sentiment import narrative as narrative_mod
    from backend.src.sentiment import scorer as scorer_mod
    from backend.src.sentiment import sources as sources_mod

    def _boom(*a, **k):  # pragma: no cover - only fires on regression
        raise AssertionError("export must not generate sentiment")

    monkeypatch.setattr(sources_mod, "collect_sources", _boom)
    monkeypatch.setattr(scorer_mod, "score_texts", _boom)
    monkeypatch.setattr(narrative_mod, "build_template_narrative", _boom)

    resp = client.post("/strategies/midterm_52w_high_momentum/advisor-prompt", json={})
    assert resp.status_code == 200, resp.text
    prompt = resp.json()["prompt"]
    # NVDA's section was dropped by the fail-soft; no section at all embedded
    assert _SENTIMENT_HEADING not in prompt
