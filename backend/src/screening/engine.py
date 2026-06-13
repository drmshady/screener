from __future__ import annotations

import glob
import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ..data.prices import YFinancePriceProvider, fetch_incremental_ohlcv
from ..data.prices_store import load_prices, save_prices
from ..data.profiles import load_or_fetch_profiles
from ..data.universe import UniverseLoader
from ..data.market_calendar import drop_market_weekends, market_of, trading_days_between
from ..events.service import EventsService, TickerEventsSnapshot
from ..indicators.momentum import calculate_12_1_return
from ..indicators.moving_averages import calculate_sma
from ..indicators.price_action import calculate_chandelier_exit_long
from ..indicators.volatility import calculate_adr_ratio, calculate_atr
from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from ..models.strategy import Candidate, ScreenResult
from .regime import market_regime, strategy_is_regime_sensitive
from ..shariah.lookup import ShariahLookup, normalize_shariah_overrides
from ..strategies._registry import registry

DEFAULT_SCREEN_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "AMZN",
    "META",
    "AVGO",
    "LLY",
    "JPM",
    "COST",
    "XOM",
    "UNH",
    "HD",
    "ORCL",
    "AMD",
    "NFLX",
    "CRM",
    "ADBE",
    "V",
    "MA",
]

_SNAPSHOT_CACHE_TTL_SECONDS = 60
# A liquid name with no bar in this many business days is treated as halted /
# suspended / delisted and excluded from the live screen (stale frozen price).
_MAX_BAR_STALENESS_BDAYS = 5
_DISK_SNAPSHOT_CACHE_TTL_SECONDS = 24 * 60 * 60
_STOOQ_SNAPSHOT_CACHE_VERSION = (
    "v4"  # v2: fresh overlay; v3: warm-profile overlay; v4: per-ticker staleness gate
)
_SNAPSHOT_CACHE: dict[tuple[Any, ...], tuple[datetime, pd.DataFrame, str]] = {}
_STOOQ_SNAPSHOT_CACHE: dict[tuple[Any, ...], tuple[datetime, pd.DataFrame, str]] = {}
_STOOQ_TICKERS_CACHE: list[str] | None = None


def clear_snapshot_caches() -> None:
    """Drop in-memory + on-disk snapshot caches so the next screen rebuilds from
    freshly-ingested prices. Called after a manual data refresh."""
    _SNAPSHOT_CACHE.clear()
    _STOOQ_SNAPSHOT_CACHE.clear()
    try:
        import shutil

        if SNAPSHOT_CACHE_DIR.exists():
            shutil.rmtree(SNAPSHOT_CACHE_DIR)
    except Exception:
        pass


def _stable_id(
    strategy_slug: str,
    as_of_date: str,
    parameters: dict[str, Any],
    filters: dict[str, Any],
) -> str:
    payload = {
        "strategy_slug": strategy_slug,
        "as_of_date": as_of_date,
        "parameters": parameters,
        "filters": filters,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _parse_tickers(parameters: dict[str, Any]) -> list[str]:
    raw = parameters.get("tickers") or os.getenv("SCREENER_DEFAULT_TICKERS")
    if raw is None:
        return DEFAULT_SCREEN_TICKERS
    if isinstance(raw, str):
        tickers = [part.strip().upper() for part in raw.split(",")]
    elif isinstance(raw, list):
        tickers = [str(part).strip().upper() for part in raw]
    else:
        raise ValueError("parameters.tickers must be a comma-separated string or list")
    return sorted({ticker for ticker in tickers if ticker})


def _has_explicit_tickers(parameters: dict[str, Any]) -> bool:
    return (
        parameters.get("tickers") is not None
        or os.getenv("SCREENER_DEFAULT_TICKERS") is not None
    )


def _all_stooq_tickers() -> list[str]:
    """Return the local Stooq ticker universe when the deep archive is present."""
    global _STOOQ_TICKERS_CACHE
    if _STOOQ_TICKERS_CACHE is not None:
        return _STOOQ_TICKERS_CACHE
    if not STOOQ_PARQUET_DIR.exists():
        _STOOQ_TICKERS_CACHE = []
        return _STOOQ_TICKERS_CACHE
    try:
        tickers = pd.read_parquet(STOOQ_PARQUET_DIR, columns=["ticker"])
    except Exception:
        _STOOQ_TICKERS_CACHE = []
        return _STOOQ_TICKERS_CACHE
    _STOOQ_TICKERS_CACHE = sorted(
        tickers["ticker"].astype(str).str.upper().dropna().unique().tolist()
    )
    return _STOOQ_TICKERS_CACHE


def _latest_complete_date(prices: pd.DataFrame, requested_as_of: str | None) -> date:
    prices = prices.dropna(subset=["close", "high", "low"])
    if prices.empty:
        raise ValueError("No complete OHLCV bars were returned by the price provider")
    if requested_as_of:
        requested = pd.Timestamp(requested_as_of).date()
        eligible = prices[pd.to_datetime(prices["as_of_date"]).dt.date <= requested]
        if eligible.empty:
            raise ValueError(
                f"No complete OHLCV bars available on or before {requested_as_of}"
            )
        return pd.to_datetime(eligible["as_of_date"]).dt.date.max()
    return pd.to_datetime(prices["as_of_date"]).dt.date.max()


def _ticker_profiles(tickers: list[str]) -> dict[str, dict[str, Any]]:
    return load_or_fetch_profiles(tickers)


def build_universe_snapshot(
    tickers: list[str],
    as_of_date: str | None = None,
    min_adv_20d: float = 1_000_000,
    min_price: float = 5.0,
) -> tuple[pd.DataFrame, str]:
    cache_key = (
        tuple(sorted(tickers)),
        as_of_date,
        float(min_adv_20d),
        float(min_price),
    )
    cached = _SNAPSHOT_CACHE.get(cache_key)
    if (
        cached
        and (datetime.now(timezone.utc) - cached[0]).total_seconds()
        <= _SNAPSHOT_CACHE_TTL_SECONDS
    ):
        return cached[1].copy(deep=True), cached[2]

    end_date = (
        pd.Timestamp(as_of_date).date() + timedelta(days=1)
        if as_of_date
        else date.today() + timedelta(days=1)
    )
    start_date = end_date - timedelta(days=650)
    prices = load_prices(tickers, start_date=start_date, end_date=end_date)
    if as_of_date is None:
        fetched = fetch_incremental_ohlcv(tickers, history_days=650)
        if not fetched.empty:
            save_prices(fetched)
            prices = load_prices(tickers, start_date=start_date, end_date=end_date)
    else:
        available = set(prices["ticker"].unique()) if not prices.empty else set()
        missing = [ticker for ticker in tickers if ticker not in available]
        if missing:
            fetched = YFinancePriceProvider().fetch_ohlcv(
                missing, start_date=start_date, end_date=end_date
            )
            if not fetched.empty:
                save_prices(fetched)
                prices = load_prices(tickers, start_date=start_date, end_date=end_date)
    if prices.empty:
        raise ValueError("No OHLCV data available from local Parquet store or yfinance")

    prices["as_of_date"] = pd.to_datetime(prices["as_of_date"])
    prices = drop_market_weekends(prices)  # market-aware: drop stray weekend bars
    latest_date = _latest_complete_date(prices, as_of_date)
    latest_iso = f"{latest_date.isoformat()}T21:00:00Z"

    liquid = set(
        UniverseLoader(prices).get_liquid_universe(
            latest_date.isoformat(),
            min_adv_20d=min_adv_20d,
            min_price=min_price,
        )
    )

    profiles = _ticker_profiles(sorted(liquid))
    snapshot = _compute_snapshot_rows(prices, liquid, latest_date, profiles)
    _SNAPSHOT_CACHE[cache_key] = (
        datetime.now(timezone.utc),
        snapshot.copy(deep=True),
        latest_iso,
    )
    return snapshot, latest_iso


def build_single_ticker_snapshot(
    ticker: str, as_of: str | None = None
) -> tuple[pd.DataFrame, str, list[str]]:
    """Build the strategy row for one user-supplied symbol.

    This intentionally bypasses the universe-wide liquidity and Shariah gates:
    analysis is an on-demand diagnostic for any ticker. Row-level staleness is
    still checked and reported, but the row is returned so the user can see why
    the data is not a clean screen candidate.
    """
    symbol = ticker.strip().upper()
    if not symbol:
        raise ValueError("Ticker is required")

    end_date = (
        pd.Timestamp(as_of).date() + timedelta(days=1)
        if as_of
        else date.today() + timedelta(days=1)
    )
    start_date = end_date - timedelta(days=650)
    prices = load_prices([symbol], start_date=start_date, end_date=end_date)
    if as_of is None:
        fetched = fetch_incremental_ohlcv([symbol], history_days=650)
        if not fetched.empty:
            save_prices(fetched)
            prices = load_prices([symbol], start_date=start_date, end_date=end_date)
    elif prices.empty:
        fetched = YFinancePriceProvider().fetch_ohlcv(
            [symbol], start_date=start_date, end_date=end_date
        )
        if not fetched.empty:
            save_prices(fetched)
            prices = load_prices([symbol], start_date=start_date, end_date=end_date)
    if prices.empty:
        # Fall back to the local Stooq deep archive (covers US names yfinance is
        # flaky for, e.g. LNTH) so analysis works for any priced symbol.
        stooq = _load_stooq_prices([symbol], start_date, end_date)
        if not stooq.empty:
            prices = stooq
    if prices.empty:
        raise ValueError(f"No OHLCV data available for {symbol}")

    prices["as_of_date"] = pd.to_datetime(prices["as_of_date"])
    latest_date = _latest_complete_date(prices, as_of)
    latest_iso = f"{latest_date.isoformat()}T21:00:00Z"
    snapshot = _compute_snapshot_rows(
        prices,
        {symbol},
        latest_date,
        _ticker_profiles([symbol]),
        exclude_stale=False,
    )
    data_notes: list[str] = []
    stale = list(snapshot.attrs.get("stale_excluded", []))
    if stale:
        data_notes.append(
            f"{symbol} has no recent price bar within {_MAX_BAR_STALENESS_BDAYS}"
            " sessions; levels may reflect stale or halted data"
        )
    if snapshot.empty:
        raise ValueError(f"Not enough complete OHLCV history to analyze {symbol}")
    return snapshot, latest_iso, data_notes


def _compute_snapshot_rows(
    prices: pd.DataFrame,
    liquid: set[str],
    latest_date: date,
    profiles: dict[str, dict[str, Any]],
    *,
    exclude_stale: bool = True,
) -> pd.DataFrame:
    """Shared indicator/row computation used by every price source.

    `profiles` must supply name/sector/fcf_ttm/debt_to_equity/gp_to_assets per
    ticker; missing keys default safely so any profile provider works.
    """

    def _last_wilder_atr(
        high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14
    ) -> float | None:
        high_values = high.to_numpy(dtype=float)
        low_values = low.to_numpy(dtype=float)
        close_values = close.to_numpy(dtype=float)
        if len(close_values) < length:
            return None
        true_ranges: list[float] = []
        for idx, high_value in enumerate(high_values):
            low_value = low_values[idx]
            if idx == 0:
                true_ranges.append(float(high_value - low_value))
                continue
            previous_close = close_values[idx - 1]
            true_ranges.append(
                float(
                    max(
                        high_value - low_value,
                        abs(high_value - previous_close),
                        abs(low_value - previous_close),
                    )
                )
            )
        atr = sum(true_ranges[:length]) / length
        for true_range in true_ranges[length:]:
            atr = ((atr * (length - 1)) + true_range) / length
        return atr

    rows: list[dict[str, Any]] = []
    stale_excluded: list[str] = []
    for ticker, group in prices.groupby("ticker"):
        if ticker not in liquid:
            continue
        history = group[group["as_of_date"].dt.date <= latest_date].sort_values(
            "as_of_date"
        )
        if len(history) < 252:
            continue
        # Per-ticker freshness gate: a genuinely-trading liquid name has a bar on
        # (or within a few sessions of) the latest global trading day. A name whose
        # last bar is materially stale is halted / suspended / acquired / delisted
        # (e.g. CTLP frozen at its $11.20 buyout price) — its stale close sits near
        # the old 52w high and would otherwise pass the screen. Exclude it.
        last_bar = history["as_of_date"].iloc[-1].date()
        # Market-aware gap (US Mon-Fri vs Saudi Sun-Thu) so a Saudi name isn't
        # judged stale on the US calendar and vice-versa.
        if trading_days_between(last_bar, latest_date, market_of(ticker)) > _MAX_BAR_STALENESS_BDAYS:
            stale_excluded.append(str(ticker))
            if exclude_stale:
                continue
        close = history["close"].astype(float)
        high = history["high"].astype(float)
        low = history["low"].astype(float)
        volume = history["volume"].astype(float)
        atr = _last_wilder_atr(high, low, close, length=14)
        ret_12_1 = (
            float(close.iloc[-22] / close.iloc[-253] - 1.0)
            if len(close) > 252 and close.iloc[-253] != 0
            else None
        )
        sma_50 = close.tail(50).mean() if len(close) >= 50 else None
        sma_150 = close.tail(150).mean() if len(close) >= 150 else None
        sma_200 = close.tail(200).mean() if len(close) >= 200 else None
        sma_200_20d_ago = close.iloc[-220:-20].mean() if len(close) >= 220 else None
        if atr is None or ret_12_1 is None or pd.isna(ret_12_1):
            continue
        prior_high_20 = high.iloc[:-1].tail(20).max() if len(high) > 20 else None
        prior_high_50 = high.iloc[:-1].tail(50).max() if len(high) > 50 else None
        contraction_low_20 = low.tail(20).min() if len(low) >= 20 else None
        avg_volume_50 = volume.iloc[:-1].tail(50).mean() if len(volume) > 50 else None
        volume_ratio_50 = (
            float(volume.iloc[-1] / avg_volume_50)
            if avg_volume_50 is not None
            and pd.notna(avg_volume_50)
            and avg_volume_50 > 0
            else None
        )
        avg_volume_5 = volume.tail(5).mean() if len(volume) >= 5 else None
        # Smoothed recent participation (5d avg / 50d avg): less noisy than the
        # single-day ratio, used by the midterm volume "not fading" gate.
        volume_ratio_recent = (
            float(avg_volume_5 / avg_volume_50)
            if avg_volume_5 is not None
            and avg_volume_50 is not None
            and pd.notna(avg_volume_50)
            and avg_volume_50 > 0
            else None
        )
        daily_range = (high / low) - 1.0
        recent_adr = daily_range.tail(20).mean() if len(daily_range) >= 20 else None
        prior_adr = daily_range.iloc[-40:-20].mean() if len(daily_range) >= 40 else None
        adr_ratio = (
            float(recent_adr / prior_adr)
            if recent_adr is not None
            and prior_adr is not None
            and pd.notna(recent_adr)
            and pd.notna(prior_adr)
            and prior_adr > 0
            else None
        )
        chandelier_exit = (
            float(high.tail(22).max() - atr * 3.0) if len(high) >= 22 else None
        )
        profile = profiles.get(str(ticker), {})
        rows.append(
            {
                "ticker": str(ticker),
                "name": profile.get("name", str(ticker)),
                "sector": profile.get("sector", "Unclassified"),
                "close": float(close.iloc[-1]),
                "high": float(high.iloc[-1]),
                "low": float(low.iloc[-1]),
                "volume": int(volume.iloc[-1]),
                # George-Hwang PTH uses the peak daily *closing* price (T149).
                "52w_high": float(close.tail(252).max()),
                "return_12_1": float(ret_12_1),
                "sma_50": float(sma_50) if pd.notna(sma_50) else None,
                "sma_150": float(sma_150) if pd.notna(sma_150) else None,
                "sma_200": float(sma_200) if pd.notna(sma_200) else None,
                "sma_200_20d_ago": (
                    float(sma_200_20d_ago)
                    if sma_200_20d_ago is not None and pd.notna(sma_200_20d_ago)
                    else None
                ),
                "fcf_ttm": profile.get("fcf_ttm"),
                "debt_to_equity": profile.get("debt_to_equity"),
                "gp_to_assets": profile.get("gp_to_assets"),
                "asset_growth": profile.get("asset_growth"),
                "atr": float(atr),
                "breakout_high_20": (
                    float(prior_high_20)
                    if prior_high_20 is not None and pd.notna(prior_high_20)
                    else None
                ),
                "breakout_high_50": (
                    float(prior_high_50)
                    if prior_high_50 is not None and pd.notna(prior_high_50)
                    else None
                ),
                "contraction_low_20": (
                    float(contraction_low_20)
                    if contraction_low_20 is not None and pd.notna(contraction_low_20)
                    else None
                ),
                "adr_ratio_20_20": float(adr_ratio) if adr_ratio is not None else None,
                "avg_volume_50": (
                    float(avg_volume_50)
                    if avg_volume_50 is not None and pd.notna(avg_volume_50)
                    else None
                ),
                "volume_ratio_50": volume_ratio_50,
                "volume_ratio_recent": volume_ratio_recent,
                "chandelier_exit": chandelier_exit,
                "daily_returns": close.pct_change().dropna().tail(126),
            }
        )

    snapshot = pd.DataFrame(rows)
    snapshot.attrs["stale_excluded"] = stale_excluded
    return snapshot


STOOQ_PARQUET_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "prices" / "stooq_parquet"
)
EDGAR_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "edgar_cache"
SNAPSHOT_CACHE_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "cache" / "snapshots"
)


def _load_stooq_prices(
    tickers: list[str], start_date: date, end_date: date
) -> pd.DataFrame:
    """Read local Stooq parquet for a ticker subset (fast, no network/rate limits)."""
    if not tickers or not STOOQ_PARQUET_DIR.exists():
        return pd.DataFrame()
    ticker_set = {ticker.upper() for ticker in tickers}
    filters = [
        ("as_of_date", ">=", pd.Timestamp(start_date)),
        ("as_of_date", "<=", pd.Timestamp(end_date)),
    ]
    if len(ticker_set) <= 1000:
        filters.append(("ticker", "in", sorted(ticker_set)))
    try:
        df = pd.read_parquet(STOOQ_PARQUET_DIR, filters=filters)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    if len(ticker_set) > 1000:
        df = df[df["ticker"].astype(str).str.upper().isin(ticker_set)]
    df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    return df


_FRESH_OVERLAY_ENABLED = os.getenv("SCREENER_FRESH_OVERLAY", "1") != "0"
_OVERLAY_COLUMNS = ["ticker", "as_of_date", "open", "high", "low", "close", "volume"]
_WARM_STORE_DIR = Path(__file__).resolve().parents[2] / "data" / "prices" / "parquet"


def _warm_store_signature() -> float:
    """Newest mtime across the warm yfinance store — a cheap cache-busting signature.
    Any incremental ingest (save_prices) bumps it, so the overlaid snapshot cache
    refreshes the same day new bars land instead of waiting out the disk TTL."""
    try:
        if not _WARM_STORE_DIR.exists():
            return 0.0
        return max(
            (p.stat().st_mtime for p in _WARM_STORE_DIR.rglob("*.parquet")),
            default=0.0,
        )
    except Exception:
        return 0.0


def _overlay_fresh_prices(
    stooq_prices: pd.DataFrame, tickers: list[str], end_date: date
) -> pd.DataFrame:
    """Overlay recent warm-store (yfinance) bars onto Stooq deep history (T132a).

    The Stooq parquet is a static deep-history archive, so its last bar goes stale
    daily. The yfinance store (populated incrementally by scripts/ingest_daily.py)
    carries today's bars. Merging the store's recent rows on top makes the live
    halal screen current with ZERO per-run network calls — it only reads the warm
    cache. yfinance wins on overlapping (ticker, date). The backtest path never
    calls this, so deep-history backtests stay Stooq-only and reproducible.
    """
    if stooq_prices.empty:
        return stooq_prices
    try:
        stooq_max = pd.Timestamp(stooq_prices["as_of_date"].max())
        # small overlap window absorbs late restatements without a full reload
        overlay_start = (stooq_max - pd.Timedelta(days=5)).date()
        fresh = load_prices(tickers, start_date=overlay_start, end_date=end_date)
    except Exception:
        return stooq_prices
    if fresh is None or fresh.empty:
        return stooq_prices

    fresh = fresh.copy()
    fresh["as_of_date"] = pd.to_datetime(fresh["as_of_date"])
    fresh["ticker"] = fresh["ticker"].astype(str).str.upper()
    fresh = fresh[[c for c in _OVERLAY_COLUMNS if c in fresh.columns]]

    base = stooq_prices.copy()
    base["as_of_date"] = pd.to_datetime(base["as_of_date"])
    base["ticker"] = base["ticker"].astype(str).str.upper()
    base = base[[c for c in _OVERLAY_COLUMNS if c in base.columns]]

    base["_src"] = 0  # Stooq
    fresh["_src"] = 1  # yfinance overlay wins on overlap (keep="last")
    merged = pd.concat([base, fresh], ignore_index=True)
    merged = merged.sort_values(["ticker", "as_of_date", "_src"])
    merged = merged.drop_duplicates(["ticker", "as_of_date"], keep="last")
    return merged.drop(columns=["_src"]).reset_index(drop=True)


def _stooq_snapshot_cache_id(cache_key: tuple[Any, ...]) -> str:
    raw = json.dumps(
        {"version": _STOOQ_SNAPSHOT_CACHE_VERSION, "key": cache_key},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _load_stooq_snapshot_from_disk(
    cache_key: tuple[Any, ...],
) -> tuple[pd.DataFrame, str] | None:
    cache_id = _stooq_snapshot_cache_id(cache_key)
    meta_path = SNAPSHOT_CACHE_DIR / f"{cache_id}.json"
    data_path = SNAPSHOT_CACHE_DIR / f"{cache_id}.pkl"
    if not meta_path.exists() or not data_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(
            str(meta["cached_at"]).replace("Z", "+00:00")
        )
        if datetime.now(timezone.utc) - cached_at > timedelta(
            seconds=_DISK_SNAPSHOT_CACHE_TTL_SECONDS
        ):
            return None
        return pd.read_pickle(data_path), str(meta["data_as_of"])
    except Exception:
        return None


def _save_stooq_snapshot_to_disk(
    cache_key: tuple[Any, ...], snapshot: pd.DataFrame, data_as_of: str
) -> None:
    try:
        SNAPSHOT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_id = _stooq_snapshot_cache_id(cache_key)
        snapshot.to_pickle(SNAPSHOT_CACHE_DIR / f"{cache_id}.pkl")
        (SNAPSHOT_CACHE_DIR / f"{cache_id}.json").write_text(
            json.dumps(
                {
                    "cached_at": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "data_as_of": data_as_of,
                    "row_count": int(len(snapshot)),
                    "version": _STOOQ_SNAPSHOT_CACHE_VERSION,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    except Exception:
        return


def _edgar_profiles(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """Profiles from the local EDGAR slim cache (no network). Missing -> safe defaults."""
    from ..data.fundamentals import FundamentalsLoader
    from ..data.sectors import SectorMapper

    loader = FundamentalsLoader()
    mapper = SectorMapper()
    today = date.today()
    # Warm profile TTL cache (populated by scripts/ingest_daily.py via
    # refresh_profiles): fills name/sector and any quality metric the EDGAR slim
    # cache lacks. Read-only — no network. EDGAR stays authoritative where present
    # (point-in-time discipline); the overlay only fills holes.
    try:
        from ..data.profiles import load_cached_profiles

        warm_profiles, _ = load_cached_profiles(tickers)
    except Exception:
        warm_profiles = {}
    out: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        path = EDGAR_CACHE_DIR / f"{ticker}.json"
        quality: dict[str, Any] = {}
        sector = "Unclassified"
        if path.exists():
            try:
                slim = json.loads(path.read_text(encoding="utf-8"))
                quality = loader.quality_metrics_as_of(ticker, today, payload=slim)
                sector = mapper.get_sector(slim.get("sic"))
            except Exception:
                quality, sector = {}, "Unclassified"
        warm = warm_profiles.get(ticker, {})
        if sector == "Unclassified" and warm.get("sector"):
            sector = str(warm["sector"])
        out[ticker] = {
            "name": str(warm.get("name") or ticker),
            "sector": sector,
            "fcf_ttm": (
                quality.get("fcf_ttm")
                if quality.get("fcf_ttm") is not None
                else warm.get("fcf_ttm")
            ),
            "debt_to_equity": (
                quality.get("debt_to_equity")
                if quality.get("debt_to_equity") is not None
                else warm.get("debt_to_equity")
            ),
            "gp_to_assets": (
                quality.get("gp_to_assets")
                if quality.get("gp_to_assets") is not None
                else warm.get("gp_to_assets")
            ),
            # asset_growth is EDGAR-only (the warm profile cache doesn't store it);
            # missing -> the strategy's AG gate fails open.
            "asset_growth": quality.get("asset_growth"),
        }
    return out


def build_universe_snapshot_stooq(
    tickers: list[str],
    as_of_date: str | None = None,
    min_adv_20d: float = 1_000_000,
    min_price: float = 5.0,
) -> tuple[pd.DataFrame, str]:
    """Snapshot for a (large) ticker list using local Stooq prices + EDGAR-cache
    fundamentals. Used for Shariah-universe screens so the engine can run over the
    full compliant list without per-name yfinance calls."""
    cache_key = (
        tuple(sorted(tickers)),
        as_of_date,
        float(min_adv_20d),
        float(min_price),
        bool(_FRESH_OVERLAY_ENABLED),
        _warm_store_signature() if _FRESH_OVERLAY_ENABLED else 0.0,
    )
    cached = _STOOQ_SNAPSHOT_CACHE.get(cache_key)
    if (
        cached
        and (datetime.now(timezone.utc) - cached[0]).total_seconds()
        <= _SNAPSHOT_CACHE_TTL_SECONDS
    ):
        return cached[1].copy(deep=True), cached[2]
    disk_cached = _load_stooq_snapshot_from_disk(cache_key)
    if disk_cached is not None:
        snapshot, data_as_of = disk_cached
        _STOOQ_SNAPSHOT_CACHE[cache_key] = (
            datetime.now(timezone.utc),
            snapshot.copy(deep=True),
            data_as_of,
        )
        return snapshot.copy(deep=True), data_as_of

    end_date = (
        pd.Timestamp(as_of_date).date() if as_of_date else date.today()
    ) + timedelta(days=1)
    start_date = end_date - timedelta(days=650)
    if not tickers:
        return pd.DataFrame(), f"{(end_date - timedelta(days=1)).isoformat()}T21:00:00Z"
    prices = _load_stooq_prices(tickers, start_date, end_date)
    if prices.empty:
        # No local Stooq coverage -> fall back to the yfinance-backed builder.
        return build_universe_snapshot(
            tickers, as_of_date=as_of_date, min_adv_20d=min_adv_20d, min_price=min_price
        )
    # T132a: overlay fresh warm-store (yfinance) bars so the live screen is current
    # even though the Stooq archive is static. Reads cache only; no network.
    if _FRESH_OVERLAY_ENABLED:
        prices = _overlay_fresh_prices(prices, tickers, end_date)
    prices = drop_market_weekends(prices)  # market-aware: drop stray weekend bars
    latest_date = _latest_complete_date(prices, as_of_date)
    latest_iso = f"{latest_date.isoformat()}T21:00:00Z"
    liquid = set(
        UniverseLoader(prices).get_liquid_universe(
            latest_date.isoformat(), min_adv_20d=min_adv_20d, min_price=min_price
        )
    )
    profiles = _edgar_profiles(sorted(liquid))
    snapshot = _compute_snapshot_rows(prices, liquid, latest_date, profiles)
    _STOOQ_SNAPSHOT_CACHE[cache_key] = (
        datetime.now(timezone.utc),
        snapshot.copy(deep=True),
        latest_iso,
    )
    _save_stooq_snapshot_to_disk(cache_key, snapshot, latest_iso)
    return snapshot, latest_iso


_STOOQ_TICKER_SET: set[str] | None = None
_US_TICKER_RE = re.compile(r"[A-Z]{1,5}(\.[A-Z])?$")


def _stooq_ticker_set() -> set[str]:
    """Cached set of tickers present in the local Stooq US-exchange parquet."""
    global _STOOQ_TICKER_SET
    if _STOOQ_TICKER_SET is None:
        parts = glob.glob(str(STOOQ_PARQUET_DIR / "part-*.parquet"))
        if parts:
            frames = [pd.read_parquet(p, columns=["ticker"]) for p in parts]
            _STOOQ_TICKER_SET = set(pd.concat(frames)["ticker"].astype(str).unique())
        else:
            _STOOQ_TICKER_SET = set()
    return _STOOQ_TICKER_SET


def _drop_foreign_otc_noise(tickers: set[str]) -> set[str]:
    """Keep only US-exchange-listed names. The Stooq US bundle IS the US exchange
    universe, so membership in it cleanly drops foreign listings ('000270 KS',
    '1093 HK'), OTC ADRs ('ADDYY'), and junk ('CASH&OTHER', CUSIPs). Falls back
    to a US-ticker regex when the Stooq parquet is unavailable (fresh clone)."""
    stooq = _stooq_ticker_set()
    if stooq:
        return tickers & stooq
    return {t for t in tickers if _US_TICKER_RE.fullmatch(t)}


def _compliant_universe(normalized_overrides: dict[str, Any]) -> list[str]:
    """Tickers compliant under the active sources + user inclusion, minus user exclusion.

    External-source tickers are filtered to US-exchange-listed names (foreign/OTC/junk
    dropped); explicit user inclusions are kept as-is so a deliberate override is honored.
    """
    lookup = ShariahLookup(normalized_overrides)
    exclusion = set(lookup.exclusion.keys())
    external = set(lookup.rows_by_ticker.keys()) - exclusion
    inclusion = set(lookup.inclusion.keys()) - exclusion
    return sorted(_drop_foreign_otc_noise(external) | inclusion)


REFERENCE_SHARIAH_SOURCES = [
    "spus_holdings",
    "spwo_holdings",
    "spre_holdings",
    "spte_holdings",
    "halal_terminal",
]


def refresh_reference_thresholds(as_of_date: str | None = None) -> dict:
    """Compute + cache the gross-profitability / asset-growth percentile thresholds
    over the COMPLIANT (Shariah) universe — the set actually screened — so the
    cross-sectional gates grade each name against its investable peer group, not
    the whole market (which skews lower-growth and unfairly fails compliant names).
    Using a single cached cut also keeps a name's verdict consistent across the
    screen, single-ticker analysis, and the candidate detail page. Refreshed
    alongside prices; read by the strategy's _apply_cross_sectional_gates."""
    from ..strategies._helpers.reference_thresholds import (
        compute_thresholds,
        save_reference_thresholds,
    )
    from ..strategies.midterm_52w_high_momentum import PARAMETERS

    overrides = normalize_shariah_overrides(
        {"active_sources": REFERENCE_SHARIAH_SOURCES}
    )
    tickers = _compliant_universe(overrides)
    if tickers:
        universe, data_as_of = build_universe_snapshot_stooq(tickers, as_of_date=as_of_date)
    else:
        universe, data_as_of = build_universe_snapshot(
            DEFAULT_SCREEN_TICKERS, as_of_date=as_of_date
        )
    gp_pct = float(PARAMETERS["min_gp_assets_percentile"].default)
    ag_pct = float(PARAMETERS["max_asset_growth_percentile"].default)
    gp_threshold, ag_threshold = compute_thresholds(universe, gp_pct, ag_pct)
    return save_reference_thresholds(
        gp_threshold, ag_threshold, universe_size=int(len(universe)), as_of=data_as_of
    )


def _opt_float(value: Any) -> float | None:
    """Coerce a DataFrame cell to a plain float, or None when missing/NaN."""
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def run_strategy(
    strategy_slug: str,
    parameters: dict[str, Any] | None = None,
    filters: dict[str, Any] | None = None,
    shariah_overrides: dict[str, Any] | None = None,
    as_of_date: str | None = None,
) -> ScreenResult:
    strategy = registry.get(strategy_slug)
    if strategy is None:
        from .. import strategies as _strategies

        strategy = registry.get(strategy_slug)
    if strategy is None:
        raise KeyError(strategy_slug)

    parameters_snapshot = dict(parameters or {})
    # Market selector (centralized so every caller — screen, candidate detail,
    # analyze — behaves the same). Saudi (Tadawul) → screen the `.SR` universe with
    # SAR-calibrated liquidity and no SPY-based regime gate. Operator values win.
    if str(parameters_snapshot.get("market", "")).upper() in {"SA", "SAUDI", "TADAWUL"}:
        from ..data.saudi_universe import saudi_universe

        parameters_snapshot.setdefault("tickers", saudi_universe())
        parameters_snapshot.setdefault("liquidity_min_price", 10.0)
        parameters_snapshot.setdefault("liquidity_min_avg_dollar_volume_20d", 3_000_000.0)
        parameters_snapshot.setdefault("regime_gate", False)
    shariah_only = bool((filters or {}).get("shariah_only", False))
    normalized_shariah_overrides = normalize_shariah_overrides(shariah_overrides or {})
    filters_snapshot: dict[str, Any] = {
        "shariah_only": shariah_only,
        "exclude_earnings_within_days": (filters or {}).get(
            "exclude_earnings_within_days",
            strategy.default_exclude_earnings_within_days,
        ),
    }
    if shariah_only:
        filters_snapshot.update(
            {
                "shariah_active_sources": normalized_shariah_overrides[
                    "active_sources"
                ],
                "shariah_user_inclusion": normalized_shariah_overrides["inclusion"],
                "shariah_user_exclusion": normalized_shariah_overrides["exclusion"],
            }
        )

    min_adv_20d = float(
        parameters_snapshot.get("liquidity_min_avg_dollar_volume_20d", 1_000_000)
    )
    min_price = float(parameters_snapshot.get("liquidity_min_price", 5.0))
    if shariah_only:
        # Screen the actual compliant universe (hundreds of names) sourced from the
        # local Stooq archive + EDGAR-cache fundamentals, instead of post-filtering
        # the 20-name default set.
        universe, data_as_of = build_universe_snapshot_stooq(
            _compliant_universe(normalized_shariah_overrides),
            as_of_date=as_of_date,
            min_adv_20d=min_adv_20d,
            min_price=min_price,
        )
    else:
        explicit_tickers = _has_explicit_tickers(parameters_snapshot)
        stooq_tickers = [] if explicit_tickers else _all_stooq_tickers()
        if stooq_tickers:
            universe, data_as_of = build_universe_snapshot_stooq(
                stooq_tickers,
                as_of_date=as_of_date,
                min_adv_20d=min_adv_20d,
                min_price=min_price,
            )
        else:
            universe, data_as_of = build_universe_snapshot(
                _parse_tickers(parameters_snapshot),
                as_of_date=as_of_date,
                min_adv_20d=min_adv_20d,
                min_price=min_price,
            )

    # Regime master switch (Faber 2007 / T108a): for strategies that mark
    # downtrends Unfavorable, take no NEW entries while SPY is below its 200-day
    # SMA. Enabled by default; pass parameters.regime_gate=false to disable.
    regime_gate_enabled = bool(parameters_snapshot.get("regime_gate", True))
    regime_sensitive = strategy_is_regime_sensitive(
        getattr(strategy, "regime_favorability", {}) or {}
    )
    regime_info = (
        market_regime(as_of_date=as_of_date)
        if regime_gate_enabled and regime_sensitive
        else None
    )
    regime_blocks = bool(
        regime_info is not None and not regime_info["allows_new_entries"]
    )

    data_notes: list[str] = []
    stale_excluded = (
        list(universe.attrs.get("stale_excluded", [])) if not universe.empty else []
    )
    if stale_excluded:
        sample = ", ".join(sorted(stale_excluded)[:8])
        data_notes.append(
            f"excluded {len(stale_excluded)} halted/suspended name(s) with no recent"
            f" price bar (stale > {_MAX_BAR_STALENESS_BDAYS} sessions): {sample}"
            + ("…" if len(stale_excluded) > 8 else "")
        )
    if universe.empty or regime_blocks:
        results = pd.DataFrame()
        if universe.empty and not regime_blocks:
            data_notes.append(
                "strategy did not run: empty universe after the liquidity gate"
                " (no price data, or every name failed price/ADV minimums)"
            )
    else:
        # Universe-level fundamentals coverage (the quality screen fails closed,
        # so missing fundamentals silently shrink results — report it instead).
        if "fcf_ttm" in universe.columns:
            missing_fund = int(
                (universe["fcf_ttm"].isna() | universe["debt_to_equity"].isna()).sum()
            )
            if missing_fund:
                data_notes.append(
                    f"fundamentals missing for {missing_fund}/{len(universe)} names"
                    " in the screened universe (those names cannot pass the quality gate)"
                )
        # Per-run sector-strength gate toggle (UI option): forward the requested
        # fraction to the strategy via attrs (1.0 = off; 0<f<1 = keep top f sectors).
        if parameters_snapshot.get("sector_strength_top_fraction") is not None:
            universe.attrs["sector_strength_top_fraction"] = parameters_snapshot[
                "sector_strength_top_fraction"
            ]
        results = strategy.rules(universe)
        data_notes.extend(results.attrs.get("gates_skipped", []))
        if not results.empty and {"score", "ticker"}.issubset(results.columns):
            # Tiered gates (Decision 7): rank cleanest (fewest warnings) first,
            # then by momentum score. Falls back to score-only when no warnings col.
            if "warning_count" in results.columns:
                results = results.sort_values(
                    ["warning_count", "score", "ticker"], ascending=[True, False, True]
                )
            else:
                results = results.sort_values(["score", "ticker"], ascending=[False, True])

    # Price-bar freshness: warn when the newest bar backing this screen is older
    # than 3 business days (entry/stop/take-profit levels would be stale).
    try:
        bar_age_bdays = int(
            len(
                pd.bdate_range(
                    date.fromisoformat(data_as_of[:10]),
                    date.today(),
                    inclusive="neither",
                )
            )
        )
    except Exception:
        bar_age_bdays = 0
    if bar_age_bdays > 3:
        data_notes.append(
            f"price data is stale: last bar {data_as_of[:10]} is {bar_age_bdays}"
            " business days old — entry/stop/take-profit levels may be outdated"
            " (run scripts/ingest_daily.py)"
        )

    event_snapshots: dict[str, TickerEventsSnapshot] = {}
    events_service = EventsService()
    screen_as_of = date.fromisoformat(data_as_of[:10])
    exclude_earnings_within_days = int(
        filters_snapshot.get("exclude_earnings_within_days") or 0
    )
    refresh_events = bool(parameters_snapshot.get("refresh_events", False))
    if not results.empty:
        for ticker in results["ticker"].astype(str).str.upper().tolist():
            event_snapshots[ticker] = events_service.ticker_events(
                ticker,
                as_of_date=screen_as_of,
                refresh=refresh_events,
                earnings_days_ahead=max(exclude_earnings_within_days, 90),
            )
        if exclude_earnings_within_days > 0:
            results = results[
                results["ticker"]
                .astype(str)
                .str.upper()
                .map(
                    lambda ticker: not (
                        event_snapshots[ticker].days_to_earnings is not None
                        and 0
                        <= event_snapshots[ticker].days_to_earnings
                        <= exclude_earnings_within_days
                    )
                )
            ].copy()

    shariah_statuses = {}
    stale_sources: list[str] = []
    for snapshot in event_snapshots.values():
        for source in snapshot.sources:
            if source.is_stale and source.source_name not in stale_sources:
                stale_sources.append(source.source_name)
    if shariah_only:
        lookup = ShariahLookup(normalized_shariah_overrides)
        stale_sources = [
            *stale_sources,
            *[source for source in lookup.stale_sources if source not in stale_sources],
        ]
        if not results.empty:
            shariah_statuses = lookup.statuses(results["ticker"].astype(str).tolist())
            results = results[
                results["ticker"]
                .astype(str)
                .str.upper()
                .map(lambda ticker: shariah_statuses[ticker].is_compliant)
            ].copy()
            assert all(
                shariah_statuses[str(ticker).upper()].is_compliant
                for ticker in results["ticker"]
            )

    candidates: list[Candidate] = []
    for rank, row in enumerate(results.itertuples(index=False), start=1):
        shariah_status = (
            shariah_statuses.get(str(row.ticker).upper()) if shariah_only else None
        )
        event_snapshot = event_snapshots.get(str(row.ticker).upper())
        event_source_as_of = (
            max(
                (source.source_as_of for source in event_snapshot.sources), default=None
            )
            if event_snapshot
            else None
        )
        candidates.append(
            Candidate(
                ticker=row.ticker,
                name=row.name,
                sector=row.sector,
                strategy_slug=strategy.slug,
                strategy_name=strategy.name,
                timeframe=strategy.timeframe,
                current_price=f"{row.close:.2f}",
                entry=f"{row.entry:.2f}",
                stop_loss=f"{max(row.stop_loss, 0.01):.2f}",
                tighter_stop_loss=(
                    f"{max(float(_tighter), 0.01):.2f}"
                    if (_tighter := getattr(row, "tighter_stop_loss", None)) is not None
                    and pd.notna(_tighter)
                    else None
                ),
                take_profit=f"{row.take_profit:.2f}",
                rank=rank,
                score=round(float(row.score), 6),
                reason=row.reason,
                return_12_1=_opt_float(getattr(row, "return_12_1", None)),
                vol_scalar=_opt_float(getattr(row, "vol_scalar", None)),
                dist_to_high=_opt_float(getattr(row, "dist_to_high", None)),
                atr=_opt_float(getattr(row, "atr", None)),
                debt_to_equity=_opt_float(getattr(row, "debt_to_equity", None)),
                fcf_ttm=_opt_float(getattr(row, "fcf_ttm", None)),
                gp_to_assets=_opt_float(getattr(row, "gp_to_assets", None)),
                asset_growth=_opt_float(getattr(row, "asset_growth", None)),
                gate_results=getattr(row, "gate_results", None) or [],
                warnings=list(getattr(row, "warnings", None) or []),
                shariah_compliant=(
                    shariah_status.is_compliant if shariah_status else None
                ),
                shariah_source_kind=(
                    shariah_status.source_kind if shariah_status else None
                ),
                shariah_external_source_name=(
                    shariah_status.external_source_name if shariah_status else None
                ),
                shariah_source_as_of=(
                    shariah_status.external_source_as_of if shariah_status else None
                ),
                shariah_source_url=(
                    shariah_status.source_url if shariah_status else None
                ),
                shariah_user_note=shariah_status.user_note if shariah_status else None,
                shariah_is_stale=shariah_status.is_stale if shariah_status else None,
                next_earnings_date=(
                    event_snapshot.next_earnings_date if event_snapshot else None
                ),
                days_to_earnings=(
                    event_snapshot.days_to_earnings if event_snapshot else None
                ),
                recent_8k_count_30d=(
                    event_snapshot.recent_8k_count_30d if event_snapshot else 0
                ),
                events_source_as_of=event_source_as_of,
            )
        )

    snapshot_date = data_as_of[:10]
    return ScreenResult(
        id=_stable_id(
            strategy_slug, snapshot_date, parameters_snapshot, filters_snapshot
        ),
        strategy_slug=strategy_slug,
        as_of_date=snapshot_date,
        parameters_snapshot=parameters_snapshot,
        filters_snapshot=filters_snapshot,
        candidate_count=len(candidates),
        candidates=candidates,
        computed_at=utc_now_iso(),
        data_as_of=data_as_of,
        disclaimer=DISCLAIMER_TEXT,
        stale_sources=stale_sources,
        data_notes=data_notes,
        regime=regime_info["regime"] if regime_info else None,
        regime_allows_new_entries=(
            regime_info["allows_new_entries"] if regime_info else None
        ),
        regime_note=regime_info["note"] if regime_info else None,
    )
