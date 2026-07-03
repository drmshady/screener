"""Feature 016 flag-off byte-identical guarantee (SC-005 / T040).

With ``pipeline_enabled()`` OFF (the default), the cockpit board endpoint 404s and
every existing endpoint stays byte-identical — the synthesis layer is inert until
the owner explicitly opts in. We lock this at two seams: the board 404s regardless
of body, and a representative deterministic existing endpoint (the strategy
listing) produces identical output whether the pipeline flag is OFF or ON.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.src.api.app import app

CLIENT = TestClient(app, raise_server_exceptions=True)

_BOARD_BODY = {
    "tickers": ["NVDA", "MSFT"],
    "total_capital": "100000.00",
    "caps": {"per_position_cap_pct": 0.10, "per_sector_cap_pct": 0.25},
}


def _canonical(payload: dict) -> dict:
    """Drop the per-call wall-clock envelope field so we compare the payload
    substance, not the timestamp."""
    out = dict(payload)
    out.pop("data_as_of", None)
    return out


def test_board_404s_when_flag_off(monkeypatch) -> None:
    monkeypatch.delenv("SCREENER_PIPELINE_ENABLED", raising=False)  # default OFF
    resp = CLIENT.post("/pipeline/board", json=_BOARD_BODY)
    assert resp.status_code == 404


def test_board_404s_even_for_valid_momentum_slug_when_off(monkeypatch) -> None:
    # 404 precedes the momentum-slug 422 check: the feature is simply absent.
    monkeypatch.setenv("SCREENER_PIPELINE_ENABLED", "0")
    body = {**_BOARD_BODY, "strategy_slug": "midterm_52w_high_momentum"}
    assert CLIENT.post("/pipeline/board", json=body).status_code == 404


def test_existing_endpoint_byte_identical_across_flag_toggle(monkeypatch) -> None:
    # The pipeline flag gates ONLY the board; a representative existing endpoint
    # must be byte-identical whether the flag is OFF or ON (no coupling leaked in).
    monkeypatch.setenv("SCREENER_PIPELINE_ENABLED", "0")
    off = CLIENT.get("/strategies", params={"enabled_only": "true"})
    assert off.status_code == 200

    monkeypatch.setenv("SCREENER_PIPELINE_ENABLED", "1")
    on = CLIENT.get("/strategies", params={"enabled_only": "true"})
    assert on.status_code == 200

    assert _canonical(off.json()) == _canonical(on.json())
