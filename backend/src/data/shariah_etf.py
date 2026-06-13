"""Generic Shariah-ETF holdings loader (T124).

Each Shariah ETF's equity holdings are an issuer-certified compliant inclusion
list. This loader parses any holdings CSV into `shariah_sources` rows, so new
ETFs can be added by configuration. Seeds the SP Funds equity family (verified
available, same CSV schema as SPUS) by default.

Note: SPSK (sukuk/bonds) is intentionally excluded — it is not common equity.
HLAL/UMMA track FTSE USA Shariah (same index as SPUS) so they add ~no new
US-screenable names; they can still be added here via config if desired.
"""
from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Any

import httpx

from .shariah_sources import DEFAULT_DB_PATH, DEFAULT_MANIFEST_PATH, replace_source_rows

TICKER_COLUMNS = ("StockTicker", "Ticker", "Symbol", "Holding Ticker")
DATE_COLUMNS = ("Date", "As Of Date", "as_of_date")
_NON_EQUITY = {"-", "", "CASH", "USD", "CASH&OTHER", "CASH & OTHER", "MARGIN"}

SP_FUNDS_BASE = "https://www.sp-funds.com/wp-content/uploads/data/TidalFG_Holdings_{etf}.csv"

# source_name -> (display_name, url, notes)
ETF_SOURCES: dict[str, tuple[str, str, str]] = {
    "spwo_holdings": (
        "SP Funds S&P World (SPWO) holdings",
        SP_FUNDS_BASE.format(etf="SPWO"),
        "Issuer-certified Shariah ETF holdings (global; adds US-listed ADRs). ETF-holdings proxy, not a full halal universe.",
    ),
    "spre_holdings": (
        "SP Funds S&P Global REIT (SPRE) holdings",
        SP_FUNDS_BASE.format(etf="SPRE"),
        "Issuer-certified Shariah REIT ETF holdings. REIT compliance varies by methodology; SP Funds includes them.",
    ),
    "spte_holdings": (
        "SP Funds S&P Global Technology (SPTE) holdings",
        SP_FUNDS_BASE.format(etf="SPTE"),
        "Issuer-certified Shariah technology ETF holdings (largely overlaps SPUS).",
    ),
}


def parse_holdings_csv(
    text: str,
    source_name: str,
    url: str,
    *,
    ticker_columns: tuple[str, ...] = TICKER_COLUMNS,
    date_columns: tuple[str, ...] = DATE_COLUMNS,
) -> list[dict[str, Any]]:
    """Parse a holdings CSV into shariah_source rows (no network — unit-testable)."""
    reader = csv.DictReader(StringIO(text.lstrip("﻿")))
    rows: list[dict[str, Any]] = []
    for raw in reader:
        ticker = ""
        for col in ticker_columns:
            if raw.get(col):
                ticker = str(raw[col]).strip().upper()
                break
        if ticker.replace("/", ".") in _NON_EQUITY or ticker in _NON_EQUITY:
            continue
        as_of = ""
        for col in date_columns:
            if raw.get(col):
                as_of = raw[col]
                break
        rows.append(
            {
                "ticker": ticker,
                "source_name": source_name,
                "source_kind": "external",
                "source_as_of": as_of,
                "source_url": url,
            }
        )
    return rows


def fetch_etf_holdings(source_name: str, url: str) -> list[dict[str, Any]]:
    response = httpx.get(
        url, timeout=30, follow_redirects=True, headers={"User-Agent": "screener-local-shariah-audit/1.0"}
    )
    response.raise_for_status()
    rows = parse_holdings_csv(response.text, source_name, url)
    if not rows:
        raise ValueError(f"{source_name} holdings feed returned no ticker rows")
    return rows


def seed_etf_holdings(
    source_name: str,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
) -> int:
    if source_name not in ETF_SOURCES:
        raise KeyError(f"Unknown ETF source '{source_name}'. Known: {sorted(ETF_SOURCES)}")
    display_name, url, notes = ETF_SOURCES[source_name]
    rows = fetch_etf_holdings(source_name, url)
    return replace_source_rows(
        source_name,
        rows,
        db_path=db_path,
        manifest_path=manifest_path,
        manifest_metadata={"display_name": display_name, "refresh_interval_days": 7, "notes": notes},
    )


def seed_all_etf_holdings(
    *, db_path: Path | str = DEFAULT_DB_PATH, manifest_path: Path | str = DEFAULT_MANIFEST_PATH
) -> dict[str, int]:
    results: dict[str, int] = {}
    for source_name in ETF_SOURCES:
        try:
            results[source_name] = seed_etf_holdings(source_name, db_path=db_path, manifest_path=manifest_path)
        except Exception as exc:  # one bad feed must not abort the rest
            print(f"  {source_name}: FAILED ({exc})")
            results[source_name] = 0
    return results


if __name__ == "__main__":
    for name, count in seed_all_etf_holdings().items():
        print(f"Seeded {count} rows for {name}")
