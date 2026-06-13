from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import yfinance as yf

from .fundamentals import FundamentalsLoader
from .sectors import SectorMapper

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "catalog.db"
EDGAR_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "edgar_cache"

ProfileFetcher = Callable[[str], dict[str, Any]]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_profile_cache(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ticker_profile_cache (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sector TEXT NOT NULL,
            fcf_ttm REAL,
            debt_to_equity REAL,
            gross_profit REAL,
            total_assets REAL,
            gp_to_assets REAL,
            source_name TEXT NOT NULL,
            source_as_of TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        )
        """)
    conn.commit()


def _normalize_debt_to_equity(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number / 100 if number > 10 else number


def _total_assets(handle: "yf.Ticker") -> float | None:
    try:
        balance_sheet = handle.balance_sheet
    except Exception:
        return None
    if (
        balance_sheet is None
        or balance_sheet.empty
        or "Total Assets" not in balance_sheet.index
    ):
        return None
    series = balance_sheet.loc["Total Assets"].dropna()
    if series.empty:
        return None
    try:
        value = float(series.iloc[0])
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _yfinance_profile(ticker: str) -> dict[str, Any]:
    handle = yf.Ticker(ticker)
    try:
        info = handle.info
    except Exception:
        info = {}
    gross_profit = info.get("grossProfits")
    total_assets = _total_assets(handle)
    gp_to_assets = (
        float(gross_profit) / total_assets
        if gross_profit not in (None, 0) and total_assets
        else None
    )
    return {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector") or "Unclassified",
        "fcf_ttm": info.get("freeCashflow"),
        "debt_to_equity": _normalize_debt_to_equity(info.get("debtToEquity")),
        "gross_profit": gross_profit,
        "total_assets": total_assets,
        "gp_to_assets": gp_to_assets,
        "source_name": "yfinance_profile",
        "source_as_of": _utc_now().isoformat().replace("+00:00", "Z"),
    }


def _edgar_quality_from_cache(
    ticker: str, as_of: date | None = None
) -> dict[str, Any] | None:
    path = EDGAR_CACHE_DIR / f"{ticker.upper()}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        quality = FundamentalsLoader().quality_metrics_as_of(
            ticker.upper(), as_of or date.today(), payload=payload
        )
        sector = SectorMapper().get_sector(str(payload.get("sic") or ""))
    except Exception:
        return None
    return {
        # SEC companyfacts has no SIC, so SectorMapper returns "Unclassified" here;
        # return None for that so it never overwrites a real yfinance sector in
        # fetch_profile's `if value is not None` merge.
        "sector": sector if sector and sector != "Unclassified" else None,
        "fcf_ttm": quality.get("fcf_ttm"),
        "debt_to_equity": quality.get("debt_to_equity"),
        "gross_profit": quality.get("gross_profit"),
        "total_assets": quality.get("total_assets"),
        "gp_to_assets": quality.get("gp_to_assets"),
        "source_name": "sec_edgar_companyfacts_cache",
        "source_as_of": _utc_now().isoformat().replace("+00:00", "Z"),
    }


def fetch_profile(ticker: str) -> dict[str, Any]:
    symbol = ticker.upper()
    profile = _yfinance_profile(symbol)
    edgar = _edgar_quality_from_cache(symbol)
    if edgar:
        profile.update(
            {key: value for key, value in edgar.items() if value is not None}
        )
        profile["source_name"] = (
            "sec_edgar_companyfacts_cache+yfinance_profile"
            if profile.get("name") != symbol
            else "sec_edgar_companyfacts_cache"
        )
    return profile


def _row_to_profile(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "name": row["name"],
        "sector": row["sector"],
        "fcf_ttm": row["fcf_ttm"],
        "debt_to_equity": row["debt_to_equity"],
        "gross_profit": row["gross_profit"],
        "total_assets": row["total_assets"],
        "gp_to_assets": row["gp_to_assets"],
        "source_name": row["source_name"],
        "source_as_of": row["source_as_of"],
    }


def load_cached_profiles(
    tickers: list[str],
    ttl_days: int = 7,
    db_path: Path = DB_PATH,
    now: datetime | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    symbols = sorted({ticker.upper() for ticker in tickers})
    if not symbols:
        return {}, []
    now = now or _utc_now()
    cutoff = now - timedelta(days=ttl_days)
    with _connect(db_path) as conn:
        ensure_profile_cache(conn)
        placeholders = ",".join("?" for _ in symbols)
        rows = conn.execute(
            f"SELECT * FROM ticker_profile_cache WHERE ticker IN ({placeholders})",
            symbols,
        ).fetchall()
    cached: dict[str, dict[str, Any]] = {}
    stale_or_missing = set(symbols)
    for row in rows:
        fetched_at = datetime.fromisoformat(
            str(row["fetched_at"]).replace("Z", "+00:00")
        )
        if fetched_at >= cutoff:
            cached[row["ticker"]] = _row_to_profile(row)
            stale_or_missing.discard(row["ticker"])
    return cached, sorted(stale_or_missing)


def save_profile_cache(
    profiles: dict[str, dict[str, Any]],
    db_path: Path = DB_PATH,
    fetched_at: datetime | None = None,
) -> None:
    fetched_at = fetched_at or _utc_now()
    with _connect(db_path) as conn:
        ensure_profile_cache(conn)
        for ticker, profile in profiles.items():
            conn.execute(
                """
                INSERT INTO ticker_profile_cache (
                    ticker, name, sector, fcf_ttm, debt_to_equity, gross_profit,
                    total_assets, gp_to_assets, source_name, source_as_of, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name=excluded.name,
                    sector=excluded.sector,
                    fcf_ttm=excluded.fcf_ttm,
                    debt_to_equity=excluded.debt_to_equity,
                    gross_profit=excluded.gross_profit,
                    total_assets=excluded.total_assets,
                    gp_to_assets=excluded.gp_to_assets,
                    source_name=excluded.source_name,
                    source_as_of=excluded.source_as_of,
                    fetched_at=excluded.fetched_at
                """,
                (
                    ticker.upper(),
                    str(profile.get("name") or ticker.upper()),
                    str(profile.get("sector") or "Unclassified"),
                    profile.get("fcf_ttm"),
                    profile.get("debt_to_equity"),
                    profile.get("gross_profit"),
                    profile.get("total_assets"),
                    profile.get("gp_to_assets"),
                    str(profile.get("source_name") or "unknown"),
                    str(
                        profile.get("source_as_of")
                        or fetched_at.isoformat().replace("+00:00", "Z")
                    ),
                    fetched_at.isoformat().replace("+00:00", "Z"),
                ),
            )
        conn.commit()


def load_or_fetch_profiles(
    tickers: list[str],
    ttl_days: int = 7,
    db_path: Path = DB_PATH,
    fetcher: ProfileFetcher | None = None,
) -> dict[str, dict[str, Any]]:
    symbols = sorted({ticker.upper() for ticker in tickers})
    cached, missing = load_cached_profiles(symbols, ttl_days=ttl_days, db_path=db_path)
    fetcher = fetcher or fetch_profile
    fetched: dict[str, dict[str, Any]] = {}
    for ticker in missing:
        try:
            fetched[ticker] = fetcher(ticker)
        except Exception:
            fetched[ticker] = {
                "name": ticker,
                "sector": "Unclassified",
                "fcf_ttm": None,
                "debt_to_equity": None,
                "gross_profit": None,
                "total_assets": None,
                "gp_to_assets": None,
                "source_name": "profile_unavailable",
                "source_as_of": _utc_now().isoformat().replace("+00:00", "Z"),
            }
    if fetched:
        save_profile_cache(fetched, db_path=db_path)
    return {**cached, **fetched}


def refresh_profiles(
    tickers: list[str], db_path: Path = DB_PATH
) -> dict[str, dict[str, Any]]:
    profiles = {ticker.upper(): fetch_profile(ticker.upper()) for ticker in tickers}
    save_profile_cache(profiles, db_path=db_path)
    return profiles
