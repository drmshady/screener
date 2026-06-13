"""Repopulate the profile cache for the compliant universe so sectors are real
(yfinance) instead of 'Unclassified'. Needed after fixing fetch_profile, which
used to let an empty EDGAR sector overwrite the good yfinance one. Re-enables the
sector-breadth gate.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.data.profiles import refresh_profiles
from backend.src.screening.engine import _compliant_universe, clear_snapshot_caches
from backend.src.shariah.lookup import normalize_shariah_overrides

DEFAULT_SOURCES = ["spus_holdings", "spwo_holdings", "spre_holdings", "spte_holdings", "halal_terminal"]


def main() -> None:
    ov = normalize_shariah_overrides({"active_sources": DEFAULT_SOURCES})
    universe = _compliant_universe(ov)
    print(f"Refreshing profiles (sectors) for {len(universe)} compliant names...")
    profiles = refresh_profiles(universe)
    classified = sum(1 for p in profiles.values() if p.get("sector") not in (None, "Unclassified"))
    print(f"Done: {classified}/{len(universe)} now have a real sector "
          f"({len(universe) - classified} still Unclassified - yfinance had no sector)")
    clear_snapshot_caches()
    print("Cleared snapshot caches.")


if __name__ == "__main__":
    main()
