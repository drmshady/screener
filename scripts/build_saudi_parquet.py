"""Phase 16 / T171: convert the Kaggle Tadawul dataset (Tadawul_stcks.csv.zip in
the repo root) into a consolidated Saudi price parquet — the Saudi analogue of
the Stooq bundle — so strategies can be backtested on Saudi history (2001-2020,
incl. the 2008-2009 crisis the US EDGAR fundamentals couldn't reach).

Output: backend/data/prices/saudi_parquet/part-0.parquet with the standard
schema (ticker, as_of_date, open, high, low, close, volume). Numeric Tadawul
codes are mapped to the live `.SR` ticker format (e.g. 2222 -> 2222.SR).
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT / "Tadawul_stcks.csv.zip"
OUT_DIR = ROOT / "backend" / "data" / "prices" / "saudi_parquet"


def main() -> None:
    if not ZIP_PATH.exists():
        raise SystemExit(f"Kaggle file not found: {ZIP_PATH}")
    with zipfile.ZipFile(ZIP_PATH) as z:
        df = pd.read_csv(z.open(z.namelist()[0]))
    df.columns = [c.strip() for c in df.columns]  # 'volume_traded ' -> 'volume_traded'

    out = pd.DataFrame({
        "ticker": df["symbol"].astype(int).astype(str) + ".SR",
        "as_of_date": pd.to_datetime(df["date"], errors="coerce"),
        "open": pd.to_numeric(df["open"], errors="coerce"),
        "high": pd.to_numeric(df["high"], errors="coerce"),
        "low": pd.to_numeric(df["low"], errors="coerce"),
        "close": pd.to_numeric(df["close"], errors="coerce"),
        "volume": pd.to_numeric(df["volume_traded"], errors="coerce"),
    })
    out = out.dropna(subset=["as_of_date", "close"]).sort_values(["ticker", "as_of_date"])
    out = out.drop_duplicates(["ticker", "as_of_date"], keep="last").reset_index(drop=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_DIR / "part-0.parquet", index=False)
    print(
        f"Wrote {len(out):,} Saudi bars for {out['ticker'].nunique()} tickers "
        f"({out['as_of_date'].min().date()} -> {out['as_of_date'].max().date()}) to {OUT_DIR}"
    )


if __name__ == "__main__":
    main()
