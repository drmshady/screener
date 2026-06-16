"""On-demand independent verification endpoint (feature 008).

Network-free: the single-ticker snapshot builder and the independent-quote
provider are both monkeypatched, so the test exercises verdict assignment and the
response shape without touching the price store or any vendor.
"""
from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from backend.src.api import verify as verify_mod
from backend.src.api.app import app
from backend.src.data.independent_quote import IndependentQuote

client = TestClient(app)


def _fake_snapshot(close: float = 100.0, high: float = 103.0) -> pd.DataFrame:
    # Minimal row the contract + endpoint read; series signals are clean.
    return pd.DataFrame(
        [
            {
                "ticker": "TST",
                "name": "Test",
                "sector": "Industrials",
                "close": close,
                "52w_high": high,
                "return_12_1": 0.10,
                "series_dates_ok": True,
                "series_max_session_move": 0.05,
                "seam_consistent": True,
                "seam_factor": 1.0,
                "corporate_action_in_window": False,
                "series_max_move_explained": True,
                "share_class_consistent": True,
            }
        ]
    )


class _StubProvider:
    def __init__(self, quote: IndependentQuote):
        self._quote = quote

    def quote(self, ticker: str) -> IndependentQuote:
        return self._quote


def _patch(monkeypatch, *, snapshot, quote, key="k"):
    monkeypatch.setattr(
        verify_mod, "build_single_ticker_snapshot",
        lambda symbol, as_of=None: (snapshot, "2026-06-12T21:00:00Z", []),
    )
    monkeypatch.setattr(
        verify_mod, "build_default_independent_provider", lambda: _StubProvider(quote)
    )
    monkeypatch.setenv("SCREENER_INDEPENDENT_QUOTE_API_KEY", key) if key else \
        monkeypatch.delenv("SCREENER_INDEPENDENT_QUOTE_API_KEY", raising=False)


def test_verify_agrees(monkeypatch):
    _patch(
        monkeypatch,
        snapshot=_fake_snapshot(close=100.0),
        quote=IndependentQuote("TST", price=101.0, high_52w=103.0, source="finnhub", available=True),
    )
    r = client.get("/candidate/TST/verify")
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "AGREES"
    assert body["key_configured"] is True
    assert body["independent_source"] == "finnhub"
    assert body["divergence_pct"] < 0.10


def test_verify_diverges_unflagged_when_screener_clean(monkeypatch):
    # Independent price is 40% off but the screener did not flag the (clean) row.
    _patch(
        monkeypatch,
        snapshot=_fake_snapshot(close=100.0),
        quote=IndependentQuote("TST", price=60.0, high_52w=None, source="finnhub", available=True),
    )
    body = client.get("/candidate/TST/verify").json()
    assert body["verdict"] == "DIVERGES_UNFLAGGED"
    assert body["screener_flagged"] is False


def test_verify_unverified_without_key(monkeypatch):
    _patch(
        monkeypatch,
        snapshot=_fake_snapshot(),
        quote=IndependentQuote("TST", price=None, high_52w=None, source="finnhub", available=False, error="no API key configured"),
        key="",
    )
    body = client.get("/candidate/TST/verify").json()
    assert body["verdict"] == "UNVERIFIED"
    assert body["key_configured"] is False
