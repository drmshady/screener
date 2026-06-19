from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

from ..lib.disclaimer import utc_now_iso
from ..models.events import TickerEvent
from .events_store import DEFAULT_DB_PATH

SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_8K_SOURCE = "sec_edgar_8k"


def _headers() -> dict[str, str]:
    return {
        "User-Agent": os.getenv(
            "SEC_USER_AGENT",
            "screener-local-events contact@example.com",
        )
    }


def _catalog_cik(ticker: str, db_path: Path | str = DEFAULT_DB_PATH) -> str | None:
    path = Path(db_path)
    if not path.exists():
        return None
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT cik FROM tickers WHERE ticker = ?",
            (ticker.upper(),),
        ).fetchone()
    if row and row[0]:
        return str(row[0]).zfill(10)
    return None


def _sec_cik(ticker: str) -> str | None:
    response = httpx.get(SEC_COMPANY_TICKERS_URL, headers=_headers(), timeout=30)
    response.raise_for_status()
    rows = response.json().values()
    symbol = ticker.upper()
    for row in rows:
        if str(row.get("ticker", "")).upper() == symbol:
            return str(row.get("cik_str")).zfill(10)
    return None


def cik_for_ticker(ticker: str, db_path: Path | str = DEFAULT_DB_PATH) -> str | None:
    return _catalog_cik(ticker, db_path) or _sec_cik(ticker)


def _filing_url(cik: str, accession: str) -> str:
    cik_plain = str(int(cik))
    accession_plain = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_plain}/{accession_plain}/{accession}-index.html"


def fetch_recent_8k_filings(
    ticker: str,
    *,
    days: int = 30,
    as_of_date: date | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[TickerEvent]:
    symbol = ticker.strip().upper()
    cik = cik_for_ticker(symbol, db_path)
    if not cik:
        return []
    as_of = as_of_date or date.today()
    since = as_of - timedelta(days=days)
    response = httpx.get(
        SEC_SUBMISSIONS_URL.format(cik=cik), headers=_headers(), timeout=30
    )
    response.raise_for_status()
    recent = response.json().get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    accession_numbers = recent.get("accessionNumber", [])
    accepted = recent.get("acceptanceDateTime", [])

    source_as_of = utc_now_iso()
    events: list[TickerEvent] = []
    for form, filing_date, accession, accepted_at in zip(
        forms, filing_dates, accession_numbers, accepted, strict=False
    ):
        if str(form).upper() != "8-K":
            continue
        filed = date.fromisoformat(filing_date)
        if filed < since or filed > as_of:
            continue
        event_time = None
        try:
            accepted_dt = datetime.fromisoformat(
                str(accepted_at).replace("Z", "+00:00")
            )
            if accepted_dt.tzinfo is None:
                accepted_dt = accepted_dt.replace(tzinfo=timezone.utc)
            event_time = accepted_dt.time().replace(microsecond=0).isoformat()
        except (TypeError, ValueError):
            pass
        events.append(
            TickerEvent(
                ticker=symbol,
                event_type="8K_filed",
                event_date=filed.isoformat(),
                event_time=event_time,
                source_name=SEC_8K_SOURCE,
                source_as_of=source_as_of,
                source_url=_filing_url(cik, accession),
                metadata={"accession_number": accession, "cik": cik},
            )
        )
    return events
