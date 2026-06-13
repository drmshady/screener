from __future__ import annotations


def test_endpoint_returns_prompt_response_shape(client, reference_ticker):
    resp = client.get(f"/analyze/{reference_ticker}/advisor-prompt")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("ticker", "strategy", "personal_use_directive", "prompt", "data_as_of", "disclaimer"):
        assert key in body
    assert body["ticker"] == reference_ticker
    assert isinstance(body["personal_use_directive"], bool)
    assert len(body["prompt"]) > 0


def test_endpoint_rejects_unsupported_strategy(client, reference_ticker):
    resp = client.get(
        f"/analyze/{reference_ticker}/advisor-prompt", params={"strategy": "shortterm_atr_breakout"}
    )
    assert resp.status_code == 400


def test_endpoint_404_for_unknown_ticker(client):
    resp = client.get("/analyze/ZZZZNOTATICKER/advisor-prompt")
    assert resp.status_code == 404


def test_prompt_numbers_match_analyze_surface(client, reference_ticker):
    """SC-005: every level in the prompt equals the analyze surface's value."""
    analyze = client.get(f"/analyze/{reference_ticker}").json()
    as_of = analyze["data_as_of"][:10]
    prompt = client.get(
        f"/analyze/{reference_ticker}/advisor-prompt", params={"as_of": as_of}
    ).json()["prompt"]
    # re-fetch analyze pinned to the same as_of so the comparison is apples-to-apples
    analyze = client.get(f"/analyze/{reference_ticker}", params={"as_of": as_of}).json()
    assert analyze["entry"] in prompt
    assert analyze["stop_loss"] in prompt
    assert analyze["take_profit"] in prompt
    assert analyze["current_price"] in prompt


def test_endpoint_is_deterministic(client, reference_ticker):
    """FR-011/SC-004: same ticker + as_of -> byte-identical prompt."""
    analyze = client.get(f"/analyze/{reference_ticker}").json()
    as_of = analyze["data_as_of"][:10]
    p1 = client.get(f"/analyze/{reference_ticker}/advisor-prompt", params={"as_of": as_of}).json()["prompt"]
    p2 = client.get(f"/analyze/{reference_ticker}/advisor-prompt", params={"as_of": as_of}).json()["prompt"]
    assert p1 == p2


def test_personal_use_directive_defaults_off(client, reference_ticker, monkeypatch):
    monkeypatch.delenv("SCREENER_PERSONAL_USE_DIRECTIVE", raising=False)
    body = client.get(f"/analyze/{reference_ticker}/advisor-prompt").json()
    assert body["personal_use_directive"] is False
