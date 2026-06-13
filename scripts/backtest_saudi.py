"""Phase 16 / T172: backtest a PRICE-ONLY strategy on Saudi (Tadawul) history
from the Kaggle parquet (build_saudi_parquet.py first). The midterm strategy is
fundamentals-gated and we have no Saudi point-in-time fundamentals, so this
defaults to shortterm_atr_breakout (price/trend/breakout only).

Does NOT overwrite the US backtest artifacts — it prints the summary and writes
to a `_saudi`-suffixed file only.

Usage: py -3.12 scripts/backtest_saudi.py [--strategy shortterm_atr_breakout] [--start 2005-01-01] [--end 2020-04-16]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.backtests.runner import run_backtest
from backend.src import strategies as _strategies  # noqa: F401 register strategies

SAUDI_PARQUET = ROOT / "backend" / "data" / "prices" / "saudi_parquet"
OUT_DIR = ROOT / "backend" / "data" / "backtests"


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest a price-only strategy on Saudi history")
    parser.add_argument("--strategy", default="shortterm_atr_breakout")
    parser.add_argument("--start", default="2005-01-01")
    parser.add_argument("--end", default="2020-04-16")
    args = parser.parse_args()

    parts = glob.glob(str(SAUDI_PARQUET / "part-*.parquet"))
    if not parts:
        raise SystemExit("No Saudi parquet — run scripts/build_saudi_parquet.py first.")
    prices = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    prices["as_of_date"] = pd.to_datetime(prices["as_of_date"])
    print(f"Saudi prices: {len(prices):,} bars, {prices['ticker'].nunique()} tickers, "
          f"{prices['as_of_date'].min().date()} -> {prices['as_of_date'].max().date()}")

    result = run_backtest(
        args.strategy,
        date.fromisoformat(args.start),
        date.fromisoformat(args.end),
        prices=prices,
    )
    s = result["summary_metrics"]
    print(f"\n=== {args.strategy} on SAUDI ({args.start} -> {args.end}) ===")
    print(f"total_return={s['total_return']*100:+.1f}%  hit={s['hit_rate']*100:.0f}%  "
          f"avg_win={s['avg_win']*100:.1f}%  avg_loss=-{s['avg_loss']*100:.1f}%  "
          f"maxDD={s['max_drawdown']*100:.0f}%  trades={int(s['turnover'])}")
    print("bias:", {k: v['passed'] for k, v in result['bias_check'].items()})
    print("per-year basket return:")
    for y in result["yearly_metrics"]:
        if y["trades"] > 0:
            print(f"  {y['year']}: trades={y['trades']:3} hit={y['hit_rate']:.2f} ret={y['total_return']:+.3f}")

    out_path = OUT_DIR / f"{args.strategy}_saudi.json"
    serializable = {k: v for k, v in result.items() if k != "equity_curve"}
    out_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path.name} (US artifacts untouched)")


if __name__ == "__main__":
    main()
