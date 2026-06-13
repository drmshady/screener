"""Generate a SAMPLE of synthetic *delisted* stocks in Stooq text format for
testing the survivorship-bias path (A1). Each ticker rises to a breakout, then
collapses and stops trading (the file simply ends) — exactly the shape a real
delisted/bankrupt name has, and exactly what the free Stooq bundle is missing.

Files are written to a SEPARATE folder so they never contaminate a real backtest:
    backend/data/prices/stooq_synthetic_delisted/data/daily/us/test stocks/

To test the full pipeline against them, point the consolidator/runner at this
folder (or copy the files into backend/data/prices/stooq/ if you explicitly want
them in the main archive), then rebuild the parquet and run the backtest. The
runner auto-detects delisted coverage and flips survivorship_bias to PASS.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "backend" / "data" / "prices" / "stooq_synthetic_delisted" / "data" / "daily" / "us" / "test stocks"

# (ticker, start, breakout_date, last_trading_date) — collapse begins after breakout.
SPECS = [
    ("ZOMBA", date(2014, 1, 2), date(2016, 1, 29), date(2016, 5, 13)),
    ("DEFNK", date(2013, 6, 3), date(2015, 7, 31), date(2015, 11, 20)),
    ("BUSTX", date(2012, 1, 3), date(2014, 2, 28), date(2014, 6, 30)),
]


def _series(start: date, breakout: date, last: date) -> pd.DataFrame:
    up = pd.bdate_range(start, breakout)
    closes_up = 18.0 * (1.0 + np.linspace(0.0, 1.7, len(up)))  # steady uptrend, new highs
    crash = pd.bdate_range(breakout + timedelta(days=1), last)
    n = len(crash)
    peak = float(closes_up[-1])
    decay = peak * (0.78 ** np.arange(min(n, 16)))
    tail = np.full(max(n - 16, 0), max(peak * 0.78 ** 16, 0.30))
    closes_crash = np.concatenate([decay, tail])[:n]
    dates = up.append(crash)
    close = np.concatenate([closes_up, closes_crash])
    return pd.DataFrame(
        {
            "date": [d.strftime("%Y%m%d") for d in dates],
            "open": np.round(np.concatenate([[close[0]], close[:-1]]), 4),
            "high": np.round(close, 4),
            "low": np.round(close * 0.97, 4),
            "close": np.round(close, 4),
            "vol": 200_000,
        }
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for ticker, start, breakout, last in SPECS:
        df = _series(start, breakout, last)
        lines = ["<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>"]
        for _, r in df.iterrows():
            lines.append(
                f"{ticker}.US,D,{r['date']},000000,{r['open']},{r['high']},{r['low']},{r['close']},{r['vol']},0"
            )
        path = OUT_DIR / f"{ticker.lower()}.us.txt"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {path}  ({len(df)} bars, {df['date'].iloc[0]}..{df['date'].iloc[-1]})")
    print(f"\nSample delisted files in: {OUT_DIR}")
    print("These end mid-history (delisting). Copy into backend/data/prices/stooq/ and rerun")
    print("build_stooq_parquet.py + runner.py to see survivorship_bias flip to PASS.")


if __name__ == "__main__":
    main()
