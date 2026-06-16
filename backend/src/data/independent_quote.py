"""Harness-only independent quote provider (feature 008, T018; Decision 5).

A *free-tier third-party quote vendor outside the snapshot pipeline*, behind a
small ``IndependentQuoteProvider`` interface mirroring ``PriceProvider``. It
exists solely to give the offline integrity harness a vendor-independent reality
check on the top-N candidates' price / 52-week-high (FR-010). It is imported
**only by the harness** — never by any live screen path — so the live screen
stays provably network-free (FR-002/FR-024).

Vendors (Decision 5):
  * **Primary: Finnhub** — ``/quote`` (``c`` = current price) +
    ``/stock/metric?metric=price`` (``52WeekHigh``).
  * **Fallback: Alpha Vantage** — ``GLOBAL_QUOTE`` (price; 52-week high not
    exposed there → ``None``, "derived where unavailable").

Key handling (project rule + FR-009): the API key is read from
``SCREENER_INDEPENDENT_QUOTE_API_KEY`` at construction and is **never written to
or read from any file**. A missing key, an HTTP error, or an unparseable
response yields a clean ``available=False`` quote (→ ``UNVERIFIED`` downstream),
never a crash.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional, Protocol

INDEPENDENT_QUOTE_KEY_ENV = "SCREENER_INDEPENDENT_QUOTE_API_KEY"

# A pluggable HTTP layer: (url, params) -> parsed-JSON dict. Injected in tests so
# the provider is exercised with no network; the default uses httpx (already a
# project dependency). It MUST raise on any transport/HTTP error so the provider
# can convert that into an "unavailable" result rather than a partial parse.
Transport = Callable[[str, dict], dict]


@dataclass(frozen=True)
class IndependentQuote:
    """An immutable independent reading for one ticker (data-model §10 inputs)."""

    ticker: str
    price: Optional[float]
    high_52w: Optional[float]
    source: str
    available: bool
    error: Optional[str] = None


class IndependentQuoteProvider(Protocol):
    """The harness's vendor-independent quote interface (mirrors PriceProvider)."""

    def quote(self, ticker: str) -> IndependentQuote: ...


def _httpx_transport(timeout: float = 8.0) -> Transport:
    """Default transport: a GET returning parsed JSON, raising on any error."""

    def transport(url: str, params: dict) -> dict:
        import httpx  # local import: harness-only, keeps live path import-clean

        resp = httpx.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    return transport


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return f


def _unavailable(ticker: str, source: str, error: str) -> IndependentQuote:
    return IndependentQuote(
        ticker=ticker,
        price=None,
        high_52w=None,
        source=source,
        available=False,
        error=error,
    )


class FinnhubQuoteProvider:
    """Finnhub primary adapter (Decision 5)."""

    BASE = "https://finnhub.io/api/v1"

    def __init__(self, api_key: Optional[str], transport: Optional[Transport] = None):
        self._api_key = api_key
        self._transport = transport or _httpx_transport()

    def quote(self, ticker: str) -> IndependentQuote:
        if not self._api_key:
            return _unavailable(ticker, "finnhub", "no API key configured")
        try:
            q = self._transport(
                f"{self.BASE}/quote", {"symbol": ticker, "token": self._api_key}
            )
            price = _to_float((q or {}).get("c"))
            high_52w: Optional[float] = None
            try:
                m = self._transport(
                    f"{self.BASE}/stock/metric",
                    {"symbol": ticker, "metric": "price", "token": self._api_key},
                )
                high_52w = _to_float(((m or {}).get("metric") or {}).get("52WeekHigh"))
            except Exception:
                # The 52-week-high call is best-effort; a missing metric still
                # leaves a usable price reading.
                high_52w = None
            if price is None:
                return _unavailable(ticker, "finnhub", "no price in response")
            return IndependentQuote(
                ticker=ticker,
                price=price,
                high_52w=high_52w,
                source="finnhub",
                available=True,
            )
        except Exception as exc:  # network / parse error -> unavailable, no crash
            return _unavailable(ticker, "finnhub", f"{type(exc).__name__}: {exc}")


class AlphaVantageQuoteProvider:
    """Alpha Vantage GLOBAL_QUOTE fallback adapter (Decision 5)."""

    BASE = "https://www.alphavantage.co/query"

    def __init__(self, api_key: Optional[str], transport: Optional[Transport] = None):
        self._api_key = api_key
        self._transport = transport or _httpx_transport()

    def quote(self, ticker: str) -> IndependentQuote:
        if not self._api_key:
            return _unavailable(ticker, "alpha_vantage", "no API key configured")
        try:
            payload = self._transport(
                self.BASE,
                {
                    "function": "GLOBAL_QUOTE",
                    "symbol": ticker,
                    "apikey": self._api_key,
                },
            )
            quote = (payload or {}).get("Global Quote") or {}
            price = _to_float(quote.get("05. price"))
            if price is None:
                return _unavailable(ticker, "alpha_vantage", "no price in response")
            # GLOBAL_QUOTE does not expose a 52-week high; derive-where-unavailable.
            return IndependentQuote(
                ticker=ticker,
                price=price,
                high_52w=None,
                source="alpha_vantage",
                available=True,
            )
        except Exception as exc:
            return _unavailable(ticker, "alpha_vantage", f"{type(exc).__name__}: {exc}")


class FallbackQuoteProvider:
    """Tries ``primary``; on an unavailable result falls back to ``fallback``."""

    def __init__(
        self,
        primary: IndependentQuoteProvider,
        fallback: Optional[IndependentQuoteProvider] = None,
    ):
        self._primary = primary
        self._fallback = fallback

    def quote(self, ticker: str) -> IndependentQuote:
        q = self._primary.quote(ticker)
        if q.available or self._fallback is None:
            return q
        fb = self._fallback.quote(ticker)
        if fb.available:
            return fb
        # Surface the primary's error but keep the fallback's source-agnostic shape.
        return _unavailable(
            ticker,
            f"{q.source}+{fb.source}",
            f"primary: {q.error or 'unavailable'}; fallback: {fb.error or 'unavailable'}",
        )


def build_default_independent_provider(
    transport: Optional[Transport] = None,
) -> IndependentQuoteProvider:
    """Finnhub-primary + Alpha-Vantage-fallback provider, keyed from the env only.

    The single ``SCREENER_INDEPENDENT_QUOTE_API_KEY`` is shared by both adapters
    (the operator sets whichever vendor's free key they hold); the provider is
    constructed fresh so a key rotation in the process env takes effect on the
    next harness run. ``transport`` is injectable for tests.
    """
    key = os.getenv(INDEPENDENT_QUOTE_KEY_ENV)
    return FallbackQuoteProvider(
        primary=FinnhubQuoteProvider(api_key=key, transport=transport),
        fallback=AlphaVantageQuoteProvider(api_key=key, transport=transport),
    )
