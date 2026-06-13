from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import yfinance as yf
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.src.data.db import metadata_obj
from backend.src.data.econ_calendar import seed_econ_calendar
from backend.src.data.shariah_etf import seed_all_etf_holdings
from backend.src.data.shariah_finispia import seed_finispia_export
from backend.src.data.shariah_halal_terminal import seed_halal_terminal_results
from backend.src.data.shariah_spus import seed_spus_holdings
from backend.src.lib.disclaimer import utc_now_iso
from backend.src.screening.engine import DEFAULT_SCREEN_TICKERS

DB_PATH = ROOT / "backend" / "data" / "catalog.db"
MANIFEST_PATH = ROOT / "backend" / "data" / "manifest.json"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def _tickers(raw: str | None) -> list[str]:
    if not raw:
        return DEFAULT_SCREEN_TICKERS
    return sorted({part.strip().upper() for part in raw.split(",") if part.strip()})


def _exchange(raw: str | None) -> str:
    value = (raw or "").upper()
    if value in {"NMS", "NGM", "NCM", "NAS", "NASDAQ"}:
        return "NASDAQ"
    if value in {"NYQ", "NYE", "NYSE"}:
        return "NYSE"
    if value in {"ASE", "AMEX", "NYSE AMERICAN"}:
        return "NYSE_AMERICAN"
    return "NASDAQ"


def _sec_company_tickers() -> dict[str, dict]:
    headers = {"User-Agent": "screener-local-audit contact@example.com"}
    response = httpx.get(SEC_TICKERS_URL, headers=headers, timeout=30)
    response.raise_for_status()
    payload = response.json()
    return {row["ticker"].upper(): row for row in payload.values()}


def _update_manifest(row_count: int, tickers: list[str]) -> None:
    manifest = (
        json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if MANIFEST_PATH.exists()
        else {"sources": {}}
    )
    manifest.setdefault("sources", {})["sec_edgar_company_tickers"] = {
        "kind": "fundamentals",
        "source_as_of": utc_now_iso(),
        "refresh_interval_days": 7,
        "source_url": SEC_TICKERS_URL,
        "last_row_count": row_count,
        "tickers": tickers,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the SQLite catalog with real SEC/yfinance ticker metadata."
    )
    parser.add_argument(
        "--tickers",
        help="Comma-separated tickers. Defaults to the app's real liquid US ticker set.",
    )
    parser.add_argument(
        "--skip-shariah",
        action="store_true",
        help="Skip Shariah external source refresh.",
    )
    parser.add_argument(
        "--skip-events",
        action="store_true",
        help="Skip curated macro calendar seed.",
    )
    parser.add_argument(
        "--finispia-export", help="Path or URL to a real Finispia CSV/JSON export."
    )
    args = parser.parse_args()

    tickers = _tickers(args.tickers)
    sec_rows = _sec_company_tickers()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        metadata_obj.create_all(create_engine(f"sqlite:///{DB_PATH.as_posix()}"))
        now = datetime.now(timezone.utc).isoformat()
        inserted = 0
        for ticker in tickers:
            sec = sec_rows.get(ticker, {})
            try:
                info = yf.Ticker(ticker).info
            except Exception:
                info = {}
            conn.execute(
                """
                INSERT OR REPLACE INTO tickers
                (ticker, name, exchange, cik, sic_code, sector, industry, listed_at, delisted_at, source_name, source_as_of)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    ticker,
                    sec.get("title")
                    or info.get("longName")
                    or info.get("shortName")
                    or ticker,
                    _exchange(info.get("exchange")),
                    (
                        str(sec.get("cik_str")).zfill(10)
                        if sec.get("cik_str") is not None
                        else None
                    ),
                    None,
                    info.get("sector") or "Unclassified",
                    info.get("industry"),
                    date.today().isoformat(),
                    "sec_edgar_company_tickers",
                    now,
                ),
            )
            inserted += 1
        conn.commit()
    finally:
        conn.close()

    _update_manifest(inserted, tickers)
    print(f"Seeded {inserted} real ticker catalog rows into {DB_PATH}")
    if not args.skip_shariah:
        spus_count = seed_spus_holdings(db_path=DB_PATH, manifest_path=MANIFEST_PATH)
        print(f"Seeded {spus_count} SPUS Shariah source rows into {DB_PATH}")
        etf_counts = seed_all_etf_holdings(db_path=DB_PATH, manifest_path=MANIFEST_PATH)
        for source_name, count in etf_counts.items():
            print(f"Seeded {count} {source_name} Shariah source rows")
        if args.finispia_export:
            finispia_count = seed_finispia_export(
                path_or_url=args.finispia_export,
                db_path=DB_PATH,
                manifest_path=MANIFEST_PATH,
            )
            print(
                f"Seeded {finispia_count} Finispia Shariah source rows into {DB_PATH}"
            )
        try:
            halal_terminal_count = seed_halal_terminal_results(
                db_path=DB_PATH,
                manifest_path=MANIFEST_PATH,
            )
        except RuntimeError:
            halal_terminal_count = None
        if halal_terminal_count is not None:
            print(
                f"Seeded {halal_terminal_count} Halal Terminal Shariah source rows into {DB_PATH}"
            )
    if not args.skip_events:
        econ_count = seed_econ_calendar(db_path=DB_PATH)
        print(f"Seeded {econ_count} curated macro events into {DB_PATH}")


if __name__ == "__main__":
    main()
