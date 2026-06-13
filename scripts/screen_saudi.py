"""Phase 16 feasibility test (T172): run the midterm strategy on the Saudi
(Tadawul) universe via yfinance `.SR`, end to end, and print findings.

This reuses the entire existing pipeline: passing `parameters.tickers` routes
run_strategy through the yfinance snapshot path (prices + profiles), so no
engine fork is needed. Thresholds are SAR-calibrated (Saudi prices are in SAR,
not USD). Regime gate is OFF (the regime model is SPY/US-based; TASI regime is
future work). First run fetches ~40 names x 650d from yfinance (slow); reruns
read the warm store.

Usage:
    py -3.12 scripts/screen_saudi.py [--halal] [--min-price 10] [--min-adv 3000000]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.data.saudi_universe import saudi_universe
from backend.src.data.shariah_saudi import SAUDI_SOURCE_NAME, seed_saudi_all_compliant
from backend.src.screening.engine import run_strategy
from backend.src import strategies as _strategies  # noqa: F401 register strategies


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the midterm strategy on the Saudi universe (test)")
    parser.add_argument("--strategy", default="midterm_52w_high_momentum")
    parser.add_argument("--halal", action="store_true", help="Seed + apply the provisional all-compliant Saudi source")
    parser.add_argument("--min-price", type=float, default=10.0, help="Min price in SAR (default 10)")
    parser.add_argument("--min-adv", type=float, default=3_000_000.0, help="Min 20d avg dollar(SAR) volume (default 3M SAR)")
    args = parser.parse_args()

    universe = saudi_universe()
    print(f"Saudi universe: {len(universe)} names (.SR). SAR thresholds: price>={args.min_price}, ADV20>={args.min_adv:,.0f}")

    filters = {"exclude_earnings_within_days": 0, "shariah_only": bool(args.halal)}
    shariah_overrides = {}
    if args.halal:
        seeded = seed_saudi_all_compliant()
        print(f"Seeded {seeded} provisional Saudi compliance rows (TEST ONLY, not a ruling)")
        shariah_overrides = {"active_sources": [SAUDI_SOURCE_NAME]}

    result = run_strategy(
        args.strategy,
        parameters={
            "tickers": universe,
            "liquidity_min_price": args.min_price,
            "liquidity_min_avg_dollar_volume_20d": args.min_adv,
            "regime_gate": False,        # SPY-based regime doesn't apply to TASI
            "refresh_events": False,     # US-only events pipeline
        },
        filters=filters,
        shariah_overrides=shariah_overrides,
    )

    print(f"\ndata_as_of: {result.data_as_of}  |  candidates: {result.candidate_count}")
    if result.data_notes:
        print("data_notes:")
        for n in result.data_notes:
            print(f"  - {n}")
    print("\nCandidates (prices in SAR):")
    for c in result.candidates:
        print(f"  {c.ticker:9} {c.sector:22} entry={c.entry} stop={c.stop_loss} tighter={c.tighter_stop_loss} target={c.take_profit}")
        print(f"            reason: {c.reason}")
    if not result.candidates:
        print("  (none — see data_notes above for why)")


if __name__ == "__main__":
    main()
