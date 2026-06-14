from __future__ import annotations

import pytest

from backend.src.agent.advisor_prompt import build_screen_advisor_prompt
from backend.src.models.strategy import Candidate, GateResult, ScreenResult

FAIL_SURV = {"confirmed": True, "passed": False, "note": "no delisted tickers in the free bundle"}


def _candidate(
    ticker: str, rank: int, *, skipped: bool = False, sector_status: str = "skipped"
) -> Candidate:
    gates = [
        GateResult(gate="52-week-high proximity", status="pass", detail="1.0% below high"),
        GateResult(
            gate="Sector strength",
            status=sector_status,
            detail="leading sector" if sector_status == "pass" else "sector gate not applied",
        ),
        GateResult(
            gate="Low asset growth",
            status="skipped" if skipped else "pass",
            detail="asset-growth data unavailable" if skipped else "in the low group",
        ),
    ]
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
        rank=rank,
        score=round(1.0 / rank, 4),
        return_12_1=0.5 / rank,
        vol_scalar=0.9,
        dist_to_high=0.01 * rank,
        atr=3.0,
        debt_to_equity=0.5,
        fcf_ttm=5.0e8,
        gp_to_assets=0.35,
        asset_growth=0.04,
        reason="matched",
        gate_results=gates,
        recent_8k_count_30d=0,
    )


@pytest.fixture
def sample_screen() -> ScreenResult:
    cands = [_candidate("AAA", 1), _candidate("BBB", 2, skipped=True)]
    return ScreenResult(
        id="screen-1",
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


def test_batch_prompt_covers_all_candidates(sample_screen, midterm_strategy):
    prompt = build_screen_advisor_prompt(sample_screen, midterm_strategy, survivorship=FAIL_SURV)
    assert "Candidates (2)" in prompt
    assert "AAA" in prompt and "BBB" in prompt
    assert "#1" in prompt and "#2" in prompt
    # strategy context + citation once
    assert midterm_strategy.citation in prompt
    assert prompt.count(midterm_strategy.citation) == 1
    # regime once
    assert "Trending up" in prompt and "Favorable" in prompt
    # honesty + survivorship caveat once
    assert "survivorship" in prompt.lower() and "optimistic" in prompt.lower()
    # the skipped gate on BBB is flagged as a data gap
    assert "Data gaps" in prompt
    # ranking inputs are present so the advisor can order the names
    assert "Ranking inputs:" in prompt
    assert "12-1 momentum" in prompt
    assert "return_12_1 × vol_scalar" in prompt  # score formula explained once
    assert "per sector" in prompt  # cap disclosed


def test_batch_prompt_is_deterministic(sample_screen, midterm_strategy):
    a = build_screen_advisor_prompt(sample_screen, midterm_strategy, survivorship=FAIL_SURV)
    b = build_screen_advisor_prompt(sample_screen, midterm_strategy, survivorship=FAIL_SURV)
    assert a == b
    assert "T00:00:00Z" not in a  # no full-ISO wall-clock leaks into the body


def test_batch_prompt_neutral_has_no_directive_language(sample_screen, midterm_strategy):
    prompt = build_screen_advisor_prompt(
        sample_screen, midterm_strategy, survivorship=FAIL_SURV, directive=False
    )
    lower = prompt.lower()
    for word in ("buy", "sell", "recommended", "strong buy"):
        assert word not in lower


def test_batch_endpoint_runs_and_returns_prompt(client):
    resp = client.post(
        "/strategies/midterm_52w_high_momentum/advisor-prompt",
        json={
            "parameters": {"tickers": ["UNH"], "regime_gate": False, "refresh_events": False},
            "filters": {"exclude_earnings_within_days": 0},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    for key in ("strategy", "candidate_count", "personal_use_directive", "prompt", "data_as_of", "disclaimer"):
        assert key in body
    assert isinstance(body["candidate_count"], int)
    assert "Candidates" in body["prompt"]


def test_batch_endpoint_unknown_strategy_404(client):
    resp = client.post("/strategies/not_a_strategy/advisor-prompt", json={})
    assert resp.status_code == 404


def _screen_with(params: dict, cands) -> ScreenResult:
    return ScreenResult(
        id="s",
        strategy_slug="midterm_52w_high_momentum",
        as_of_date="2026-06-12",
        parameters_snapshot=params,
        filters_snapshot={},
        candidate_count=len(cands),
        candidates=cands,
        computed_at="2026-06-12T00:00:00Z",
        data_as_of="2026-06-12T00:00:00Z",
        disclaimer="info only.",
        regime="Trending up",
    )


def test_sector_gate_off_is_config_not_data_gap(midterm_strategy):
    # Default run: sector_strength_top_fraction absent -> gate OFF; sector strength
    # shows SKIPPED but must NOT be flagged as a data gap.
    screen = _screen_with({}, [_candidate("AAA", 1, sector_status="skipped")])
    prompt = build_screen_advisor_prompt(screen, midterm_strategy, survivorship=FAIL_SURV)
    assert "Sector-strength gate: OFF" in prompt
    # the inline data-gaps line, if present, must not include Sector strength
    for line in prompt.splitlines():
        if line.startswith("- Data gaps (skipped"):
            assert "Sector strength" not in line


def test_sector_gate_on_is_disclosed_and_filtered(midterm_strategy):
    screen = _screen_with(
        {"sector_strength_top_fraction": 0.5},
        [_candidate("AAA", 1, sector_status="pass")],
    )
    prompt = build_screen_advisor_prompt(screen, midterm_strategy, survivorship=FAIL_SURV)
    assert "Sector-strength gate: ON" in prompt
    assert "top 50%" in prompt
