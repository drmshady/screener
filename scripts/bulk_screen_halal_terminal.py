"""T126: bulk-classify the full Stooq US universe via Halal Terminal.

Requires HALAL_TERMINAL_API_KEY in the environment. Resumable — rerun to
continue; already-screened symbols are read from data/halal_terminal_cache/.

Usage:
    set HALAL_TERMINAL_API_KEY=...           # PowerShell: $env:HALAL_TERMINAL_API_KEY="..."
    py -3.12 scripts\\bulk_screen_halal_terminal.py [--max N] [--tickers AAPL,MSFT]
"""
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.data.shariah_halal_terminal import bulk_screen_universe

STOOQ_PARQUET = ROOT / "backend" / "data" / "prices" / "stooq_parquet"


def stooq_universe() -> list[str]:
    parts = glob.glob(str(STOOQ_PARQUET / "part-*.parquet"))
    if not parts:
        return []
    frames = [pd.read_parquet(p, columns=["ticker"]) for p in parts]
    return sorted(pd.concat(frames)["ticker"].astype(str).unique().tolist())


def liquid_universe(min_price: float = 5.0, min_adv_20d: float = 1_000_000.0) -> list[str]:
    """Names passing the liquidity gate as of the latest Stooq bar (price + 20d ADV)."""
    parts = glob.glob(str(STOOQ_PARQUET / "part-*.parquet"))
    if not parts:
        return []
    df = pd.concat([pd.read_parquet(p, columns=["ticker", "as_of_date", "close", "volume"]) for p in parts])
    df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    cutoff = df["as_of_date"].max() - pd.Timedelta(days=45)
    df = df[df["as_of_date"] >= cutoff].sort_values("as_of_date")
    keep: list[str] = []
    for ticker, g in df.groupby("ticker", sort=False):
        tail = g.tail(20)
        if tail.empty:
            continue
        last_close = float(tail["close"].iloc[-1])
        adv = float((tail["close"] * tail["volume"]).mean())
        if last_close >= min_price and adv >= min_adv_20d:
            keep.append(str(ticker))
    return sorted(keep)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk Halal Terminal classification of the US universe")
    parser.add_argument("--max", type=int, default=None, help="Cap symbols screened this run")
    parser.add_argument("--tickers", help="Comma-separated subset (default: full Stooq universe)")
    parser.add_argument("--liquid", action="store_true", help="Only liquid names (price>=$5, ADV20>=$1M)")
    parser.add_argument("--sleep", type=float, default=0.25, help="Seconds between live calls")
    args = parser.parse_args()

    if args.tickers:
        universe = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    elif args.liquid:
        universe = liquid_universe()
    else:
        universe = stooq_universe()
    if not universe:
        raise SystemExit("No universe found. Build the Stooq parquet first or pass --tickers.")

    print(f"Bulk-screening {len(universe)} symbols via Halal Terminal...")
    stats = bulk_screen_universe(universe, rate_limit_sleep=args.sleep, max_symbols=args.max)
    print(f"Done: {stats}")


if __name__ == "__main__":
    main()
