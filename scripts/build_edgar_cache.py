"""Fetch + cache SEC EDGAR companyfacts (slim) for compliant-universe names that
are missing their EDGAR cache, so the live screen's quality + asset-growth gates
have data for them (reduces the 'fundamentals missing' / 'asset-growth passed
through' data_notes). Names with no SEC filings (foreign ADRs, ETPs) get an empty
slim cache and remain without fundamentals — that's inherent, not fixable.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.backtests.runner import prefetch_fundamentals  # parallel + cached
from backend.src.screening.engine import _compliant_universe, clear_snapshot_caches
from backend.src.shariah.lookup import normalize_shariah_overrides

EDGAR_CACHE = ROOT / "backend" / "data" / "edgar_cache"
DEFAULT_SOURCES = ["spus_holdings", "spwo_holdings", "spre_holdings", "spte_holdings", "halal_terminal"]


def main() -> None:
    ov = normalize_shariah_overrides({"active_sources": DEFAULT_SOURCES})
    universe = _compliant_universe(ov)
    missing = [t for t in universe if not (EDGAR_CACHE / f"{t}.json").exists()]
    print(f"Compliant universe: {len(universe)} | missing EDGAR cache: {len(missing)}")
    if not missing:
        print("Nothing to fetch.")
        return

    # get_slim_facts (called inside prefetch_fundamentals) writes each ticker's
    # slim companyfacts to backend/data/edgar_cache/<TICKER>.json.
    facts, _sectors = prefetch_fundamentals(missing)

    now_present = sum(1 for t in missing if (EDGAR_CACHE / f"{t}.json").exists())
    non_empty = sum(
        1 for t in missing
        if (facts.get(t) or {}).get("facts", {}).get("us-gaap")
    )
    print(f"Fetched {now_present}/{len(missing)} cache files; {non_empty} have us-gaap facts "
          f"({len(missing) - non_empty} are foreign/no-SEC-filings -> stay without fundamentals)")
    clear_snapshot_caches()
    print("Cleared snapshot caches — re-run the screen to pick up the new fundamentals.")


if __name__ == "__main__":
    main()
