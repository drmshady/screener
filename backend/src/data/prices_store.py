from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

PRICES_DIR = "backend/data/prices/parquet"


def _root(prices_dir: str | Path | None = None) -> Path:
    return Path(prices_dir or PRICES_DIR)


def _ensure_dir(prices_dir: str | Path | None = None) -> None:
    _root(prices_dir).mkdir(parents=True, exist_ok=True)


def _normalize_prices(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized["ticker"] = normalized["ticker"].astype(str).str.upper()
    normalized["as_of_date"] = pd.to_datetime(normalized["as_of_date"])
    if "source_as_of" in normalized:
        normalized["source_as_of"] = pd.to_datetime(
            normalized["source_as_of"], errors="coerce", utc=True
        )
    else:
        normalized["source_as_of"] = pd.Timestamp.utcnow()
    normalized["year"] = normalized["as_of_date"].dt.year
    return normalized


def save_prices(df: pd.DataFrame, prices_dir: str | Path | None = None) -> None:
    """
    Upsert OHLCV data to the partitioned Parquet store.

    Only partitions for years present in `df` are rewritten. Existing rows for
    other tickers in those same years are preserved, fixing the old
    delete-matching behavior that could erase unrelated tickers.
    """
    _ensure_dir(prices_dir)
    if df.empty:
        return

    root = _root(prices_dir)
    incoming = _normalize_prices(df)
    years = sorted(incoming["year"].dropna().astype(int).unique().tolist())
    existing = pd.DataFrame()
    if root.exists() and any((root / f"year={year}").exists() for year in years):
        try:
            existing = pd.read_parquet(
                root,
                engine="pyarrow",
                filters=[("year", "in", years)],
            )
        except Exception:
            existing = pd.DataFrame()
    if not existing.empty:
        existing = _normalize_prices(existing)

    merged = (
        pd.concat([existing, incoming], ignore_index=True)
        if not existing.empty
        else incoming
    )
    merged["_source_as_of_sort"] = pd.to_datetime(
        merged["source_as_of"], errors="coerce", utc=True
    )
    merged = merged.sort_values(["ticker", "as_of_date", "_source_as_of_sort"])
    merged = merged.drop_duplicates(["ticker", "as_of_date"], keep="last")
    merged = merged.drop(columns=["_source_as_of_sort"])
    merged = merged[merged["year"].isin(years)].copy()

    merged.to_parquet(
        root,
        partition_cols=["year"],
        engine="pyarrow",
        index=False,
        existing_data_behavior="delete_matching",
    )


def load_prices(
    tickers: Optional[list[str]] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    prices_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Load OHLCV data from the partitioned Parquet store."""
    root = _root(prices_dir)
    if not os.path.exists(root):
        return pd.DataFrame()
    if tickers is not None and len(tickers) == 0:
        return pd.DataFrame()

    filters = []
    if tickers:
        filters.append(("ticker", "in", [ticker.upper() for ticker in tickers]))
    if start_date:
        filters.append(("as_of_date", ">=", pd.Timestamp(start_date)))
    if end_date:
        filters.append(("as_of_date", "<=", pd.Timestamp(end_date)))

    try:
        return pd.read_parquet(
            root,
            engine="pyarrow",
            filters=filters if filters else None,
        )
    except Exception:
        return pd.DataFrame()


def load_last_dates(
    tickers: Iterable[str] | None = None,
    prices_dir: str | Path | None = None,
) -> dict[str, date]:
    """Return max stored bar date per ticker."""
    ticker_list = (
        [ticker.upper() for ticker in tickers] if tickers is not None else None
    )
    prices = load_prices(ticker_list, prices_dir=prices_dir)
    if prices.empty:
        return {}
    prices["as_of_date"] = pd.to_datetime(prices["as_of_date"])
    grouped = prices.groupby(prices["ticker"].astype(str).str.upper())[
        "as_of_date"
    ].max()
    return {
        str(ticker): pd.Timestamp(value).date() for ticker, value in grouped.items()
    }
