from __future__ import annotations

from fastapi.testclient import TestClient

from backend.src.api.app import app

client = TestClient(app)

SLUG = "midterm_52w_high_momentum"


def test_run_with_unresolvable_tickers_returns_400_not_500() -> None:
    """BUG-007: a run whose explicit tickers resolve to no OHLCV data must fail
    gracefully (400 with a message), not crash with an uncaught ValueError/500.

    Mirrors the analyze/candidate paths, which already convert that ValueError
    into a clean client error rather than a server crash.
    """
    resp = client.post(
        f"/strategies/{SLUG}/run",
        json={"parameters": {"tickers": ["ZZZZNOPE"]}, "filters": {}},
    )
    assert resp.status_code == 400, resp.text
    assert "data" in resp.json()["detail"].lower()


def test_advisor_prompt_with_unresolvable_tickers_returns_400_not_500() -> None:
    """BUG-007: the screen advisor-prompt export shares the run path and must
    also degrade gracefully on the same unresolvable-tickers condition."""
    resp = client.post(
        f"/strategies/{SLUG}/advisor-prompt",
        json={"parameters": {"tickers": ["ZZZZNOPE"]}, "filters": {}},
    )
    assert resp.status_code == 400, resp.text


def test_empty_result_run_still_succeeds() -> None:
    """A screen that legitimately yields zero candidates returns an explicit
    empty result with the standard envelope, never an error (FR-016)."""
    resp = client.post(
        f"/strategies/{SLUG}/run",
        json={"parameters": {"liquidity_min_price": 1e12}, "filters": {}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidate_count"] == 0
    assert body["candidates"] == []
    assert "disclaimer" in body and "data_as_of" in body
