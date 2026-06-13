"""Market regime master switch (Faber 2007 / tasks.md T108a).

The recommendation from the strategy comparison study (T049c) was to run the
mid-term momentum strategy with a regime gate: take NO new entries while SPY is
below its 200-day SMA. This module computes that regime from SPY's own history.

Design choices:
- Deterministic from a data snapshot (same as-of -> same regime).
- Fail-OPEN on unknown: if SPY data can't be loaded or the SMA isn't yet defined,
  the gate does NOT block entries (mirrors the events layer's "don't exclude on
  unknown" rule, FR-029). A missing data feed must not silently halt the screener.
- `spy_prices` can be injected for testing (no network).
"""
from __future__ import annotations

import glob
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from ..data.prices import YFinancePriceProvider
from ..indicators.moving_averages import calculate_sma

_STOOQ_ROOT = Path(__file__).resolve().parents[2] / "data" / "prices" / "stooq"


def _spy_from_stooq() -> pd.DataFrame | None:
    """SPY deep history from the local Stooq archive (no network, deterministic)."""
    matches = glob.glob(str(_STOOQ_ROOT / "**" / "spy.us.txt"), recursive=True)
    if not matches:
        return None
    try:
        df = pd.read_csv(matches[0])
    except Exception:
        return None
    df.columns = [c.strip("<>").lower() for c in df.columns]
    if "date" not in df or "close" not in df:
        return None
    df["as_of_date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
    return df.dropna(subset=["as_of_date"])[["as_of_date", "close"]].assign(ticker="SPY")


def _load_spy(as_of_date: str | None, sma_length: int) -> tuple[pd.DataFrame | None, str]:
    # Prefer current EOD from yfinance; fall back to the local Stooq archive when
    # yfinance is unavailable/rate-limited so the gate still computes a real regime.
    end = (pd.Timestamp(as_of_date).date() if as_of_date else date.today()) + timedelta(days=1)
    start = end - timedelta(days=int(sma_length * 2.2) + 60)
    try:
        df = YFinancePriceProvider().fetch_ohlcv(["SPY"], start_date=start, end_date=end)
        if df is not None and not df.empty:
            return df, "yfinance"
    except Exception:
        pass
    stooq = _spy_from_stooq()
    if stooq is not None and not stooq.empty:
        return stooq, "stooq(local)"
    return None, "none"


def market_regime(
    as_of_date: str | None = None,
    sma_length: int = 200,
    spy_prices: pd.DataFrame | None = None,
) -> dict[str, Any]:
    source = "injected"
    if spy_prices is None:
        spy_prices, source = _load_spy(as_of_date, sma_length)

    if spy_prices is None or spy_prices.empty:
        return {
            "regime": "Unknown",
            "allows_new_entries": True,
            "spy_close": None,
            "spy_sma_200": None,
            "note": "SPY regime data unavailable; regime gate fails open (entries allowed).",
        }

    df = spy_prices.copy()
    df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    if as_of_date:
        df = df[df["as_of_date"] <= pd.Timestamp(as_of_date)]
    df = df.sort_values("as_of_date")
    close = df["close"].astype(float)
    sma = calculate_sma(close, sma_length)
    last_close = float(close.iloc[-1]) if len(close) else None
    last_sma = sma.iloc[-1] if len(sma) else None

    if last_close is None or last_sma is None or pd.isna(last_sma):
        return {
            "regime": "Unknown",
            "allows_new_entries": True,
            "spy_close": last_close,
            "spy_sma_200": None,
            "note": f"Insufficient SPY history for a {sma_length}-day SMA; regime gate fails open.",
        }

    above = last_close > float(last_sma)
    spy_as_of = pd.Timestamp(df["as_of_date"].iloc[-1]).date().isoformat()
    return {
        "regime": "Trending up" if above else "Trending down",
        "allows_new_entries": bool(above),
        "spy_close": last_close,
        "spy_sma_200": float(last_sma),
        "note": (
            f"SPY {last_close:.2f} {'above' if above else 'below'} its {sma_length}-day SMA "
            f"{float(last_sma):.2f} (source: {source}, SPY as-of {spy_as_of}); "
            f"new entries {'allowed' if above else 'blocked (downtrend)'}."
        ),
    }


def strategy_is_regime_sensitive(regime_favorability: dict[str, str]) -> bool:
    """A strategy opts into the master switch by marking downtrends Unfavorable."""
    return regime_favorability.get("Trending down") == "Unfavorable"
