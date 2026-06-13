"""Enhanced strategy-comparison study: mid-term vs short-term on Stooq deep history.

Improvements over the annual T049 runner, for a *fair* cross-timeframe comparison:

- Signal frequency matched to each strategy's holding period: monthly rebalances
  for short-term strategies, quarterly for mid-term (annual snapshots starve a
  5-30-day strategy of trades and make its statistics meaningless).
- Realistic execution: entry at the NEXT day's open after the signal, exits
  honored bar-by-bar (initial stop, take-profit, trailing exit), and a 0.20%
  round-trip cost deducted from every trade.
- Exits faithful to each strategy's documented design:
    midterm_52w_high_momentum  -> trailing 200-day-SMA exit (Faber), 3R target
    shortterm_minervini_vcp    -> fixed stop at contraction low, 2.5R target
    shortterm_atr_breakout     -> initial 1.5xATR stop, Chandelier trailing exit
- Optional regime master switch (Faber 2007 / tasks.md T108a): when SPY closes
  below its 200-day SMA, no new entries are taken. Each strategy runs with the
  gate OFF and ON so its effect is measured, not assumed.
- Pre-registered validity criteria (committed before results are computed):
  a strategy is "valid" when trades >= 50, expectancy after costs > 0, and the
  t-statistic of mean trade return >= 2.0; strategies are ranked by t-stat.

Strategy *rules are unchanged* — tuning rules against the same history used to
validate them would be data snooping.

Caveat shared by every variant: the free Stooq bundle has no delisted tickers,
so absolute results are survivor-inflated. The *comparison* is internally fair
because all strategies face the same bias.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.src.backtests.runner import (  # noqa: E402
    load_consolidated_prices,
    precompute_features,
    prefetch_fundamentals,
)
from backend.src.data.fundamentals import FundamentalsLoader  # noqa: E402
from backend.src.strategies._registry import registry  # noqa: E402
from backend.src.strategies import (  # noqa: E402,F401
    midterm_52w_high_momentum,
    shortterm_atr_breakout,
    shortterm_minervini_vcp,
)

COST_ROUNDTRIP = 0.002  # 0.10% per side
TOP_N = 5
MIN_PRICE = 5.0
MIN_ADV_20D = 1_000_000.0

SPEC: dict[str, dict[str, Any]] = {
    "midterm_52w_high_momentum": {"freq": "Q", "horizon_bars": 126, "uses_fundamentals": True},
    "shortterm_minervini_vcp": {"freq": "M", "horizon_bars": 21, "uses_fundamentals": False},
    "shortterm_atr_breakout": {"freq": "M", "horizon_bars": 15, "uses_fundamentals": False},
}

OUT_DIR = ROOT / "backend" / "backtests" / "comparison"


# --------------------------------------------------------------------------- #
# Features and calendar
# --------------------------------------------------------------------------- #
def add_extra_features(prices: pd.DataFrame) -> pd.DataFrame:
    g = prices.groupby("ticker", sort=False)
    prev_close = g["close"].shift(1)
    tr = pd.concat(
        [
            prices["high"] - prices["low"],
            (prices["high"] - prev_close).abs(),
            (prices["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    prices["atr_14"] = tr.groupby(prices["ticker"], sort=False).transform(
        lambda s: s.ewm(alpha=1 / 14, adjust=False).mean()
    )
    prices["chandelier_exit"] = (
        g["high"].transform(lambda s: s.rolling(22, min_periods=22).max()) - 3.0 * prices["atr_14"]
    )
    prices["ret_12_1"] = g["close"].transform(lambda s: s.shift(21) / s.shift(252) - 1.0)
    return prices


def rebalance_dates(trading_days: pd.DatetimeIndex, start: date, end: date, freq: str) -> list[pd.Timestamp]:
    days = trading_days[(trading_days >= pd.Timestamp(start)) & (trading_days <= pd.Timestamp(end))]
    frame = pd.DataFrame({"d": days})
    month_ends = frame.groupby([frame["d"].dt.year, frame["d"].dt.month])["d"].max().tolist()
    if freq == "M":
        return month_ends
    return [d for d in month_ends if d.month in (1, 4, 7, 10)]


def load_spy_regime() -> tuple[np.ndarray, np.ndarray] | None:
    """SPY (close > 200-day SMA) regime series from the Stooq ETF archive."""
    matches = glob.glob(str(ROOT / "backend" / "data" / "prices" / "stooq" / "**" / "spy.us.txt"), recursive=True)
    if not matches:
        return None
    df = pd.read_csv(matches[0])
    df.columns = [c.strip("<>").lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df = df.sort_values("date")
    sma = df["close"].rolling(200, min_periods=200).mean()
    ok = (df["close"] > sma).fillna(False).to_numpy()
    return df["date"].to_numpy(dtype="datetime64[ns]"), ok


def regime_allows(spy: tuple[np.ndarray, np.ndarray] | None, when: pd.Timestamp) -> bool:
    if spy is None:
        return True
    dates, ok = spy
    idx = np.searchsorted(dates, np.datetime64(when), side="right") - 1
    return bool(ok[idx]) if idx >= 0 else True


# --------------------------------------------------------------------------- #
# Candidate pools (vectorized, on the exact-rebalance-date panel)
# --------------------------------------------------------------------------- #
def pool_mask(panel: pd.DataFrame, slug: str) -> pd.Series:
    base = (
        (panel["close"] >= MIN_PRICE)
        & (panel["adv20"] >= MIN_ADV_20D)
        & (panel["n_obs"] >= 252)
        & panel["sma_200"].notna()
    )
    if slug == "midterm_52w_high_momentum":
        dist = (panel["close_high_252"] - panel["close"]) / panel["close"]
        return base & panel["close_high_252"].notna() & (dist <= 0.05) & (panel["close"] > panel["sma_200"])
    if slug == "shortterm_minervini_vcp":
        needed = ["breakout_high_50", "contraction_low_20", "adr_ratio_20_20", "volume_ratio_50", "sma_50", "sma_150", "sma_200_20d_ago"]
        ok = base
        for col in needed:
            ok = ok & panel[col].notna()
        return (
            ok
            & (panel["close"] >= panel["breakout_high_50"])
            & (panel["adr_ratio_20_20"] <= 0.9)
            & (panel["volume_ratio_50"] >= 1.0)
            & (panel["close"] > panel["sma_200"])
            & (panel["sma_200"] > panel["sma_200_20d_ago"])
        )
    if slug == "shortterm_atr_breakout":
        return (
            base
            & panel["breakout_high_20"].notna()
            & panel["sma_200_20d_ago"].notna()
            & (panel["close"] >= panel["breakout_high_20"])
            & (panel["close"] > panel["sma_200"])
            & (panel["sma_200"] > panel["sma_200_20d_ago"])
        )
    return base


SNAPSHOT_RENAMES = {"close_high_252": "52w_high", "ret_12_1": "return_12_1", "atr_14": "atr"}


def build_snapshot(
    pool_rows: pd.DataFrame,
    as_of: pd.Timestamp,
    slug: str,
    facts: dict[str, Any],
    sectors: dict[str, str],
    close_arrays: dict[str, tuple[np.ndarray, np.ndarray]],
    loader: FundamentalsLoader,
) -> pd.DataFrame:
    snap = pool_rows.rename(columns=SNAPSHOT_RENAMES).copy()
    snap["name"] = snap["ticker"]
    snap["sector"] = snap["ticker"].map(sectors).fillna("Unclassified")
    if SPEC[slug]["uses_fundamentals"]:
        quality = {
            t: loader.quality_metrics_as_of(t, as_of.date(), payload=facts.get(t) or {"facts": {"us-gaap": {}}})
            for t in snap["ticker"]
        }
        snap["fcf_ttm"] = snap["ticker"].map(lambda t: quality[t]["fcf_ttm"])
        snap["debt_to_equity"] = snap["ticker"].map(lambda t: quality[t]["debt_to_equity"])
        snap["gp_to_assets"] = snap["ticker"].map(lambda t: quality[t]["gp_to_assets"])
        returns_col = []
        for t in snap["ticker"]:
            dates, closes = close_arrays[t]
            hi = np.searchsorted(dates, np.datetime64(as_of), side="right")
            window = closes[max(0, hi - 127) : hi]
            returns_col.append(pd.Series(window).pct_change().dropna())
        snap["daily_returns"] = returns_col
    return snap


# --------------------------------------------------------------------------- #
# Trade simulation
# --------------------------------------------------------------------------- #
def simulate_trade(
    arrays: dict[str, np.ndarray],
    signal: pd.Timestamp,
    slug: str,
    row: pd.Series,
) -> dict[str, Any] | None:
    dates = arrays["dates"]
    start_idx = int(np.searchsorted(dates, np.datetime64(signal), side="right"))
    if start_idx >= len(dates):
        return None
    fill = float(arrays["open"][start_idx])
    if not math.isfinite(fill) or fill <= 0:
        fill = float(arrays["close"][start_idx])
    if fill <= 0:
        return None

    horizon = SPEC[slug]["horizon_bars"]
    if slug == "midterm_52w_high_momentum":
        initial_stop = float(row["sma_200"])
        target = fill + 3.0 * max(fill - initial_stop, 0.0) if initial_stop < fill else math.inf
    elif slug == "shortterm_minervini_vcp":
        initial_stop = float(row["contraction_low_20"])
        target = fill + 2.5 * max(fill - initial_stop, 0.0)
    else:
        atr = float(row["atr"])
        initial_stop = fill - 1.5 * atr
        target = fill + max(fill - float(row["chandelier_exit"]), atr)

    exit_px, reason = None, "time"
    last_idx = min(start_idx + horizon, len(dates) - 1)
    for i in range(start_idx, last_idx + 1):
        op, hi_, lo, cl = (float(arrays[k][i]) for k in ("open", "high", "low", "close"))
        if op <= initial_stop:
            exit_px, reason = op, "gap_stop"
            break
        if lo <= initial_stop:
            exit_px, reason = initial_stop, "stop"
            break
        if math.isfinite(target) and hi_ >= target:
            exit_px, reason = target, "target"
            break
        if slug == "midterm_52w_high_momentum":
            sma = float(arrays["sma_200"][i])
            if math.isfinite(sma) and cl < sma:
                exit_px, reason = cl, "trail_sma200"
                break
        elif slug == "shortterm_atr_breakout":
            ch = float(arrays["chandelier_exit"][i])
            if math.isfinite(ch) and cl < ch:
                exit_px, reason = cl, "trail_chandelier"
                break
    if exit_px is None:
        exit_px = float(arrays["close"][last_idx])
    gross = exit_px / fill - 1.0
    return {"gross": gross, "net": gross - COST_ROUNDTRIP, "reason": reason, "ticker": row["ticker"], "date": str(signal.date())}


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {"trades": 0}
    net = pd.Series([t["net"] for t in trades], dtype=float)
    wins, losses = net[net > 0], net[net <= 0]
    by_batch = pd.DataFrame(trades).groupby("date")["net"].mean().sort_index()
    equity = (1 + by_batch).cumprod()
    max_dd = float((1 - equity / equity.cummax()).max())
    years = pd.DataFrame(trades)
    years["year"] = years["date"].str[:4]
    yearly = years.groupby("year")["net"].agg(["mean", "count"])
    t_stat = float(net.mean() / (net.std(ddof=1) / math.sqrt(len(net)))) if len(net) > 1 and net.std(ddof=1) > 0 else 0.0
    return {
        "trades": int(len(net)),
        "hit_rate": float((net > 0).mean()),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(abs(losses.mean())) if len(losses) else 0.0,
        "expectancy": float(net.mean()),
        "profit_factor": float(wins.sum() / abs(losses.sum())) if losses.sum() != 0 else float("inf"),
        "t_stat": t_stat,
        "positive_year_fraction": float((yearly["mean"] > 0).mean()),
        "active_years": int(len(yearly)),
        "max_drawdown_batched": max_dd,
        "yearly": {idx: {"mean_net": float(r["mean"]), "trades": int(r["count"])} for idx, r in yearly.iterrows()},
    }


def is_valid(m: dict[str, Any]) -> bool:
    return m.get("trades", 0) >= 50 and m.get("expectancy", 0) > 0 and m.get("t_stat", 0) >= 2.0


# --------------------------------------------------------------------------- #
# Study driver
# --------------------------------------------------------------------------- #
def run_study(start: date, end: date) -> dict[str, Any]:
    prices = load_consolidated_prices(start, end)
    if prices is None:
        raise SystemExit("No consolidated Stooq parquet found; run scripts/build_stooq_parquet.py first.")
    print(f"Loaded {len(prices)} bars for {prices['ticker'].nunique()} tickers")
    prices = precompute_features(prices)
    prices = add_extra_features(prices)
    print("Features ready")

    trading_days = pd.DatetimeIndex(np.sort(prices["as_of_date"].unique()))
    dates_by_freq = {
        "M": rebalance_dates(trading_days, start, end, "M"),
        "Q": rebalance_dates(trading_days, start, end, "Q"),
    }
    all_dates = sorted({d for ds in dates_by_freq.values() for d in ds})
    panel = prices[prices["as_of_date"].isin(all_dates)]

    spy = load_spy_regime()
    print(f"Regime gate source: {'SPY 200-SMA' if spy else 'UNAVAILABLE (gate disabled)'}")

    by_ticker = prices.groupby("ticker", sort=False)
    sim_cache: dict[str, dict[str, np.ndarray]] = {}

    def sim_arrays(ticker: str) -> dict[str, np.ndarray]:
        if ticker not in sim_cache:
            grp = by_ticker.get_group(ticker)
            sim_cache[ticker] = {
                "dates": grp["as_of_date"].to_numpy(dtype="datetime64[ns]"),
                "open": grp["open"].to_numpy(dtype=float),
                "high": grp["high"].to_numpy(dtype=float),
                "low": grp["low"].to_numpy(dtype=float),
                "close": grp["close"].to_numpy(dtype=float),
                "sma_200": grp["sma_200"].to_numpy(dtype=float),
                "chandelier_exit": grp["chandelier_exit"].to_numpy(dtype=float),
            }
        return sim_cache[ticker]

    close_arrays = {
        t: (g["as_of_date"].to_numpy(dtype="datetime64[ns]"), g["close"].to_numpy(dtype=float))
        for t, g in by_ticker
    }

    loader = FundamentalsLoader()
    results: dict[str, Any] = {}
    for slug, spec in SPEC.items():
        strategy = registry.get(slug)
        rebal = dates_by_freq[spec["freq"]]
        pools = {d: panel[(panel["as_of_date"] == d) & pool_mask(panel[panel["as_of_date"] == d], slug)] for d in rebal}

        facts: dict[str, Any] = {}
        sectors: dict[str, str] = {}
        if spec["uses_fundamentals"]:
            union = sorted({t for p in pools.values() for t in p["ticker"]})
            print(f"{slug}: fundamentals union {len(union)} tickers")
            facts, sectors = prefetch_fundamentals(union)

        for variant in ("baseline", "regime_gated"):
            trades: list[dict[str, Any]] = []
            skipped_by_gate = 0
            for d in rebal:
                if variant == "regime_gated" and not regime_allows(spy, d):
                    skipped_by_gate += 1
                    continue
                pool = pools[d]
                if pool.empty:
                    continue
                snap = build_snapshot(pool, d, slug, facts, sectors, close_arrays, loader)
                cands = strategy.rules(snap)
                if cands.empty or "score" not in cands.columns:
                    continue
                cands = cands.sort_values(["score", "ticker"], ascending=[False, True]).head(TOP_N)
                for _, row in cands.iterrows():
                    trade = simulate_trade(sim_arrays(row["ticker"]), d, slug, row)
                    if trade is not None:
                        trades.append(trade)
            m = metrics(trades)
            m["rebalances"] = len(rebal)
            m["skipped_by_regime_gate"] = skipped_by_gate
            m["valid"] = is_valid(m)
            results[f"{slug}::{variant}"] = m
            print(
                f"{slug} [{variant}]: trades={m.get('trades', 0)} hit={m.get('hit_rate', 0):.2f} "
                f"exp={m.get('expectancy', 0):.4f} t={m.get('t_stat', 0):.2f} valid={m['valid']}"
            )

    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "cost_roundtrip": COST_ROUNDTRIP,
        "top_n": TOP_N,
        "criteria": "valid iff trades>=50 and expectancy>0 and t_stat>=2.0; ranked by t_stat",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }


def write_report(study: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "comparison.json").write_text(json.dumps(study, indent=2), encoding="utf-8")
    lines = [
        "# Strategy Comparison Study",
        "",
        f"Window: {study['window']['start']} to {study['window']['end']}. "
        f"Costs: {study['cost_roundtrip']*100:.2f}% round-trip. Top {study['top_n']} per rebalance.",
        "",
        f"Validity criteria (pre-registered): {study['criteria']}",
        "",
        "| strategy | variant | trades | hit | avg win | avg loss | expectancy | PF | t-stat | +yrs | maxDD | valid |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    ranked = sorted(study["results"].items(), key=lambda kv: kv[1].get("t_stat", 0), reverse=True)
    for key, m in ranked:
        slug, variant = key.split("::")
        if m.get("trades", 0) == 0:
            lines.append(f"| {slug} | {variant} | 0 | - | - | - | - | - | - | - | - | no |")
            continue
        lines.append(
            f"| {slug} | {variant} | {m['trades']} | {m['hit_rate']:.0%} | {m['avg_win']:.1%} | "
            f"{m['avg_loss']:.1%} | {m['expectancy']:.2%} | {m['profit_factor']:.2f} | {m['t_stat']:.2f} | "
            f"{m['positive_year_fraction']:.0%} | {m['max_drawdown_batched']:.0%} | {'YES' if m['valid'] else 'no'} |"
        )
    lines += [
        "",
        "Survivorship caveat: the free Stooq bundle has no delisted tickers; absolute numbers",
        "are survivor-inflated for every variant. The comparison is internally fair.",
        "",
    ]
    (OUT_DIR / "comparison_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_DIR / 'comparison_report.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enhanced strategy comparison study")
    parser.add_argument("--start", default="2008-01-01")
    parser.add_argument("--end", default="2024-12-31")
    args = parser.parse_args()
    study = run_study(date.fromisoformat(args.start), date.fromisoformat(args.end))
    write_report(study)


if __name__ == "__main__":
    main()
