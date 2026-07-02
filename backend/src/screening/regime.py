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
# Daily-baked SPY history. The hosted image excludes the raw Stooq archive
# (backend/.dockerignore) and SPY is not in the screening parquet, so without
# this the host has no offline SPY and the regime gate falls to Unknown whenever
# request-time yfinance is unreachable. The daily refresh (scripts/ingest_daily.py)
# rewrites this file every run and the Dockerfile bakes the whole data/regime dir,
# so the host always has a recent SPY series to compute the 200-day SMA from.
_SPY_HISTORY_PARQUET = (
    Path(__file__).resolve().parents[2] / "data" / "regime" / "spy_history.parquet"
)


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


def _spy_from_baked(path: Path | str | None = None) -> pd.DataFrame | None:
    """SPY history from the daily-baked parquet (no network, deterministic)."""
    target = Path(path) if path is not None else _SPY_HISTORY_PARQUET
    if not target.exists():
        return None
    try:
        df = pd.read_parquet(target)
    except Exception:
        return None
    if "as_of_date" not in df or "close" not in df or df.empty:
        return None
    return df[["as_of_date", "close"]].assign(ticker="SPY")


def refresh_spy_history(
    *,
    history_days: int = 900,
    provider: "YFinancePriceProvider | None" = None,
    path: Path | str | None = None,
) -> int:
    """Fetch SPY EOD and persist it to the daily-baked regime parquet.

    Called by the daily refresh (scripts/ingest_daily.py), which runs in CI / locally
    where yfinance is reachable, so the host never has to fetch SPY at request time.
    Fail-soft: an empty/failed fetch leaves any existing file untouched (returns 0)
    rather than clobbering a good series with nothing.
    """
    target = Path(path) if path is not None else _SPY_HISTORY_PARQUET
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=int(history_days))
    prov = provider or YFinancePriceProvider()
    try:
        df = prov.fetch_ohlcv(["SPY"], start_date=start, end_date=end)
    except Exception:
        df = None
    if df is None or df.empty or "as_of_date" not in df or "close" not in df:
        return 0
    out = (
        df[["as_of_date", "close"]]
        .dropna(subset=["as_of_date", "close"])
        .sort_values("as_of_date")
        .reset_index(drop=True)
    )
    if out.empty:
        return 0
    out["as_of_date"] = pd.to_datetime(out["as_of_date"])
    out = out.assign(ticker="SPY")
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(target, index=False)
    return len(out)


def _load_spy(as_of_date: str | None, sma_length: int) -> tuple[pd.DataFrame | None, str]:
    # Prefer the freshest source that can actually compute the requested SMA.
    # A short live frame is worse than a full daily-baked/offline frame because
    # it would turn an otherwise computable regime into a transient Unknown.
    def usable_rows(frame: pd.DataFrame | None) -> int:
        if frame is None or frame.empty or "as_of_date" not in frame or "close" not in frame:
            return 0
        candidate = frame.copy()
        candidate["as_of_date"] = pd.to_datetime(candidate["as_of_date"], errors="coerce")
        if as_of_date:
            candidate = candidate[candidate["as_of_date"] <= pd.Timestamp(as_of_date)]
        return len(candidate.dropna(subset=["as_of_date", "close"]))

    end = (pd.Timestamp(as_of_date).date() if as_of_date else date.today()) + timedelta(days=1)
    start = end - timedelta(days=int(sma_length * 2.2) + 60)
    best: tuple[pd.DataFrame | None, str, int] = (None, "none", 0)
    try:
        df = YFinancePriceProvider().fetch_ohlcv(["SPY"], start_date=start, end_date=end)
        rows = usable_rows(df)
        if rows >= sma_length:
            return df, "yfinance"
        if rows > best[2]:
            best = (df, "yfinance", rows)
    except Exception:
        pass
    baked = _spy_from_baked()
    rows = usable_rows(baked)
    if rows >= sma_length:
        return baked, "baked(daily)"
    if rows > best[2]:
        best = (baked, "baked(daily)", rows)
    stooq = _spy_from_stooq()
    rows = usable_rows(stooq)
    if rows >= sma_length:
        return stooq, "stooq(local)"
    if rows > best[2]:
        best = (stooq, "stooq(local)", rows)
    return best[0], best[1]


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


def benchmark_momentum_12_1(as_of_date: str | None = None) -> float | None:
    """SPY 12-1 month momentum (skip the most recent ~month), or None when SPY
    history is unavailable. Mirrors the per-candidate ``return_12_1`` computation
    so the relative-strength gate compares like-for-like (feature 012 US2). Pure
    given the SPY snapshot → deterministic; fails open (None) for the gate to skip.
    """
    spy, _ = _load_spy(as_of_date, 252)
    if spy is None or spy.empty:
        return None
    df = spy.copy()
    df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    if as_of_date:
        df = df[df["as_of_date"] <= pd.Timestamp(as_of_date)]
    close = df.sort_values("as_of_date")["close"].astype(float)
    if len(close) <= 252 or close.iloc[-253] == 0:
        return None
    try:
        return float(close.iloc[-22] / close.iloc[-253] - 1.0)
    except (IndexError, ZeroDivisionError, ValueError):
        return None


def strategy_is_regime_sensitive(regime_favorability: dict[str, str]) -> bool:
    """A strategy opts into the master switch by marking downtrends Unfavorable."""
    return regime_favorability.get("Trending down") == "Unfavorable"
