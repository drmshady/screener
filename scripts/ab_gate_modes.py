"""A/B backtest: HARD (every gate filters) vs TIERED (only proximity hard; the
rest warn + rank) for the midterm strategy. Tests Decision 7 / the operator's
report instead of assuming it. Loads prices once; runs both modes on the same
data; prints a comparison. Does NOT overwrite the committed artifact.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.backtests.runner import load_consolidated_prices, run_backtest
from backend.src import strategies as _strategies  # noqa: F401

START, END = date(2008, 1, 1), date(2024, 12, 31)


def main() -> None:
    prices = load_consolidated_prices(START, END)
    if prices is None:
        raise SystemExit("No consolidated Stooq prices.")
    rows = []
    for mode in ("hard", "tiered"):
        os.environ["SCREENER_GATE_MODE"] = mode
        r = run_backtest("midterm_52w_high_momentum", START, END, prices=prices.copy())
        s = r["summary_metrics"]
        trades = sum(y["trades"] for y in r["yearly_metrics"])
        pos_yrs = sum(1 for y in r["yearly_metrics"] if y["trades"] and y["total_return"] > 0)
        tot_yrs = sum(1 for y in r["yearly_metrics"] if y["trades"])
        rows.append((mode, s, trades, pos_yrs, tot_yrs))
        print(f"\n=== {mode.upper()} ===")
        print(f"total_return={s['total_return']*100:+.1f}%  hit={s['hit_rate']*100:.0f}%  "
              f"avg_win={s['avg_win']*100:.1f}%  avg_loss=-{s['avg_loss']*100:.1f}%  "
              f"maxDD={s['max_drawdown']*100:.0f}%  trades={trades}  +years={pos_yrs}/{tot_yrs}")

    print("\n=== VERDICT ===")
    h, t = rows[0][1], rows[1][1]
    print(f"return:   hard {h['total_return']*100:+.1f}%  vs  tiered {t['total_return']*100:+.1f}%")
    print(f"hit:      hard {h['hit_rate']*100:.0f}%  vs  tiered {t['hit_rate']*100:.0f}%")
    print(f"avg_loss: hard -{h['avg_loss']*100:.1f}%  vs  tiered -{t['avg_loss']*100:.1f}%")
    print(f"maxDD:    hard {h['max_drawdown']*100:.0f}%  vs  tiered {t['max_drawdown']*100:.0f}%")


if __name__ == "__main__":
    main()
