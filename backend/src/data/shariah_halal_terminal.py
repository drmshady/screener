from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from ..lib import flags
from ..shariah.refresh_cadence import RefreshDecision, should_refresh
from .shariah_sources import (
    DEFAULT_DB_PATH,
    DEFAULT_MANIFEST_PATH,
    load_manifest,
    normalize_ticker,
    parse_source_as_of,
    replace_source_rows,
    update_manifest_source,
    upsert_source_row,
    utc_now_iso,
)

HALAL_TERMINAL_SOURCE_NAME = "halal_terminal"
HALAL_TERMINAL_BASE_URL = "https://api.halalterminal.com"
HT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "halal_terminal_cache"


def _api_key(api_key: str | None = None) -> str:
    key = api_key or os.getenv("HALAL_TERMINAL_API_KEY")
    if not key:
        raise RuntimeError("HALAL_TERMINAL_API_KEY is not configured")
    return key


def _headers(api_key: str | None = None) -> dict[str, str]:
    return {"X-API-Key": _api_key(api_key)}


def _key_present(api_key: str | None = None) -> bool:
    return bool(api_key or os.getenv("HALAL_TERMINAL_API_KEY"))


def _parse_manifest_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _halal_terminal_meta(manifest_path: Path | str) -> dict[str, Any]:
    return load_manifest(manifest_path).get("sources", {}).get(
        HALAL_TERMINAL_SOURCE_NAME, {}
    )


def _last_success_at(manifest_path: Path | str) -> datetime | None:
    return _parse_manifest_datetime(_halal_terminal_meta(manifest_path).get("source_as_of"))


def _cached_row_count(manifest_path: Path | str) -> int:
    raw = _halal_terminal_meta(manifest_path).get("last_row_count")
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _cadence_decision(
    *,
    api_key: str | None,
    manifest_path: Path | str,
    force: bool,
    now: datetime | None,
    key_present: bool | None = None,
) -> RefreshDecision:
    return should_refresh(
        now or datetime.now(timezone.utc),
        _last_success_at(manifest_path),
        interval_days=flags.shariah_refresh_interval_days(),
        force=force,
        key_present=_key_present(api_key) if key_present is None else key_present,
    )


def _mark_stale_manifest(
    manifest_path: Path | str,
    decision: RefreshDecision,
    *,
    source_url: str,
) -> None:
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(path)
    source = manifest.setdefault("sources", {}).setdefault(
        HALAL_TERMINAL_SOURCE_NAME,
        {
            "kind": "shariah",
            "source_as_of": None,
            "source_url": source_url,
            "last_row_count": 0,
        },
    )
    source.update(
        {
            "kind": "shariah",
            "refresh_interval_days": flags.shariah_refresh_interval_days(),
            "source_url": source.get("source_url") or source_url,
            "is_stale": True,
            "stale_reason": decision.reason,
            "notes": "Cached Halal Terminal compliance data. WARNING: compliance data stale; refresh lapsed without a successful API call.",
        }
    )
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _is_us_equity(row: dict[str, Any]) -> bool:
    asset_type = str(row.get("asset_type") or row.get("type") or "").lower()
    country = str(row.get("country") or "").lower()
    return asset_type == "equity" and country in {"united states", "usa", "us"}


def status_to_row(row: dict[str, Any]) -> dict[str, Any] | None:
    if not row.get("is_compliant"):
        return None
    symbol = str(row.get("symbol") or row.get("ticker") or "").strip().upper()
    if not symbol:
        return None
    return {
        "ticker": symbol,
        "source_name": HALAL_TERMINAL_SOURCE_NAME,
        "source_kind": "external",
        "source_as_of": parse_source_as_of(row.get("last_checked_at")),
        "source_url": f"{HALAL_TERMINAL_BASE_URL}/api/screen/{symbol}",
    }


def fetch_cached_results(api_key: str | None = None) -> list[dict[str, Any]]:
    response = httpx.get(
        f"{HALAL_TERMINAL_BASE_URL}/api/results",
        headers=_headers(api_key),
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        payload = payload.get("results", [])
    if not isinstance(payload, list):
        raise ValueError("Halal Terminal /api/results returned an unexpected payload")
    return [row for row in payload if isinstance(row, dict)]


def screen_symbol(symbol: str, api_key: str | None = None) -> dict[str, Any]:
    ticker = symbol.strip().upper()
    response = httpx.post(
        f"{HALAL_TERMINAL_BASE_URL}/api/screen/{ticker}",
        headers=_headers(api_key),
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"Halal Terminal returned an unexpected payload for {ticker}")
    return payload


def seed_halal_terminal_results(
    *,
    api_key: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
    force: bool = False,
    now: datetime | None = None,
    key_present: bool | None = None,
) -> int:
    decision = _cadence_decision(
        api_key=api_key,
        manifest_path=manifest_path,
        force=force,
        now=now,
        key_present=key_present,
    )
    if decision.action == "skip":
        return _cached_row_count(manifest_path)
    if decision.action == "stale":
        _mark_stale_manifest(
            manifest_path,
            decision,
            source_url=f"{HALAL_TERMINAL_BASE_URL}/api/results",
        )
        print(f"WARNING: {decision.reason}")
        return _cached_row_count(manifest_path)

    rows = fetch_cached_results(api_key)
    us_equity_rows = [row for row in rows if _is_us_equity(row)]
    compliant_rows = [
        mapped for row in us_equity_rows if (mapped := status_to_row(row))
    ]
    stale_count = sum(1 for row in us_equity_rows if bool(row.get("is_stale")))
    row_count = replace_source_rows(
        HALAL_TERMINAL_SOURCE_NAME,
        compliant_rows,
        db_path=db_path,
        manifest_path=manifest_path,
        manifest_metadata={
            "display_name": "Halal Terminal",
            "refresh_interval_days": flags.shariah_refresh_interval_days(),
            "source_url": f"{HALAL_TERMINAL_BASE_URL}/api/results",
            "raw_result_count": len(rows),
            "us_equity_count": len(us_equity_rows),
            "stale_result_count": stale_count,
            "is_stale": stale_count > 0,
            "cadence_reason": decision.reason,
            "notes": "Cached Halal Terminal screening results. Missing tickers require live /api/screen/{symbol} calls with an API key.",
        },
    )
    return row_count


def bulk_screen_universe(
    tickers: list[str],
    *,
    api_key: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
    cache_dir: Path | str = HT_CACHE_DIR,
    rate_limit_sleep: float = 0.25,
    max_symbols: int | None = None,
    screen_fn: Callable[[str], dict[str, Any]] | None = None,
    force: bool = False,
    now: datetime | None = None,
    key_present: bool | None = None,
) -> dict[str, Any]:
    """Bulk-classify a universe via Halal Terminal per-symbol screening (T126).

    Resumable: every screened symbol's raw result is cached to `cache_dir` as
    `<TICKER>.json`, so reruns skip already-screened names (compliant *or not*).
    Compliant US equities are upserted into `shariah_sources`. `screen_fn` is
    injectable for testing without the network/API key.

    Requires `HALAL_TERMINAL_API_KEY` (or `api_key`) unless `screen_fn` is given.
    """
    universe = sorted({normalize_ticker(t) for t in tickers if normalize_ticker(t)})
    if max_symbols is not None:
        universe = universe[:max_symbols]

    stats: dict[str, Any] = {
        "universe": len(universe),
        "screened": 0,
        "from_cache": 0,
        "compliant": 0,
        "errors": 0,
        "stale": 0,
    }
    decision = _cadence_decision(
        api_key=api_key,
        manifest_path=manifest_path,
        force=force,
        now=now,
        key_present=(
            (screen_fn is not None) or _key_present(api_key)
            if key_present is None
            else key_present
        ),
    )
    if decision.action == "skip":
        stats["from_cache"] = len(universe)
        stats["reason"] = decision.reason
        return stats
    if decision.action == "stale":
        stats["stale"] = 1
        stats["reason"] = decision.reason
        _mark_stale_manifest(
            manifest_path,
            decision,
            source_url=f"{HALAL_TERMINAL_BASE_URL}/api/screen",
        )
        print(f"WARNING: {decision.reason}")
        return stats

    if screen_fn is None:
        key = _api_key(api_key)  # raises RuntimeError if unset
        screen = lambda ticker: screen_symbol(ticker, key)  # noqa: E731
    else:
        screen = screen_fn

    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    for i, ticker in enumerate(universe, start=1):
        path = cache_path / f"{ticker}.json"
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                payload = {"symbol": ticker, "error": "corrupt-cache"}
            stats["from_cache"] += 1
        else:
            try:
                payload = screen(ticker)
            except Exception as exc:
                payload = {"symbol": ticker, "error": str(exc)}
            path.write_text(json.dumps(payload), encoding="utf-8")
            stats["screened"] += 1
            if rate_limit_sleep:
                time.sleep(rate_limit_sleep)

        if not isinstance(payload, dict) or payload.get("error"):
            stats["errors"] += 1
            continue
        if payload.get("is_stale"):
            stats["stale"] += 1
        row = status_to_row(payload)  # None unless compliant
        if row is not None:
            # Accept compliant names that are explicitly US equity, or whose
            # per-symbol payload omits asset_type/country (single-symbol screens
            # often do) — the universe is already US-listed (sourced from Stooq US).
            has_classification = "asset_type" in payload or "type" in payload
            if not has_classification or _is_us_equity(payload):
                upsert_source_row(row, db_path=db_path)
                stats["compliant"] += 1
        if i % 200 == 0:
            print(f"  halal-terminal bulk {i}/{len(universe)} (compliant={stats['compliant']})")

    update_manifest_source(
        HALAL_TERMINAL_SOURCE_NAME,
        row_count=stats["compliant"],
        source_as_of=utc_now_iso(),
        source_url=f"{HALAL_TERMINAL_BASE_URL}/api/screen",
        manifest_path=manifest_path,
        metadata={
            "display_name": "Halal Terminal",
            "refresh_interval_days": flags.shariah_refresh_interval_days(),
            "is_stale": stats["stale"] > 0,
            "stale_result_count": stats["stale"],
            "bulk_universe_screened": stats["universe"],
            "cadence_reason": decision.reason,
            "notes": "Bulk per-symbol Halal Terminal screening; raw results cached under data/halal_terminal_cache/.",
        },
    )
    return stats


if __name__ == "__main__":
    count = seed_halal_terminal_results()
    print(f"Seeded {count} Halal Terminal compliant US equity rows")
