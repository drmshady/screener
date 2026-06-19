from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.src.agent.advisor_prompt import (
    build_screen_advisor_prompt,
    load_survivorship_status,
)
from backend.src.api.app import create_app
from backend.src.lib.disclaimer import DISCLAIMER_TEXT
from backend.src.screening.engine import run_strategy
from backend.src.strategies._registry import registry


SLUG = "midterm_52w_high_momentum"
REQUEST = {
    "parameters": {
        "tickers": ["AAPL", "MSFT", "NVDA"],
        "regime_gate": False,
        "refresh_events": False,
    },
    "filters": {"shariah_only": False, "exclude_earnings_within_days": 0},
    "shariah_overrides": {},
}


def _canonical_screen(payload: dict) -> dict:
    return {
        "strategy_slug": payload["strategy_slug"],
        "as_of_date": payload["as_of_date"],
        "parameters_snapshot": payload["parameters_snapshot"],
        "filters_snapshot": payload["filters_snapshot"],
        "candidate_count": payload["candidate_count"],
        "candidates": [
            {
                "ticker": candidate["ticker"],
                "rank": candidate["rank"],
                "score": candidate["score"],
                "entry": candidate["entry"],
                "stop_loss": candidate["stop_loss"],
                "take_profit": candidate["take_profit"],
                "gate_results": candidate["gate_results"],
                "material_input_freshness": candidate["material_input_freshness"],
            }
            for candidate in payload["candidates"]
        ],
        "data_as_of": payload["data_as_of"],
        "disclaimer": payload["disclaimer"],
        "material_input_freshness": payload["material_input_freshness"],
        "regime": payload["regime"],
        "regime_allows_new_entries": payload["regime_allows_new_entries"],
    }


def test_hosted_screen_and_advisor_prompt_match_local_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SCREENER_HOSTED_MODE", raising=False)
    monkeypatch.delenv("SCREENER_PERSONAL_USE_DIRECTIVE", raising=False)
    local_screen = run_strategy(SLUG, **REQUEST).model_dump(mode="json")
    local_prompt = build_screen_advisor_prompt(
        run_strategy(SLUG, **REQUEST),
        registry.get(SLUG),
        survivorship=load_survivorship_status(slug=SLUG),
        directive=False,
    )

    monkeypatch.setenv("SCREENER_HOSTED_MODE", "1")
    monkeypatch.setenv("SCREENER_OWNER_SECRET", "owner-secret")
    monkeypatch.setenv("SCREENER_FRONTEND_ORIGIN", "https://owner.example")
    hosted = TestClient(create_app())

    hosted_screen_response = hosted.post(
        f"/strategies/{SLUG}/run",
        json=REQUEST,
        headers={"X-Owner-Secret": "owner-secret"},
    )
    assert hosted_screen_response.status_code == 200
    assert json.dumps(_canonical_screen(hosted_screen_response.json()), sort_keys=True) == json.dumps(
        _canonical_screen(local_screen), sort_keys=True
    )

    hosted_prompt_response = hosted.post(
        f"/strategies/{SLUG}/advisor-prompt",
        json=REQUEST,
        headers={"X-Owner-Secret": "owner-secret"},
    )
    assert hosted_prompt_response.status_code == 200
    hosted_prompt = hosted_prompt_response.json()
    assert hosted_prompt["personal_use_directive"] is False
    assert hosted_prompt["prompt"] == local_prompt
    assert hosted_prompt["disclaimer"] == DISCLAIMER_TEXT
