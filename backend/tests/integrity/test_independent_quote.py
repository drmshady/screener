"""T016 [US2] — the harness-only independent quote provider (Decision 5, FR-009).

Written FIRST: must FAIL before ``data/independent_quote.py`` exists (T018).

With a fully mocked HTTP layer (no network) assert:
  * Finnhub ``/quote`` + ``/stock/metric`` parse to price + 52-week high;
  * Alpha Vantage ``GLOBAL_QUOTE`` fallback parses price;
  * a missing/unset key or a network error yields a clean "unavailable" result
    (→ UNVERIFIED downstream), never a crash (FR-009);
  * the key is read from ``SCREENER_INDEPENDENT_QUOTE_API_KEY`` ONLY, never a file.
"""
from __future__ import annotations

import pytest

from backend.src.data.independent_quote import (
    INDEPENDENT_QUOTE_KEY_ENV,
    AlphaVantageQuoteProvider,
    FallbackQuoteProvider,
    FinnhubQuoteProvider,
    IndependentQuote,
    build_default_independent_provider,
)


def _finnhub_transport(price=121.5, high=130.0):
    def transport(url: str, params: dict) -> dict:
        if "/quote" in url and "/stock" not in url:
            return {"c": price, "h": price, "l": price, "pc": price}
        if "/stock/metric" in url:
            return {"metric": {"52WeekHigh": high, "52WeekLow": 80.0}}
        raise AssertionError(f"unexpected url {url}")

    return transport


def _alpha_transport(price="121.50"):
    def transport(url: str, params: dict) -> dict:
        return {"Global Quote": {"01. symbol": params.get("symbol"), "05. price": price}}

    return transport


def test_finnhub_parses_price_and_52w_high():
    provider = FinnhubQuoteProvider(api_key="k", transport=_finnhub_transport())
    q = provider.quote("BELFB")
    assert q.available is True
    assert q.source == "finnhub"
    assert q.price == pytest.approx(121.5)
    assert q.high_52w == pytest.approx(130.0)


def test_alpha_vantage_global_quote_parses_price():
    provider = AlphaVantageQuoteProvider(api_key="k", transport=_alpha_transport())
    q = provider.quote("BELFB")
    assert q.available is True
    assert q.source == "alpha_vantage"
    assert q.price == pytest.approx(121.5)
    # GLOBAL_QUOTE carries no 52-week high — derived-where-unavailable is None.
    assert q.high_52w is None


def test_network_error_yields_unavailable_not_crash():
    def boom(url, params):
        raise RuntimeError("connection reset")

    provider = FinnhubQuoteProvider(api_key="k", transport=boom)
    q = provider.quote("BELFB")
    assert q.available is False
    assert q.price is None and q.high_52w is None
    assert q.error  # a reason is recorded


def test_missing_key_yields_unavailable_not_crash():
    provider = FinnhubQuoteProvider(api_key=None, transport=_finnhub_transport())
    q = provider.quote("BELFB")
    assert q.available is False
    assert q.price is None


def test_fallback_uses_alpha_vantage_when_primary_unavailable():
    def primary_down(url, params):
        raise RuntimeError("finnhub down")

    primary = FinnhubQuoteProvider(api_key="k", transport=primary_down)
    fallback = AlphaVantageQuoteProvider(api_key="k", transport=_alpha_transport())
    provider = FallbackQuoteProvider(primary=primary, fallback=fallback)
    q = provider.quote("BELFB")
    assert q.available is True
    assert q.source == "alpha_vantage"
    assert q.price == pytest.approx(121.5)


def test_fallback_reports_unavailable_when_all_sources_down():
    def down(url, params):
        raise RuntimeError("down")

    provider = FallbackQuoteProvider(
        primary=FinnhubQuoteProvider(api_key="k", transport=down),
        fallback=AlphaVantageQuoteProvider(api_key="k", transport=down),
    )
    q = provider.quote("BELFB")
    assert q.available is False


def test_key_is_read_from_env_var_only(monkeypatch):
    """The key comes from SCREENER_INDEPENDENT_QUOTE_API_KEY; never from a file."""
    assert INDEPENDENT_QUOTE_KEY_ENV == "SCREENER_INDEPENDENT_QUOTE_API_KEY"

    monkeypatch.setenv(INDEPENDENT_QUOTE_KEY_ENV, "env-secret-123")
    provider = build_default_independent_provider(transport=_finnhub_transport())
    q = provider.quote("BELFB")
    assert q.available is True  # the env key was used

    monkeypatch.delenv(INDEPENDENT_QUOTE_KEY_ENV, raising=False)
    provider2 = build_default_independent_provider(transport=_finnhub_transport())
    q2 = provider2.quote("BELFB")
    assert q2.available is False  # no key anywhere → unavailable, no file read


def test_independent_quote_is_immutable_value():
    q = IndependentQuote(
        ticker="BELFB", price=1.0, high_52w=2.0, source="finnhub", available=True
    )
    with pytest.raises(Exception):
        q.price = 5.0  # frozen dataclass
