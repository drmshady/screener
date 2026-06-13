"""A halted/suspended name (no recent price bar, frozen close near its old 52w
high) must be excluded from the live screen — e.g. CTLP frozen at its buyout
price. Regression for the per-ticker freshness gate in _compute_snapshot_rows."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from backend.src.screening import engine


def _series(ticker: str, end: date, n: int = 300, price: float = 100.0) -> pd.DataFrame:
    days = pd.bdate_range(end=pd.Timestamp(end), periods=n)
    return pd.DataFrame(
        {
            "ticker": ticker,
            "as_of_date": days,
            "open": price,
            "high": price * 1.01,
            "low": price * 0.99,
            "close": price,
            "volume": 5_000_000,
        }
    )


def test_stale_ticker_excluded_from_snapshot():
    latest = date(2026, 6, 9)
    fresh = _series("FRESH", latest)                       # trades through latest
    halted = _series("HALTED", latest - timedelta(days=30))  # last bar ~30d stale
    prices = pd.concat([fresh, halted], ignore_index=True)
    prices["as_of_date"] = pd.to_datetime(prices["as_of_date"])
    profiles = {
        t: {"name": t, "sector": "Tech", "fcf_ttm": 1e9, "debt_to_equity": 0.5,
            "gp_to_assets": 0.6, "asset_growth": 0.05}
        for t in ("FRESH", "HALTED")
    }
    liquid = {"FRESH", "HALTED"}

    snap = engine._compute_snapshot_rows(prices, liquid, latest, profiles)

    assert "FRESH" in set(snap["ticker"])
    assert "HALTED" not in set(snap["ticker"])
    assert "HALTED" in snap.attrs.get("stale_excluded", [])
