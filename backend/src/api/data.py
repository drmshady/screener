from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..data.prices import fetch_incremental_ohlcv
from ..data.prices_store import load_last_dates, save_prices
from ..data.saudi_universe import saudi_universe
from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from ..screening.engine import (
    DEFAULT_SCREEN_TICKERS,
    _compliant_universe,
    clear_snapshot_caches,
    refresh_reference_thresholds,
)
from ..shariah.lookup import normalize_shariah_overrides

router = APIRouter(prefix="/data", tags=["data"])

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "data" / "manifest.json"

# The default US halal screen runs on the compliant universe, so a manual US
# refresh must cover those names (not just the 20 demo tickers) for the
# recommended stocks' date to advance. Default Shariah sources mirror the
# frontend store's defaults.
_DEFAULT_SHARIAH_SOURCES = [
    "spus_holdings",
    "spwo_holdings",
    "spre_holdings",
    "spte_holdings",
    "halal_terminal",
]


def _update_prices_manifest(tickers: list[str]) -> str | None:
    """Refresh the yfinance source's per-ticker last-bar dates in the manifest so
    /meta (header + home 'prices as of') reflects the manual refresh, not just
    scripts/ingest_daily.py. Merges into existing dates (keeps other tickers)."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest = (
        json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if MANIFEST_PATH.exists()
        else {"sources": {}}
    )
    src = manifest.setdefault("sources", {}).setdefault("yfinance", {})
    src["kind"] = "prices"
    src["refresh_interval_days"] = src.get("refresh_interval_days", 1)
    src["source_url"] = src.get("source_url", "https://finance.yahoo.com")
    src["source_as_of"] = utc_now_iso()
    src["is_stale"] = False
    by_ticker = src.get("last_bar_date_by_ticker")
    if not isinstance(by_ticker, dict):
        by_ticker = {}
    for ticker, last_date in load_last_dates(tickers).items():
        by_ticker[ticker] = last_date.isoformat()
    src["last_bar_date_by_ticker"] = by_ticker
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return max(by_ticker.values(), default=None)

# Bound a manual refresh so an interactive click can't kick off a multi-minute,
# thousands-of-names yfinance pull (that's the scheduled ingest's job).
_MAX_REFRESH_TICKERS = 1200


class DataRefreshRequest(BaseModel):
    market: str | None = None  # "US" | "SA"
    tickers: list[str] | None = Field(default=None)


class DataRefreshResponse(BaseModel):
    refreshed_tickers: int
    fetched_rows: int
    latest_bar: str | None
    capped: bool
    data_as_of: str
    disclaimer: str


def _resolve_tickers(req: DataRefreshRequest) -> list[str]:
    if req.tickers:
        names = [t.strip().upper() for t in req.tickers if t.strip()]
    elif str(req.market or "").upper() in {"SA", "SAUDI", "TADAWUL"}:
        names = saudi_universe()
    else:
        # US: refresh the actual screened (compliant halal) universe so the
        # recommended stocks' date advances, not just the demo tickers.
        try:
            overrides = normalize_shariah_overrides(
                {"active_sources": _DEFAULT_SHARIAH_SOURCES}
            )
            names = _compliant_universe(overrides) or list(DEFAULT_SCREEN_TICKERS)
        except Exception:
            names = list(DEFAULT_SCREEN_TICKERS)
    return sorted(set(names))


@router.post("/refresh", response_model=DataRefreshResponse)
def refresh_data(req: DataRefreshRequest) -> DataRefreshResponse:
    """Manually pull the latest bars for the market's screened universe (or an
    explicit list), persist them, update the manifest so /meta shows the new date,
    and clear snapshot caches so the next screen reflects the fresh data."""
    names = _resolve_tickers(req)
    capped = len(names) > _MAX_REFRESH_TICKERS
    names = names[:_MAX_REFRESH_TICKERS]

    fetched = fetch_incremental_ohlcv(names, history_days=650)
    if not fetched.empty:
        save_prices(fetched)
    manifest_latest = _update_prices_manifest(names)
    clear_snapshot_caches()

    # Recompute the fixed reference-universe thresholds for the cross-sectional
    # gates so a name's GP/asset-growth verdict stays stable across the screen and
    # single-ticker analysis on the fresh data. Best-effort: never fail the refresh.
    try:
        refresh_reference_thresholds()
    except Exception:
        pass

    last_dates = load_last_dates(names)
    latest_bar = max((d.isoformat() for d in last_dates.values()), default=manifest_latest)
    return DataRefreshResponse(
        refreshed_tickers=len(names),
        fetched_rows=int(len(fetched)),
        latest_bar=latest_bar,
        capped=capped,
        data_as_of=utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )
