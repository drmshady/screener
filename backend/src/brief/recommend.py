"""Deterministic rule-based ranker producing exactly five recommendations.

Pure synthesis over signals the brief already carries — it selects nothing new and
fabricates no signal (FR-005). Precedence (documented constants below):

1. **Tier 1 — Holdings attention** (`AttentionItem`s, already precedence-ordered
   risk/heat breach → stop proximity → stage change).
2. **Tier 2 — News/sentiment materiality** (held before watched, strongest first).
3. **Tier 3 — Portfolio-level fill** (heat-headroom note → "no action indicated"
   per remaining holding in ticker order → watchlist-review note → generic), so the
   list always reaches exactly five (US3 AC4).

Selection + ordering are deterministic; ties break on `(severity desc, ticker asc)`
(FR-013). Wording is gated by `directive`: neutral, no-directive-verb copy by
default (FR-006, lint-tested); direct language + strategy citations when the
single-owner carve-out holds (FR-007). An AI narrative model may only *phrase* the
already-selected items in `render.py` — never select or add signals.
"""
from __future__ import annotations

from decimal import Decimal

from ..models.brief import (
    AttentionItem,
    AttentionReason,
    NewsItem,
    PortfolioStatusSection,
    RecommendationItem,
    SourceSignal,
    SubjectKind,
)

# Documented ranking constants (contracts/recommendation-ranking.md).
FINAL_COUNT = 5
_MATERIAL_SENTIMENT = {"positive", "negative", "mixed"}


def _attention_text(item: AttentionItem, *, directive: bool) -> tuple[str, str]:
    """(reason, text) for a holdings-attention recommendation."""
    reason = item.detail
    if directive:
        if item.reason_code in (AttentionReason.RISK_BREACH, AttentionReason.HEAT_BREACH):
            text = f"{item.ticker}: reduce exposure — {item.detail}."
        elif item.reason_code is AttentionReason.STOP_PROXIMITY:
            text = f"{item.ticker}: manage the stop — {item.detail}."
        else:
            text = f"{item.ticker}: review the position — {item.detail}."
    else:
        text = f"{item.ticker}: {item.detail} — candidate for review."
    return reason, text


def _news_text(item: NewsItem, *, directive: bool) -> tuple[str, str]:
    label = item.sentiment_label or "material"
    reason = f"{label} news/sentiment signal in the window"
    tickers = ", ".join(item.tickers) or "portfolio"
    if directive:
        text = f"{tickers}: review on the {label} signal — {item.headline}."
    else:
        text = f"{tickers}: {label} news signal — consider reviewing ({item.headline})."
    return reason, text


def select_recommendations(
    section: PortfolioStatusSection,
    news: list[NewsItem],
    *,
    directive: bool,
    held_tickers: list[str] | None = None,
    watchlist_tickers: list[str] | None = None,
    citations: list[str] | None = None,
) -> list[RecommendationItem]:
    """Return exactly five priority-ordered recommendations (FR-005, SC-003)."""
    held = {t.upper() for t in (held_tickers or [])}
    watched = list(watchlist_tickers or [])
    directive_citations = list(citations or []) if directive else []

    candidates: list[RecommendationItem] = []
    used_subjects: set[str] = set()

    # --- Tier 1: holdings attention (already precedence-ordered) ------------
    for item in section.attention:
        reason, text = _attention_text(item, directive=directive)
        candidates.append(
            RecommendationItem(
                rank=0,
                subject=item.ticker,
                subject_kind=SubjectKind.HOLDING,
                reason=reason,
                source_signal=SourceSignal.ATTENTION,
                citations=list(directive_citations),
                text=text,
            )
        )
        used_subjects.add(item.ticker.upper())

    # --- Tier 2: news/sentiment materiality (held before watched) -----------
    def _news_sort_key(item: NewsItem) -> tuple[int, float, str]:
        is_held = any(t.upper() in held for t in item.tickers)
        primary = (item.tickers[0].upper() if item.tickers else "~")
        return (0 if is_held else 1, 0.0, primary)  # stable; strength folded in below

    material_news = [
        item
        for item in news
        if (item.sentiment_label or "").lower() in _MATERIAL_SENTIMENT
    ]
    for item in sorted(material_news, key=_news_sort_key):
        subject_ticker = item.tickers[0].upper() if item.tickers else "portfolio"
        if subject_ticker in used_subjects:
            continue
        reason, text = _news_text(item, directive=directive)
        kind = SubjectKind.HOLDING if subject_ticker in held else SubjectKind.WATCHLIST
        candidates.append(
            RecommendationItem(
                rank=0,
                subject=subject_ticker,
                subject_kind=kind if subject_ticker != "portfolio" else SubjectKind.PORTFOLIO,
                reason=reason,
                source_signal=SourceSignal.NEWS_SENTIMENT,
                citations=list(directive_citations),
                text=text,
            )
        )
        used_subjects.add(subject_ticker)

    # --- Tier 3: portfolio-level fill (never fabricates a signal) -----------
    fill: list[RecommendationItem] = []

    headroom_pct = section.heat_headroom_pct
    fill.append(
        RecommendationItem(
            rank=0,
            subject="portfolio",
            subject_kind=SubjectKind.PORTFOLIO,
            reason=f"Portfolio heat headroom is {headroom_pct:.0%} of capital.",
            source_signal=SourceSignal.PORTFOLIO_ACTION,
            citations=[],
            text=f"Portfolio heat headroom {headroom_pct:.0%} — no action indicated at this time.",
        )
    )

    for holding in section.holdings:
        if holding.ticker.upper() in used_subjects:
            continue
        fill.append(
            RecommendationItem(
                rank=0,
                subject=holding.ticker,
                subject_kind=SubjectKind.HOLDING,
                reason="No actionable signal; position is within the risk budget.",
                source_signal=SourceSignal.PORTFOLIO_ACTION,
                citations=[],
                text=f"{holding.ticker}: no action indicated at this time.",
            )
        )

    if watched:
        fill.append(
            RecommendationItem(
                rank=0,
                subject="watchlist",
                subject_kind=SubjectKind.PORTFOLIO,
                reason=f"{len(watched)} watched name(s) tracked.",
                source_signal=SourceSignal.PORTFOLIO_ACTION,
                citations=[],
                text=f"Watchlist: {len(watched)} name(s) — consider reviewing.",
            )
        )

    # Generic padding guarantees at least five even for an empty portfolio.
    while len(candidates) + len(fill) < FINAL_COUNT:
        fill.append(
            RecommendationItem(
                rank=0,
                subject="portfolio",
                subject_kind=SubjectKind.PORTFOLIO,
                reason="No actionable signal from available data.",
                source_signal=SourceSignal.PORTFOLIO_ACTION,
                citations=[],
                text="No action indicated at this time.",
            )
        )

    ordered = (candidates + fill)[:FINAL_COUNT]
    for index, item in enumerate(ordered):
        item.rank = index + 1
    return ordered
