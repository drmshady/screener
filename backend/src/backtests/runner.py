from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.src.backtests.bias_check import build_bias_check, to_markdown
from backend.src.backtests.metrics import summarize_portfolio, yearly_metric
from backend.src.data.fundamentals import FundamentalsLoader
from backend.src.data.prices import YFinancePriceProvider
from backend.src.data.sectors import SectorMapper
from backend.src.data.stooq_history import StooqHistoricalProvider
from backend.src.indicators.momentum import calculate_12_1_return
from backend.src.indicators.price_action import calculate_chandelier_exit_long
from backend.src.indicators.volatility import calculate_adr_ratio, calculate_atr
from backend.src.screening.engine import DEFAULT_SCREEN_TICKERS
from backend.src.strategies._registry import registry
from backend.src import strategies as _strategies  # noqa: F401 - imports register strategy modules

CONSOLIDATED_DIR = ROOT / "backend" / "data" / "prices" / "stooq_parquet"
EDGAR_CACHE = ROOT / "backend" / "data" / "edgar_cache"
SEC_RATE_LIMIT_SLEEP = 0.12  # SEC asks for <= 10 requests/second

# Concepts the point-in-time quality gate consumes.
NEEDED_TAGS = [
    "GrossProfit",
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "CostOfRevenue",
    "CostOfGoodsAndServicesSold",
    "Assets",
    "Liabilities",
    "StockholdersEquity",
    "NetCashProvidedByUsedInOperatingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment",
]

# Strategy gate parameters (kept in step with midterm_52w_high_momentum.PARAMETERS).
PROXIMITY_PCT = 0.05
MIN_PRICE = 5.0
MIN_ADV_20D = 1_000_000.0
HOLDING_HORIZON_DAYS = 126
TOP_N = 10


def _tickers(raw: str | None) -> list[str]:
    if raw is None:
        return DEFAULT_SCREEN_TICKERS
    return sorted({part.strip().upper() for part in raw.split(",") if part.strip()})


# --------------------------------------------------------------------------- #
# Price loading + feature precompute (full universe, vectorized)
# --------------------------------------------------------------------------- #
def load_consolidated_prices(start: date, end: date) -> pd.DataFrame | None:
    parts = sorted(glob.glob(str(CONSOLIDATED_DIR / "part-*.parquet")))
    if not parts:
        return None
    frames = [pd.read_parquet(p) for p in parts]
    prices = pd.concat(frames, ignore_index=True)
    prices["as_of_date"] = pd.to_datetime(prices["as_of_date"])
    lo = pd.Timestamp(start) - timedelta(days=650)
    hi = pd.Timestamp(end) + timedelta(days=90)
    prices = prices[(prices["as_of_date"] >= lo) & (prices["as_of_date"] <= hi)]
    return prices.sort_values(["ticker", "as_of_date"]).reset_index(drop=True)


def precompute_features(prices: pd.DataFrame) -> pd.DataFrame:
    """Vectorized rolling features used by the liquidity + near-high pre-filter."""
    g = prices.groupby("ticker", sort=False)
    prices["sma_50"] = g["close"].transform(lambda s: s.rolling(50, min_periods=50).mean())
    prices["sma_150"] = g["close"].transform(lambda s: s.rolling(150, min_periods=150).mean())
    prices["sma_200"] = g["close"].transform(lambda s: s.rolling(200, min_periods=200).mean())
    prices["sma_200_20d_ago"] = prices.groupby("ticker", sort=False)["sma_200"].shift(20)
    # George-Hwang PTH uses the rolling peak daily *closing* price (T149), not the
    # intraday high. Closing-high <= intraday-high, so the 5% proximity band is a
    # touch more inclusive and matches the literature's definition.
    prices["close_high_252"] = g["close"].transform(lambda s: s.rolling(252, min_periods=252).max())
    prices["breakout_high_20"] = g["high"].transform(lambda s: s.shift(1).rolling(20, min_periods=20).max())
    prices["breakout_high_50"] = g["high"].transform(lambda s: s.shift(1).rolling(50, min_periods=50).max())
    prices["contraction_low_20"] = g["low"].transform(lambda s: s.rolling(20, min_periods=20).min())
    prices["avg_volume_50"] = g["volume"].transform(lambda s: s.shift(1).rolling(50, min_periods=50).mean())
    prices["volume_ratio_50"] = prices["volume"] / prices["avg_volume_50"]
    prices["avg_volume_5"] = g["volume"].transform(lambda s: s.rolling(5, min_periods=5).mean())
    prices["volume_ratio_recent"] = prices["avg_volume_5"] / prices["avg_volume_50"]
    daily_range = (prices["high"] / prices["low"]) - 1.0
    prices["adr_20"] = daily_range.groupby(prices["ticker"], sort=False).transform(
        lambda s: s.rolling(20, min_periods=20).mean()
    )
    prices["adr_ratio_20_20"] = prices["adr_20"] / prices.groupby("ticker", sort=False)["adr_20"].shift(20)
    dollar_vol = prices["close"] * prices["volume"]
    prices["adv20"] = dollar_vol.groupby(prices["ticker"], sort=False).transform(
        lambda s: s.rolling(20, min_periods=20).mean()
    )
    prices["n_obs"] = g.cumcount() + 1
    return prices


def _candidate_pool(prices_feat: pd.DataFrame, as_of: date, strategy_slug: str) -> pd.DataFrame:
    """Liquid names with a broad price pre-filter for the selected strategy."""
    as_of_ts = pd.Timestamp(as_of)
    visible = prices_feat[prices_feat["as_of_date"] <= as_of_ts]
    last = visible.groupby("ticker", sort=False).tail(1)
    elig = last[
        (last["close"] >= MIN_PRICE)
        & (last["adv20"] >= MIN_ADV_20D)
        & (last["n_obs"] >= 252)
        & last["sma_200"].notna()
        & last["close_high_252"].notna()
    ].copy()
    if strategy_slug == "midterm_52w_high_momentum":
        elig["dist_to_high"] = (elig["close_high_252"] - elig["close"]) / elig["close"]
        return elig[(elig["dist_to_high"] <= PROXIMITY_PCT) & (elig["close"] > elig["sma_200"])]
    if strategy_slug == "shortterm_minervini_vcp":
        needed = [
            "breakout_high_50",
            "contraction_low_20",
            "adr_ratio_20_20",
            "volume_ratio_50",
            "sma_50",
            "sma_150",
            "sma_200_20d_ago",
        ]
        elig = elig.dropna(subset=needed)
        return elig[
            (elig["close"] >= elig["breakout_high_50"])
            & (elig["adr_ratio_20_20"] <= 0.9)
            & (elig["volume_ratio_50"] >= 1.0)
            & (elig["close"] > elig["sma_200"])
            & (elig["sma_200"] > elig["sma_200_20d_ago"])
        ]
    if strategy_slug == "shortterm_atr_breakout":
        elig = elig.dropna(subset=["breakout_high_20", "sma_200_20d_ago"])
        return elig[
            (elig["close"] >= elig["breakout_high_20"])
            & (elig["close"] > elig["sma_200"])
            & (elig["sma_200"] > elig["sma_200_20d_ago"])
        ]
    return elig


# --------------------------------------------------------------------------- #
# Point-in-time fundamentals (slim, disk-cached) + sector
# --------------------------------------------------------------------------- #
def get_slim_facts(loader: FundamentalsLoader, ticker: str) -> dict[str, Any]:
    """Fetch (once) and cache only the EDGAR concepts the quality gate needs."""
    EDGAR_CACHE.mkdir(parents=True, exist_ok=True)
    path = EDGAR_CACHE / f"{ticker}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        payload = loader.fetch_company_facts(ticker)
    except Exception:
        slim = {"facts": {"us-gaap": {}}, "sic": None}
        path.write_text(json.dumps(slim), encoding="utf-8")
        time.sleep(SEC_RATE_LIMIT_SLEEP)
        return slim
    us_gaap = payload.get("facts", {}).get("us-gaap", {})
    slim = {
        "facts": {"us-gaap": {tag: us_gaap[tag] for tag in NEEDED_TAGS if tag in us_gaap}},
        "sic": payload.get("sic"),
    }
    path.write_text(json.dumps(slim), encoding="utf-8")
    time.sleep(SEC_RATE_LIMIT_SLEEP)
    return slim


def prefetch_fundamentals(
    tickers: list[str], max_workers: int = 8
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    from concurrent.futures import ThreadPoolExecutor

    loader = FundamentalsLoader()
    loader._load_cik_map()  # preload once so worker threads only read the map
    mapper = SectorMapper()
    uniq = sorted(set(tickers))
    facts: dict[str, dict[str, Any]] = {}
    sectors: dict[str, str] = {}

    def _work(ticker: str) -> tuple[str, dict[str, Any]]:
        return ticker, get_slim_facts(loader, ticker)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for i, (ticker, slim) in enumerate(executor.map(_work, uniq), start=1):
            facts[ticker] = slim
            sectors[ticker] = mapper.get_sector(slim.get("sic"))
            if i % 100 == 0:
                print(f"  fundamentals {i}/{len(uniq)}")
    return facts, sectors


# --------------------------------------------------------------------------- #
# Snapshot + forward returns
# --------------------------------------------------------------------------- #
def _build_snapshot(
    by_ticker: pd.core.groupby.DataFrameGroupBy,
    pool: pd.DataFrame,
    as_of: date,
    facts: dict[str, dict[str, Any]],
    sectors: dict[str, str],
    uses_fundamentals: bool,
) -> tuple[pd.DataFrame, int]:
    loader = FundamentalsLoader()
    as_of_ts = pd.Timestamp(as_of)
    rows: list[dict[str, Any]] = []
    point_in_time = 0
    for ticker in pool["ticker"].tolist():
        history = by_ticker.get_group(ticker)
        history = history[history["as_of_date"] <= as_of_ts]
        if len(history) < 252:
            continue
        close = history["close"].astype(float)
        high = history["high"].astype(float)
        low = history["low"].astype(float)
        volume = history["volume"].astype(float)
        atr = calculate_atr(high, low, close, length=14).iloc[-1]
        atr_series = calculate_atr(high, low, close, length=14)
        ret_12_1 = calculate_12_1_return(close).iloc[-1]
        sma_50 = close.rolling(50, min_periods=50).mean().iloc[-1]
        sma_150 = close.rolling(150, min_periods=150).mean().iloc[-1]
        sma_200 = close.rolling(200, min_periods=200).mean().iloc[-1]
        sma_200_20d_ago = close.rolling(200, min_periods=200).mean().iloc[-21] if len(close) >= 220 else None
        if pd.isna(atr) or pd.isna(ret_12_1):
            continue
        q = loader.quality_metrics_as_of(ticker, as_of, payload=facts.get(ticker)) if uses_fundamentals else {}
        if any(q.get(k) is not None for k in ("fcf_ttm", "gp_to_assets")):
            point_in_time += 1
        prior_high_20 = high.iloc[:-1].tail(20).max() if len(high) > 20 else None
        prior_high_50 = high.iloc[:-1].tail(50).max() if len(high) > 50 else None
        contraction_low_20 = low.tail(20).min() if len(low) >= 20 else None
        avg_volume_50 = volume.iloc[:-1].tail(50).mean() if len(volume) > 50 else None
        volume_ratio_50 = (
            float(volume.iloc[-1] / avg_volume_50)
            if avg_volume_50 is not None and pd.notna(avg_volume_50) and avg_volume_50 > 0
            else None
        )
        avg_volume_5 = volume.tail(5).mean() if len(volume) >= 5 else None
        volume_ratio_recent = (
            float(avg_volume_5 / avg_volume_50)
            if avg_volume_5 is not None and avg_volume_50 is not None and pd.notna(avg_volume_50) and avg_volume_50 > 0
            else None
        )
        adr_ratio = calculate_adr_ratio(high, low, recent_length=20, prior_length=20).iloc[-1]
        chandelier_exit = calculate_chandelier_exit_long(high, atr_series, length=22, multiplier=3.0).iloc[-1]
        rows.append(
            {
                "ticker": ticker,
                "name": ticker,
                "sector": sectors.get(ticker, "Unclassified"),
                "close": float(close.iloc[-1]),
                "high": float(high.iloc[-1]),
                "low": float(low.iloc[-1]),
                "volume": int(volume.iloc[-1]),
                "52w_high": float(close.tail(252).max()),  # closing-high PTH (T149)
                "return_12_1": float(ret_12_1),
                "sma_50": float(sma_50) if pd.notna(sma_50) else None,
                "sma_150": float(sma_150) if pd.notna(sma_150) else None,
                "sma_200": float(sma_200) if pd.notna(sma_200) else None,
                "sma_200_20d_ago": float(sma_200_20d_ago) if sma_200_20d_ago is not None and pd.notna(sma_200_20d_ago) else None,
                "fcf_ttm": q.get("fcf_ttm"),
                "debt_to_equity": q.get("debt_to_equity"),
                "gp_to_assets": q.get("gp_to_assets"),
                "asset_growth": q.get("asset_growth"),
                "atr": float(atr),
                "breakout_high_20": float(prior_high_20) if prior_high_20 is not None and pd.notna(prior_high_20) else None,
                "breakout_high_50": float(prior_high_50) if prior_high_50 is not None and pd.notna(prior_high_50) else None,
                "contraction_low_20": float(contraction_low_20) if contraction_low_20 is not None and pd.notna(contraction_low_20) else None,
                "adr_ratio_20_20": float(adr_ratio) if pd.notna(adr_ratio) else None,
                "avg_volume_50": float(avg_volume_50) if avg_volume_50 is not None and pd.notna(avg_volume_50) else None,
                "volume_ratio_50": volume_ratio_50,
                "volume_ratio_recent": volume_ratio_recent,
                "chandelier_exit": float(chandelier_exit) if pd.notna(chandelier_exit) else None,
                "daily_returns": close.pct_change().dropna().tail(126),
            }
        )
    return pd.DataFrame(rows), point_in_time


def _forward_return(
    by_ticker: pd.core.groupby.DataFrameGroupBy, ticker: str, as_of: date, horizon_days: int = HOLDING_HORIZON_DAYS
) -> float | None:
    group = by_ticker.get_group(ticker)
    after = group[group["as_of_date"] > pd.Timestamp(as_of)]
    if after.empty:
        return None
    entry = float(after.iloc[0]["close"])
    exit_rows = after[after["as_of_date"] >= pd.Timestamp(as_of) + timedelta(days=horizon_days)]
    exit_price = float((exit_rows.iloc[0] if not exit_rows.empty else after.iloc[-1])["close"])
    if entry <= 0:
        return None
    return (exit_price / entry) - 1


# --------------------------------------------------------------------------- #
# Backtest driver
# --------------------------------------------------------------------------- #
def _annual_as_of_dates(start: date, end: date) -> list[date]:
    return [date(y, 1, 31) for y in range(start.year, end.year + 1) if start <= date(y, 1, 31) <= end]


def detect_delisted_coverage(
    prices: pd.DataFrame, min_gap_days: int = 365, min_fraction: float = 0.02
) -> bool:
    """
    Survivorship-bias-free datasets contain tickers that stopped trading well
    before the dataset's most recent date (they delisted/went bankrupt). If a
    meaningful fraction of tickers have their last bar more than `min_gap_days`
    before the dataset end, the dataset has delisted coverage. The free Stooq
    bundle has ~none of these (every file runs to the present), so this returns
    False for it and True once real delisted history is present.
    """
    if prices.empty:
        return False
    last = prices.groupby("ticker")["as_of_date"].max()
    dataset_end = prices["as_of_date"].max()
    inactive = (dataset_end - last).dt.days > min_gap_days
    fraction = float(inactive.mean())
    print(f"Delisted coverage: {int(inactive.sum())}/{len(last)} tickers inactive ({fraction:.1%})")
    return fraction >= min_fraction


def run_backtest(
    strategy_slug: str,
    start: date,
    end: date,
    tickers: list[str] | None = None,
    prices: pd.DataFrame | None = None,
) -> dict:
    strategy = registry.get(strategy_slug)
    if strategy is None:
        raise KeyError(strategy_slug)
    uses_fundamentals = strategy_slug == "midterm_52w_high_momentum"

    source_name: str | None = None
    if prices is not None:
        # Injected price frame (e.g. a survivorship test fixture). Treat as a
        # Stooq-equivalent archive already in the standard schema.
        source_name = "stooq"
        prices = prices.copy()
        prices["as_of_date"] = pd.to_datetime(prices["as_of_date"])
        prices = prices.sort_values(["ticker", "as_of_date"]).reset_index(drop=True)
    else:
        prices = load_consolidated_prices(start, end)
        if prices is not None:
            source_name = "stooq"
    if prices is None:
        # Fallback: explicit small ticker list via Stooq per-ticker / yfinance.
        names = tickers or DEFAULT_SCREEN_TICKERS
        stooq = StooqHistoricalProvider().fetch_ohlcv(names, start - timedelta(days=650), end + timedelta(days=90))
        prices = stooq if not stooq.empty else YFinancePriceProvider().fetch_ohlcv(
            names, start - timedelta(days=650), end + timedelta(days=90)
        )
        source_name = "stooq" if not stooq.empty else "yfinance"
        if prices.empty:
            raise ValueError("No backtest price data available")
        prices["as_of_date"] = pd.to_datetime(prices["as_of_date"])
        prices = prices.sort_values(["ticker", "as_of_date"]).reset_index(drop=True)
    if tickers:
        prices = prices[prices["ticker"].isin(set(tickers))]

    delisted_coverage = detect_delisted_coverage(prices)

    prices = precompute_features(prices)
    as_of_dates = _annual_as_of_dates(start, end)

    # Pass 1: price-only near-high pools per year + union for fundamentals.
    pools: dict[date, pd.DataFrame] = {}
    union: set[str] = set()
    for as_of in as_of_dates:
        pool = _candidate_pool(prices, as_of, strategy_slug)
        pools[as_of] = pool
        union.update(pool["ticker"].tolist())
    print(f"Candidate pool union across {len(as_of_dates)} years: {len(union)} tickers")

    # Fetch point-in-time fundamentals only when the selected strategy consumes them.
    if uses_fundamentals:
        facts, sectors = prefetch_fundamentals(sorted(union))
    else:
        facts = {}
        sectors = {ticker: "Unclassified" for ticker in union}

    # Pass 2: build snapshots, run the strategy, score forward returns.
    by_ticker = prices.groupby("ticker", sort=False)
    yearly_metrics = []
    all_returns: list[float] = []
    total_point_in_time = 0
    coverage_notes: list[str] = []
    for as_of in as_of_dates:
        pool = pools[as_of]
        if pool.empty:
            yearly_metrics.append(yearly_metric(as_of.year, []))
            continue
        snapshot, pit = _build_snapshot(by_ticker, pool, as_of, facts, sectors, uses_fundamentals)
        total_point_in_time += pit
        # Honest coverage note: a year with names near their highs but almost no
        # point-in-time fundamentals can't be screened by a fundamentals strategy
        # (the quality gate fails closed). SEC XBRL/companyfacts coverage is sparse
        # before ~2011, so the 2008-2010 crisis years are structurally empty here —
        # a data limitation, not a result. Surfaced in the walk-forward panel.
        if (
            uses_fundamentals
            and not snapshot.empty
            and pit < max(1, int(0.1 * len(snapshot)))
        ):
            coverage_notes.append(
                f"{as_of.year}: {len(pool)} names near the 52-week high but only"
                f" {pit}/{len(snapshot)} had point-in-time fundamentals — the"
                " fundamentals-dependent gates could not be evaluated (SEC XBRL"
                " coverage is sparse before ~2011), so this year contributes no trades"
            )
        if snapshot.empty:
            yearly_metrics.append(yearly_metric(as_of.year, []))
            continue
        candidates = strategy.rules(snapshot)
        if candidates.empty or not {"score", "ticker"}.issubset(candidates.columns):
            yearly_metrics.append(yearly_metric(as_of.year, []))
            continue
        if "warning_count" in candidates.columns:
            candidates = candidates.sort_values(
                ["warning_count", "score", "ticker"], ascending=[True, False, True]
            ).head(TOP_N)
        else:
            candidates = candidates.sort_values(["score", "ticker"], ascending=[False, True]).head(TOP_N)
        returns = []
        horizon_days = int(strategy.holding_period_days.get("max", HOLDING_HORIZON_DAYS))
        for ticker in candidates["ticker"].tolist():
            value = _forward_return(by_ticker, ticker, as_of, horizon_days=horizon_days)
            if value is not None:
                returns.append(value)
        all_returns.extend(returns)
        yearly_metrics.append(yearly_metric(as_of.year, returns))
        print(f"  {as_of}: pool={len(pool)} candidates={len(candidates)} trades={len(returns)}")

    # Portfolio-correct summary: compound the per-year equal-weight basket returns
    # (yearly_metric.total_return is the mean of that year's trades), NOT every
    # individual trade sequentially. Hit/avg-win/avg-loss are per trade.
    yearly_returns = [ym["total_return"] for ym in yearly_metrics]
    summary = summarize_portfolio(yearly_returns, all_returns)
    computed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    # Honest bias check: survivorship passes only when the price archive
    # actually carries delisted tickers (auto-detected). The free Stooq bundle
    # does not, so this stays False for it and flips True once real (or test)
    # delisted history is present.
    bias_check = build_bias_check(
        source_name,
        uses_point_in_time_fundamentals=total_point_in_time > 0,
        delisted_coverage=delisted_coverage,
        uses_fundamentals=uses_fundamentals,
    )
    data_sources = [{"source_name": source_name, "source_as_of": computed_at}]
    if uses_fundamentals:
        data_sources.append({"source_name": "sec_edgar_companyfacts", "source_as_of": computed_at})

    return {
        "id": f"{strategy_slug}_{source_name}_{start.isoformat()}_{end.isoformat()}",
        "strategy_slug": strategy_slug,
        "data_window_start": start.isoformat(),
        "data_window_end": end.isoformat(),
        "data_sources": data_sources,
        "universe_size": int(len(by_ticker.groups)),
        "candidate_pool_universe": len(union),
        "fundamentals_universe": len(union) if uses_fundamentals else 0,
        "bias_check": bias_check,
        "coverage_notes": coverage_notes,
        "yearly_metrics": yearly_metrics,
        "summary_metrics": summary,
        "code_version": "local",
        "computed_at": computed_at,
        # Annual rebalanced-portfolio equity curve (one step per year), compounding
        # the per-year equal-weight basket returns — not sequential per-trade.
        "equity_curve": [
            {"step": idx + 1, "equity": float(value)}
            for idx, value in enumerate((1 + pd.Series(yearly_returns, dtype=float)).cumprod().tolist())
        ],
    }


def write_artifacts(result: dict) -> None:
    slug = result["strategy_slug"]
    data_dir = ROOT / "backend" / "data" / "backtests"
    artifact_dir = ROOT / "backend" / "backtests" / slug
    data_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    serializable = {key: value for key, value in result.items() if key != "equity_curve"}
    (data_dir / f"{slug}.json").write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    (artifact_dir / "summary_metrics.json").write_text(json.dumps(result["summary_metrics"], indent=2), encoding="utf-8")
    (artifact_dir / "yearly_metrics.json").write_text(json.dumps(result["yearly_metrics"], indent=2), encoding="utf-8")
    (artifact_dir / "bias_check.md").write_text(
        to_markdown(slug, result["data_window_start"], result["data_window_end"], result["bias_check"]),
        encoding="utf-8",
    )
    pd.DataFrame(result["equity_curve"]).to_parquet(artifact_dir / "equity_curve.parquet", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a reproducible local strategy backtest.")
    parser.add_argument("--strategy", default="midterm_52w_high_momentum")
    parser.add_argument("--start", default="2008-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--tickers", help="Optional comma-separated ticker subset (default: full Stooq universe).")
    args = parser.parse_args()

    result = run_backtest(
        args.strategy,
        date.fromisoformat(args.start),
        date.fromisoformat(args.end),
        _tickers(args.tickers) if args.tickers else None,
    )
    write_artifacts(result)
    print(f"Wrote backtest artifacts for {args.strategy}")


if __name__ == "__main__":
    main()
