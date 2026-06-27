from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.data.prices import fetch_incremental_ohlcv
from backend.src.data.econ_calendar import seed_econ_calendar
from backend.src.data.prices_store import load_last_dates, load_prices, save_prices
from backend.src.data.profiles import refresh_profiles
from backend.src.data.shariah_etf import seed_all_etf_holdings
from backend.src.data.shariah_finispia import seed_finispia_export
from backend.src.data.shariah_halal_terminal import seed_halal_terminal_results
from backend.src.data.shariah_spus import seed_spus_holdings
from backend.src.lib.disclaimer import utc_now_iso
from backend.src.events.service import EventsService
from backend.src.screening.engine import (
    DEFAULT_SCREEN_TICKERS,
    _compliant_universe,
    run_strategy,
)
from backend.src.shariah.lookup import (
    KNOWN_CONFIGURABLE_SOURCES,
    normalize_shariah_overrides,
)
from backend.src import strategies as _strategies  # noqa: F401 - register strategies

MANIFEST_PATH = ROOT / "backend" / "data" / "manifest.json"


def _tickers(raw: str | None) -> list[str]:
    if not raw:
        return DEFAULT_SCREEN_TICKERS
    return sorted({part.strip().upper() for part in raw.split(",") if part.strip()})


def _update_manifest(row_count: int, tickers: list[str]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest = (
        json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if MANIFEST_PATH.exists()
        else {"sources": {}}
    )
    manifest.setdefault("sources", {})["yfinance"] = {
        "kind": "prices",
        "source_as_of": utc_now_iso(),
        "refresh_interval_days": 1,
        "source_url": "https://finance.yahoo.com",
        "last_row_count": row_count,
        "tickers": tickers,
        "last_bar_date_by_ticker": {
            ticker: last_date.isoformat()
            for ticker, last_date in load_last_dates(tickers).items()
        },
    }
    manifest.setdefault("sources", {})["ticker_profile_cache"] = {
        "kind": "fundamentals",
        "source_as_of": utc_now_iso(),
        "refresh_interval_days": 7,
        "source_url": "https://finance.yahoo.com + SEC EDGAR local cache",
        "tickers": tickers,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _halal_universe_tickers() -> list[str]:
    """The compliant US universe across all known Shariah sources — the names the
    halal-first live screen actually runs over. Warming these keeps the T132a
    yfinance overlay current for the real screening universe, not just the demo set."""
    overrides = normalize_shariah_overrides(
        {"active_sources": sorted(KNOWN_CONFIGURABLE_SOURCES)}
    )
    return _compliant_universe(overrides)


def _warm_strategy_snapshots() -> None:
    for slug in [
        "midterm_52w_high_momentum",
        "shortterm_atr_breakout",
        "shortterm_minervini_vcp",
    ]:
        try:
            result = run_strategy(
                slug,
                parameters={"regime_gate": False, "refresh_events": False},
                filters={"exclude_earnings_within_days": 0},
            )
        except Exception as exc:
            print(f"Skipped {slug} snapshot warm: {exc}")
            continue
        print(
            f"Warmed {slug} broad snapshot as of {result.as_of_date} with {result.candidate_count} candidates"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch real yfinance OHLCV and persist it to Parquet."
    )
    parser.add_argument(
        "--tickers",
        help="Comma-separated tickers. Defaults to the app's real liquid US ticker set.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=650,
        help="Calendar days to fetch; 650 supports 52-week and 12-1 momentum.",
    )
    parser.add_argument(
        "--skip-shariah",
        action="store_true",
        help="Skip Shariah external source refresh.",
    )
    parser.add_argument(
        "--force-shariah",
        action="store_true",
        help="Force Halal Terminal Shariah refresh even inside the cadence window.",
    )
    parser.add_argument(
        "--skip-events",
        action="store_true",
        help="Skip earnings, 8-K, and macro event refresh.",
    )
    parser.add_argument(
        "--finispia-export", help="Path or URL to a real Finispia CSV/JSON export."
    )
    parser.add_argument(
        "--skip-halal-universe",
        action="store_true",
        help="Only warm the default/--tickers set; skip warming the full compliant "
        "halal universe (the live screen would then rely on stale Stooq for those names).",
    )
    args = parser.parse_args()

    base_tickers = _tickers(args.tickers)

    # 1. Seed Shariah sources FIRST so the compliant universe reflects today's
    #    holdings before we decide which tickers to warm.
    if not args.skip_shariah:
        spus_count = seed_spus_holdings(manifest_path=MANIFEST_PATH)
        print(f"Refreshed {spus_count} SPUS Shariah source rows")
        for source_name, count in seed_all_etf_holdings(
            manifest_path=MANIFEST_PATH
        ).items():
            print(f"Refreshed {count} {source_name} Shariah source rows")
        if args.finispia_export:
            finispia_count = seed_finispia_export(
                path_or_url=args.finispia_export,
                manifest_path=MANIFEST_PATH,
            )
            print(f"Refreshed {finispia_count} Finispia Shariah source rows")
        try:
            halal_terminal_count = seed_halal_terminal_results(
                manifest_path=MANIFEST_PATH,
                force=args.force_shariah,
            )
        except RuntimeError as exc:
            halal_terminal_count = None
            # Do NOT swallow silently: without this key the compliant ("halal-first")
            # universe bakes stale behind fresh prices and only the freshness banner
            # ever notices. Warn loudly; other sources still refreshed above.
            print(
                "WARNING: Halal Terminal Shariah source NOT refreshed "
                f"({exc}). Set HALAL_TERMINAL_API_KEY so the compliant universe "
                "stays current; the snapshot will otherwise re-bake stale "
                "compliance data."
            )
        if halal_terminal_count is not None:
            print(
                f"Refreshed {halal_terminal_count} Halal Terminal Shariah source rows"
            )

    # 2. Warm set = default/--tickers ∪ compliant halal universe. The app is
    #    halal-first (T147), so warming the compliant names keeps the T132a
    #    yfinance overlay current for the universe the live screen actually uses.
    warm_tickers = list(base_tickers)
    if not args.skip_halal_universe:
        halal = _halal_universe_tickers()
        if halal:
            warm_tickers = sorted(set(base_tickers) | set(halal))
            print(
                f"Halal-first warm set: {len(halal)} compliant names; "
                f"warming {len(warm_tickers)} tickers total "
                f"(first run backfills full history — subsequent runs are incremental)"
            )

    # 3. Incrementally warm prices + profiles for the full warm set.
    prices = fetch_incremental_ohlcv(warm_tickers, history_days=args.days)
    if not prices.empty:
        save_prices(prices)
    refresh_profiles(warm_tickers)
    stored = load_prices(warm_tickers)
    _update_manifest(len(stored), warm_tickers)
    print(
        f"Warmed price/profile caches for {len(warm_tickers)} tickers; fetched {len(prices)} new OHLCV rows"
    )
    _warm_strategy_snapshots()

    # 4. Events stay scoped to the base set — per-ticker EDGAR/earnings refresh over
    #    the full halal universe daily would be an EDGAR storm; the overlay handles
    #    price freshness, and event badges fetch lazily for screened candidates.
    if not args.skip_events:
        service = EventsService()
        for ticker in base_tickers:
            service.refresh_ticker_events(ticker)
        econ_count = seed_econ_calendar()
        print(
            f"Refreshed earnings/8-K events for {len(base_tickers)} tickers and {econ_count} macro calendar events"
        )


if __name__ == "__main__":
    main()
