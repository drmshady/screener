"""A/B backtest: sector-strength (breadth) gate OFF vs ON at a few fractions.

Tests Decision 7's rebuilt sector-breadth gate (industry momentum: keep names
only in sectors where a high fraction of members are above their 200-day SMA)
instead of assuming it helps. The backtest now overlays the live yfinance sector
cache as a static map (see runner) so the gate can actually run historically.
Loads prices once; runs each fraction on the same data; prints a comparison.
Does NOT overwrite the committed artifact.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.backtests.runner import load_consolidated_prices, run_backtest
from backend.src.strategies import midterm_52w_high_momentum as midterm
from backend.src import strategies as _strategies  # noqa: F401

START, END = date(2008, 1, 1), date(2024, 12, 31)
FRACTIONS = [1.0, 0.67, 0.5]  # 1.0 = disabled (current default)


def main() -> None:
    prices = load_consolidated_prices(START, END)
    if prices is None:
        raise SystemExit("No consolidated Stooq prices.")
    original = midterm.PARAMETERS["sector_strength_top_fraction"].default
    rows = []
    try:
        for frac in FRACTIONS:
            midterm.PARAMETERS["sector_strength_top_fraction"].default = frac
            r = run_backtest("midterm_52w_high_momentum", START, END, prices=prices.copy())
            s = r["summary_metrics"]
            trades = sum(y["trades"] for y in r["yearly_metrics"])
            pos = sum(1 for y in r["yearly_metrics"] if y["trades"] and y["total_return"] > 0)
            tot = sum(1 for y in r["yearly_metrics"] if y["trades"])
            rows.append((frac, s, trades, pos, tot))
            label = "OFF" if not (0.0 < frac < 1.0) else f"top {int(frac*100)}%"
            print(f"\n=== sector gate {label} (fraction={frac}) ===")
            print(f"total_return={s['total_return']*100:+.1f}%  hit={s['hit_rate']*100:.0f}%  "
                  f"avg_win={s['avg_win']*100:.1f}%  avg_loss=-{s['avg_loss']*100:.1f}%  "
                  f"maxDD={s['max_drawdown']*100:.0f}%  trades={trades}  +years={pos}/{tot}")
    finally:
        midterm.PARAMETERS["sector_strength_top_fraction"].default = original

    print("\n=== VERDICT (vs OFF) ===")
    base = rows[0][1]
    for frac, s, trades, pos, tot in rows:
        if frac == 1.0:
            continue
        dr = (s["total_return"] - base["total_return"]) * 100
        dd = (s["max_drawdown"] - base["max_drawdown"]) * 100
        print(f"top {int(frac*100)}%:  return {s['total_return']*100:+.1f}% "
              f"({dr:+.1f} vs off)  maxDD {s['max_drawdown']*100:.0f}% ({dd:+.0f})  "
              f"trades {trades}  +years {pos}/{tot}")


if __name__ == "__main__":
    main()
