from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

import httpx
import pandas as pd
import yfinance as yf

from ..indicators.moving_averages import calculate_sma

SSGA_SPY_HOLDINGS_URL = (
    "https://www.ssga.com/library-content/products/fund-data/etfs/us/"
    "holdings-daily-us-en-spy.xlsx"
)
REGIME_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "regime"
CONSTITUENTS_CACHE = REGIME_DATA_DIR / "sp500_constituents.json"
BREADTH_CACHE = REGIME_DATA_DIR / "breadth_cache.json"
_XML_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


@dataclass(frozen=True)
class ConstituentsSnapshot:
    tickers: list[str]
    source_name: str
    source_url: str
    source_as_of: str
    fetched_at: str


@dataclass(frozen=True)
class BreadthSnapshot:
    pct_above_sma200: float | None
    above_count: int
    eligible_count: int
    total_constituents: int
    source_name: str
    source_as_of: str | None
    price_source_name: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cache_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _excel_column(cell_ref: str) -> str:
    return "".join(char for char in cell_ref if char.isalpha())


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("m:si", _XML_NS):
        values.append(
            "".join(node.text or "" for node in item.findall(".//m:t", _XML_NS))
        )
    return values


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    value = cell.find("m:v", _XML_NS)
    if value is None or value.text is None:
        return ""
    if cell.attrib.get("t") == "s":
        return shared[int(value.text)]
    return value.text


def _parse_ssga_xlsx(content: bytes) -> ConstituentsSnapshot:
    zf = zipfile.ZipFile(io.BytesIO(content))
    shared = _shared_strings(zf)
    sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
    source_as_of: str | None = None
    header: dict[str, str] | None = None
    tickers: list[str] = []

    for row in sheet.findall(".//m:row", _XML_NS):
        cells = {
            _excel_column(cell.attrib["r"]): _cell_value(cell, shared).strip()
            for cell in row.findall("m:c", _XML_NS)
        }
        if cells.get("A") == "Holdings:" and cells.get("B"):
            source_as_of = cells["B"].replace("As of ", "").strip()
        if cells.get("A") == "Name" and cells.get("B") == "Ticker":
            header = cells
            continue
        if header and cells.get("B") and cells.get("H") == "USD":
            symbol = normalize_yfinance_symbol(cells["B"])
            if symbol and symbol not in {"-", "CASH_USD"}:
                tickers.append(symbol)

    if not tickers:
        raise ValueError("No tickers found in SSGA SPY holdings file")

    return ConstituentsSnapshot(
        tickers=sorted(set(tickers)),
        source_name="ssga_spy_holdings",
        source_url=SSGA_SPY_HOLDINGS_URL,
        source_as_of=source_as_of or _utc_now(),
        fetched_at=_utc_now(),
    )


def normalize_yfinance_symbol(symbol: str) -> str:
    # yfinance uses dashes for class shares that SSGA publishes with dots.
    normalized = re.sub(r"\s+", "", symbol.strip().upper()).replace(".", "-")
    if not re.fullmatch(r"[A-Z][A-Z0-9-]{0,5}", normalized):
        return ""
    return normalized


def load_sp500_constituents(force_refresh: bool = False) -> ConstituentsSnapshot:
    cached = _load_json(CONSTITUENTS_CACHE)
    if cached and not force_refresh:
        fetched_at = datetime.fromisoformat(
            str(cached["fetched_at"]).replace("Z", "+00:00")
        )
        if datetime.now(timezone.utc) - fetched_at <= timedelta(days=7):
            return ConstituentsSnapshot(
                tickers=[str(ticker) for ticker in cached["tickers"]],
                source_name=str(cached["source_name"]),
                source_url=str(cached["source_url"]),
                source_as_of=str(cached["source_as_of"]),
                fetched_at=str(cached["fetched_at"]),
            )

    try:
        response = httpx.get(
            SSGA_SPY_HOLDINGS_URL,
            headers={"User-Agent": "Mozilla/5.0 screener-local-regime/1.0"},
            follow_redirects=True,
            timeout=30,
        )
        response.raise_for_status()
        snapshot = _parse_ssga_xlsx(response.content)
        _cache_json(CONSTITUENTS_CACHE, snapshot.__dict__)
        return snapshot
    except Exception:
        if cached:
            return ConstituentsSnapshot(
                tickers=[str(ticker) for ticker in cached["tickers"]],
                source_name=str(cached["source_name"]),
                source_url=str(cached["source_url"]),
                source_as_of=str(cached["source_as_of"]),
                fetched_at=str(cached["fetched_at"]),
            )
        raise


def calculate_breadth_from_prices(
    prices: pd.DataFrame,
    constituents: Iterable[str],
    as_of_date: str | None = None,
    sma_length: int = 200,
) -> tuple[float | None, int, int]:
    if prices.empty:
        return None, 0, 0
    tickers = set(constituents)
    frame = prices.copy()
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["as_of_date"] = pd.to_datetime(frame["as_of_date"])
    frame = frame[frame["ticker"].isin(tickers)].dropna(subset=["close"])
    if as_of_date:
        frame = frame[frame["as_of_date"] <= pd.Timestamp(as_of_date)]

    above = 0
    eligible = 0
    for _ticker, group in frame.groupby("ticker"):
        group = group.sort_values("as_of_date")
        close = group["close"].astype(float)
        if len(close) < sma_length:
            continue
        sma = calculate_sma(close, sma_length)
        last_close = close.iloc[-1]
        last_sma = sma.iloc[-1]
        if pd.isna(last_close) or pd.isna(last_sma):
            continue
        eligible += 1
        if float(last_close) > float(last_sma):
            above += 1

    if eligible == 0:
        return None, 0, 0
    return above / eligible, above, eligible


def _prices_from_yfinance(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    for offset in range(0, len(tickers), 80):
        batch = tickers[offset : offset + 80]
        try:
            raw = yf.download(
                batch,
                start=start.isoformat(),
                end=end.isoformat(),
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True,
                timeout=30,
            )
        except Exception:
            continue
        if raw.empty:
            continue
        records: list[dict] = []
        if len(batch) == 1:
            ticker = batch[0]
            iterable = [(ticker, raw)]
        else:
            iterable = [
                (ticker, raw[ticker])
                for ticker in batch
                if hasattr(raw, "columns") and ticker in raw.columns.get_level_values(0)
            ]
        for ticker, ticker_df in iterable:
            for index, row in ticker_df.iterrows():
                close = row.get("Close")
                if pd.isna(close):
                    continue
                records.append(
                    {
                        "ticker": ticker,
                        "as_of_date": pd.Timestamp(index).date(),
                        "close": float(close),
                    }
                )
        if records:
            frames.append(pd.DataFrame(records))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_cached_breadth(as_of_date: str | None = None) -> BreadthSnapshot | None:
    cached = _load_json(BREADTH_CACHE)
    if not cached:
        return None
    if as_of_date and cached.get("as_of_date") != as_of_date:
        return None
    computed_at = datetime.fromisoformat(
        str(cached["computed_at"]).replace("Z", "+00:00")
    )
    if not as_of_date and datetime.now(timezone.utc) - computed_at > timedelta(days=1):
        return None
    return BreadthSnapshot(
        pct_above_sma200=cached.get("pct_above_sma200"),
        above_count=int(cached.get("above_count", 0)),
        eligible_count=int(cached.get("eligible_count", 0)),
        total_constituents=int(cached.get("total_constituents", 0)),
        source_name=str(cached.get("source_name", "unknown")),
        source_as_of=cached.get("source_as_of"),
        price_source_name=str(cached.get("price_source_name", "unknown")),
    )


def breadth_snapshot(
    as_of_date: str | None = None,
    constituents: list[str] | None = None,
    prices: pd.DataFrame | None = None,
    force_refresh: bool = False,
) -> BreadthSnapshot:
    if prices is None and not force_refresh:
        cached = load_cached_breadth(as_of_date)
        if cached:
            return cached

    constituent_snapshot = None
    if constituents is None:
        constituent_snapshot = load_sp500_constituents()
        constituents = constituent_snapshot.tickers

    end = (pd.Timestamp(as_of_date).date() if as_of_date else date.today()) + timedelta(
        days=1
    )
    start = end - timedelta(days=460)
    price_source_name = "injected"
    if prices is None:
        prices = _prices_from_yfinance(constituents, start=start, end=end)
        price_source_name = "yfinance"

    pct_above, above, eligible = calculate_breadth_from_prices(
        prices,
        constituents,
        as_of_date=as_of_date,
    )
    snapshot = BreadthSnapshot(
        pct_above_sma200=pct_above,
        above_count=above,
        eligible_count=eligible,
        total_constituents=len(constituents),
        source_name=(
            constituent_snapshot.source_name if constituent_snapshot else "injected"
        ),
        source_as_of=(
            constituent_snapshot.source_as_of if constituent_snapshot else None
        ),
        price_source_name=price_source_name,
    )

    if (
        prices is not None
        and constituent_snapshot is not None
        and pct_above is not None
    ):
        _cache_json(
            BREADTH_CACHE,
            {
                "as_of_date": str(pd.to_datetime(prices["as_of_date"]).dt.date.max()),
                "computed_at": _utc_now(),
                "pct_above_sma200": pct_above,
                "above_count": above,
                "eligible_count": eligible,
                "total_constituents": len(constituents),
                "source_name": constituent_snapshot.source_name,
                "source_as_of": constituent_snapshot.source_as_of,
                "price_source_name": price_source_name,
            },
        )
    return snapshot
