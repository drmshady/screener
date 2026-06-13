from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Any

import httpx

from .shariah_sources import DEFAULT_DB_PATH, DEFAULT_MANIFEST_PATH, replace_source_rows

SPUS_SOURCE_NAME = "spus_holdings"
SPUS_HOLDINGS_URL = (
    "https://www.sp-funds.com/wp-content/uploads/data/TidalFG_Holdings_SPUS.csv"
)


def fetch_spus_holdings(url: str = SPUS_HOLDINGS_URL) -> list[dict[str, Any]]:
    response = httpx.get(
        url,
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "screener-local-shariah-audit/1.0"},
    )
    response.raise_for_status()
    reader = csv.DictReader(StringIO(response.text.lstrip("\ufeff")))
    rows: list[dict[str, Any]] = []
    for raw in reader:
        ticker = (raw.get("StockTicker") or raw.get("Ticker") or "").strip().upper()
        if not ticker or ticker == "-":
            continue
        rows.append(
            {
                "ticker": ticker,
                "source_name": SPUS_SOURCE_NAME,
                "source_kind": "external",
                "source_as_of": raw.get("Date"),
                "source_url": url,
            }
        )
    if not rows:
        raise ValueError("SPUS holdings feed returned no ticker rows")
    return rows


def seed_spus_holdings(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
    url: str = SPUS_HOLDINGS_URL,
) -> int:
    rows = fetch_spus_holdings(url)
    return replace_source_rows(
        SPUS_SOURCE_NAME,
        rows,
        db_path=db_path,
        manifest_path=manifest_path,
        manifest_metadata={
            "display_name": "SPUS holdings",
            "refresh_interval_days": 7,
            "notes": "Official SP Funds SPUS holdings CSV. Membership is an ETF-holdings proxy, not a full halal universe.",
        },
    )


if __name__ == "__main__":
    count = seed_spus_holdings()
    print(f"Seeded {count} SPUS Shariah source rows")
