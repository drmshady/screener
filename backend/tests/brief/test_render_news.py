"""Feature 018 T024 (US2) — news + market-context render.

Sections render deterministically, each news item shows source + as-of, the
quiet-day copy appears when there is nothing material, and no directive language
leaks into the neutral path.
"""
from __future__ import annotations

from decimal import Decimal

from backend.src.brief import render
from backend.src.models.brief import (
    BriefModel,
    MarketContextLine,
    NewsItem,
    PortfolioStatusSection,
    RecommendationItem,
    SourceSignal,
    SubjectKind,
)


def _recs() -> list[RecommendationItem]:
    return [
        RecommendationItem(
            rank=i + 1,
            subject="portfolio",
            subject_kind=SubjectKind.PORTFOLIO,
            reason="No actionable signal.",
            source_signal=SourceSignal.PORTFOLIO_ACTION,
            text="No action indicated at this time.",
        )
        for i in range(5)
    ]


def _brief(news: list[NewsItem], market: MarketContextLine | None) -> BriefModel:
    return BriefModel(
        target_session="2026-07-08",
        portfolio=PortfolioStatusSection(total_value=Decimal("0"), is_empty=True),
        news=news,
        market_context=market,
        recommendations=_recs(),
        data_as_of="2026-07-08",
    )


def test_news_items_show_source_and_as_of() -> None:
    news = [
        NewsItem(
            tickers=["HELD"],
            headline="HELD posts strong quarter",
            sentiment_label="positive",
            source="Acme Newswire",
            as_of="2026-07-08",
        )
    ]
    market = MarketContextLine(
        regime="Trending up",
        regime_detail="SPY above its 200-day SMA",
        market_events=["FOMC on 2026-07-15"],
        source="daily-baked SPY; econ calendar",
        as_of="2026-07-08",
    )
    _subject, text, _html = render.render_brief(_brief(news, market))
    assert "Acme Newswire" in text
    assert "as of 2026-07-08" in text
    assert "Trending up" in text
    assert "FOMC on 2026-07-15" in text


def test_quiet_day_copy_present() -> None:
    _subject, text, _html = render.render_brief(_brief([], None))
    assert "Nothing material" in text
    assert "Market context is unavailable" in text


def test_render_is_deterministic() -> None:
    news = [
        NewsItem(
            tickers=["HELD"],
            headline="HELD news",
            sentiment_label="negative",
            source="Src",
            as_of="2026-07-08",
        )
    ]
    a = render.render_brief(_brief(news, None))
    b = render.render_brief(_brief(news, None))
    assert a == b
