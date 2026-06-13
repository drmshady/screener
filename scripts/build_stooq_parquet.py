"""Consolidate the extracted Stooq US daily-stock text files into a fast parquet
dataset for backtesting. Common equities only (excludes the ETF folders).

Reads backend/data/prices/stooq/**/*stocks*/**/<ticker>.us.txt and writes
backend/data/prices/stooq_parquet/part-*.parquet with columns:
ticker, as_of_date, open, high, low, close, volume — filtered to >= START_DATE.
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STOOQ_GLOB = str(ROOT / "backend" / "data" / "prices" / "stooq" / "**" / "*stocks*" / "**" / "*.us.txt")
OUT_DIR = ROOT / "backend" / "data" / "prices" / "stooq_parquet"
START_DATE = pd.Timestamp("2006-01-01")
BATCH = 500


def _read_one(path: str) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(
            path,
            usecols=["<DATE>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>", "<VOL>"],
        )
    except Exception:
        return None
    if df.empty:
        return None
    df.columns = ["as_of_date", "open", "high", "low", "close", "volume"]
    df["as_of_date"] = pd.to_datetime(df["as_of_date"], format="%Y%m%d", errors="coerce")
    df = df[df["as_of_date"] >= START_DATE]
    if df.empty:
        return None
    ticker = os.path.basename(path)[: -len(".us.txt")].upper()
    df.insert(0, "ticker", ticker)
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
    return df.dropna(subset=["close"])


def main() -> None:
    files = glob.glob(STOOQ_GLOB, recursive=True)
    print(f"Found {len(files)} Stooq stock files")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("part-*.parquet"):
        old.unlink()

    batch: list[pd.DataFrame] = []
    part = 0
    total_rows = 0
    for i, path in enumerate(files, start=1):
        frame = _read_one(path)
        if frame is not None:
            batch.append(frame)
        if len(batch) >= BATCH or i == len(files):
            if batch:
                out = pd.concat(batch, ignore_index=True)
                out.to_parquet(OUT_DIR / f"part-{part:04d}.parquet", index=False)
                total_rows += len(out)
                part += 1
                batch = []
            print(f"  processed {i}/{len(files)} files, {total_rows} rows, {part} parts")
    print(f"Done: {total_rows} rows across {part} parquet parts in {OUT_DIR}")


if __name__ == "__main__":
    main()
