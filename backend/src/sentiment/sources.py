from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from ..lib import flags
from ..models.sentiment import SourceClass, SourceItem


def collect_sources(
    ticker: str,
    *,
    now: datetime | None = None,
    include_events: bool = True,
    refresh_events: bool = False,
) -> list[SourceItem]:
    now = now or datetime.now(UTC)
    items: list[SourceItem] = []
    for provider in flags.sentiment_news_providers():
        if provider == "yfinance":
            items.extend(_collect_yfinance_news(ticker, now=now))
        elif provider == "finnhub" and flags.finnhub_api_key():
            items.extend(_collect_finnhub_news(ticker, now=now))
        elif provider in {"alphavantage", "alpha_vantage"} and flags.alphavantage_api_key():
            items.extend(_collect_alphavantage_news(ticker, now=now))
        if items:
            break
    items.extend(_collect_yfinance_analyst_opinion(ticker, now=now))
    if include_events:
        items.extend(_collect_events(ticker, now=now, refresh=refresh_events))
    return _dedupe(items)


def _collect_yfinance_news(ticker: str, *, now: datetime) -> list[SourceItem]:
    try:
        import yfinance as yf

        raw_items = getattr(yf.Ticker(ticker), "news", None) or []
    except Exception:
        return []
    out: list[SourceItem] = []
    for raw in raw_items[:20]:
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        published_at = _published_at(raw, now)
        out.append(
            SourceItem(
                id=_stable_id("yfinance", ticker, title, published_at.isoformat()),
                source_class=SourceClass.NEWS,
                title=title,
                publisher=raw.get("publisher") or "yfinance",
                published_at=published_at,
                reference_url=raw.get("link"),
                is_stale=published_at < now - timedelta(days=30),
            )
        )
    return out


def _collect_yfinance_analyst_opinion(ticker: str, *, now: datetime) -> list[SourceItem]:
    try:
        import yfinance as yf

        rows = getattr(yf.Ticker(ticker), "upgrades_downgrades", None)
    except Exception:
        return []
    if rows is None or getattr(rows, "empty", True):
        return []
    out: list[SourceItem] = []
    try:
        recent = rows.tail(10)
        for idx, row in recent.iterrows():
            firm = str(row.get("Firm") or row.get("firm") or "analyst opinion")
            action = str(row.get("Action") or row.get("action") or "opinion update")
            to_grade = str(row.get("ToGrade") or row.get("To Grade") or "").strip()
            when = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else now
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
            title = f"{firm} {action}" + (f" to {to_grade}" if to_grade else "")
            out.append(
                SourceItem(
                    id=_stable_id("yfinance-analyst", ticker, title, when.isoformat()),
                    source_class=SourceClass.ANALYST_OPINION,
                    title=title,
                    publisher=firm,
                    published_at=when,
                    reference_url=None,
                    is_stale=when < now - timedelta(days=90),
                )
            )
    except Exception:
        return []
    return out


def _collect_events(ticker: str, *, now: datetime, refresh: bool) -> list[SourceItem]:
    try:
        from ..events.service import EventsService

        snapshot = EventsService().ticker_events(
            ticker,
            as_of_date=now.date(),
            refresh=refresh,
        )
    except Exception:
        return []
    out: list[SourceItem] = []
    for event in snapshot.events:
        try:
            published_at = datetime.fromisoformat(event.event_date).replace(tzinfo=UTC)
        except ValueError:
            published_at = now
        source_class = (
            SourceClass.FILING_8K
            if event.event_type == "8K_filed"
            else SourceClass.EARNINGS
        )
        label = "8-K filed" if event.event_type == "8K_filed" else "Earnings scheduled"
        out.append(
            SourceItem(
                id=_stable_id("event", ticker, event.event_type, event.event_date),
                source_class=source_class,
                title=f"{label}: {event.event_date}",
                publisher=event.source_name,
                published_at=published_at,
                reference_url=event.source_url,
                is_stale=published_at < now - timedelta(days=90),
            )
        )
    return out


def _collect_finnhub_news(ticker: str, *, now: datetime) -> list[SourceItem]:
    try:
        import httpx

        response = httpx.get(
            "https://finnhub.io/api/v1/company-news",
            params={
                "symbol": ticker,
                "from": (now - timedelta(days=30)).date().isoformat(),
                "to": now.date().isoformat(),
                "token": flags.finnhub_api_key(),
            },
            timeout=8.0,
        )
        response.raise_for_status()
        raw_items = response.json()
    except Exception:
        return []
    out: list[SourceItem] = []
    for raw in raw_items[:20]:
        title = str(raw.get("headline") or "").strip()
        if not title:
            continue
        published_at = _published_at(raw, now)
        out.append(
            SourceItem(
                id=_stable_id("finnhub", ticker, title, published_at.isoformat()),
                source_class=SourceClass.NEWS,
                title=title,
                publisher=raw.get("source") or "Finnhub",
                published_at=published_at,
                reference_url=raw.get("url"),
                is_stale=published_at < now - timedelta(days=30),
            )
        )
    return out


def _collect_alphavantage_news(ticker: str, *, now: datetime) -> list[SourceItem]:
    try:
        import httpx

        response = httpx.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "apikey": flags.alphavantage_api_key(),
                "limit": 20,
            },
            timeout=8.0,
        )
        response.raise_for_status()
        raw_items = response.json().get("feed", [])
    except Exception:
        return []
    out: list[SourceItem] = []
    for raw in raw_items[:20]:
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        published_at = _parse_alpha_time(raw.get("time_published"), now)
        out.append(
            SourceItem(
                id=_stable_id("alphavantage", ticker, title, published_at.isoformat()),
                source_class=SourceClass.NEWS,
                title=title,
                publisher=raw.get("source") or "Alpha Vantage",
                published_at=published_at,
                reference_url=raw.get("url"),
                is_stale=published_at < now - timedelta(days=30),
                score=_alpha_ticker_score(raw, ticker),
            )
        )
    return out


def _published_at(raw: dict[str, Any], now: datetime) -> datetime:
    stamp = raw.get("providerPublishTime") or raw.get("datetime")
    if isinstance(stamp, (int, float)):
        return datetime.fromtimestamp(stamp, tz=UTC)
    return now


def _parse_alpha_time(value: Any, now: datetime) -> datetime:
    if not value:
        return now
    try:
        return datetime.strptime(str(value), "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return now


def _alpha_ticker_score(raw: dict[str, Any], ticker: str) -> float | None:
    for item in raw.get("ticker_sentiment", []) or []:
        if str(item.get("ticker", "")).upper() != ticker.upper():
            continue
        try:
            return float(item["ticker_sentiment_score"])
        except (KeyError, TypeError, ValueError):
            return None
    return None


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"news:{digest}"


def _dedupe(items: list[SourceItem]) -> list[SourceItem]:
    seen: set[str] = set()
    out: list[SourceItem] = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)
        out.append(item)
    return out
