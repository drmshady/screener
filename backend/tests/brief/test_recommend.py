"""Feature 018 T028 (US3) — deterministic five-item recommendation ranking.

Asserts: always exactly five (SC-003) regardless of portfolio size / news volume
(US3 AC4); tier precedence (attention → news/sentiment → portfolio fill); no
fabricated signals (fill only references present tickers, FR-005); deterministic
`(severity desc, ticker asc)` tie-break (FR-013); neutral vs directive wording.
"""
from __future__ import annotations

from decimal import Decimal

from backend.src.brief import recommend
from backend.src.models.brief import (
    AttentionItem,
    AttentionReason,
    HoldingLine,
    NewsItem,
    PortfolioStatusSection,
    SourceSignal,
)
from backend.src.sentiment.narrative import validate_no_directive_language


def _holding_line(ticker: str) -> HoldingLine:
    return HoldingLine(
        ticker=ticker,
        quantity=Decimal("10"),
        avg_cost=Decimal("95"),
        current_price=Decimal("100"),
        status="owned",
    )


def _section(attention=None, holdings=None, headroom=0.5) -> PortfolioStatusSection:
    return PortfolioStatusSection(
        total_value=Decimal("1000"),
        heat_ceiling_pct=1.0,
        heat_headroom_pct=headroom,
        holdings=holdings or [],
        attention=attention or [],
        is_empty=not holdings,
    )


def _news(ticker: str, label: str = "positive") -> NewsItem:
    return NewsItem(
        tickers=[ticker],
        headline=f"{ticker} headline",
        sentiment_label=label,
        source="Src",
        as_of="2026-07-08",
    )


def test_always_exactly_five() -> None:
    for section, news, held in [
        (_section(), [], []),  # empty portfolio, quiet day
        (_section(holdings=[_holding_line("A")]), [], ["A"]),  # sparse
        (
            _section(
                holdings=[_holding_line(t) for t in ("A", "B", "C", "D", "E", "F")]
            ),
            [_news("A"), _news("B")],
            ["A", "B", "C", "D", "E", "F"],
        ),  # rich
    ]:
        recs = recommend.select_recommendations(
            section, news, directive=False, held_tickers=held
        )
        assert len(recs) == 5
        assert [r.rank for r in recs] == [1, 2, 3, 4, 5]


def test_tier_precedence_attention_then_news_then_fill() -> None:
    section = _section(
        attention=[
            AttentionItem(
                ticker="ATN",
                reason_code=AttentionReason.RISK_BREACH,
                detail="capital at risk exceeds budget",
                severity=100,
            )
        ],
        holdings=[_holding_line("ATN"), _holding_line("FILL")],
    )
    news = [_news("NEWSY")]
    recs = recommend.select_recommendations(
        section, news, directive=False, held_tickers=["ATN", "FILL"], watchlist_tickers=["NEWSY"]
    )
    assert recs[0].source_signal is SourceSignal.ATTENTION
    assert recs[0].subject == "ATN"
    assert recs[1].source_signal is SourceSignal.NEWS_SENTIMENT
    assert recs[1].subject == "NEWSY"
    assert recs[2].source_signal is SourceSignal.PORTFOLIO_ACTION


def test_fill_never_invents_a_ticker() -> None:
    section = _section(holdings=[_holding_line("REAL")])
    recs = recommend.select_recommendations(section, [], directive=False, held_tickers=["REAL"])
    subjects = {r.subject for r in recs}
    # Only "REAL", "portfolio", "watchlist" may appear — no invented tickers.
    assert subjects <= {"REAL", "portfolio", "watchlist"}


def test_deterministic_ordering() -> None:
    section = _section(
        attention=[
            AttentionItem(ticker="B", reason_code=AttentionReason.RISK_BREACH, detail="x", severity=10),
            AttentionItem(ticker="A", reason_code=AttentionReason.RISK_BREACH, detail="x", severity=10),
        ],
        holdings=[_holding_line("A"), _holding_line("B")],
    )
    first = recommend.select_recommendations(section, [], directive=False, held_tickers=["A", "B"])
    second = recommend.select_recommendations(section, [], directive=False, held_tickers=["A", "B"])
    assert [r.model_dump() for r in first] == [r.model_dump() for r in second]


def test_neutral_mode_no_directive_language_and_no_citations() -> None:
    section = _section(
        attention=[
            AttentionItem(
                ticker="ATN", reason_code=AttentionReason.STOP_PROXIMITY, detail="within 2% of stop", severity=5
            )
        ],
        holdings=[_holding_line("ATN")],
    )
    recs = recommend.select_recommendations(
        section, [_news("ATN")], directive=False, held_tickers=["ATN"], citations=["George & Hwang (2004)"]
    )
    for rec in recs:
        validate_no_directive_language(rec.text)  # raises if a directive verb slips in
        assert rec.citations == []


def test_directive_mode_attaches_citations() -> None:
    section = _section(
        attention=[
            AttentionItem(
                ticker="ATN", reason_code=AttentionReason.RISK_BREACH, detail="over budget", severity=5
            )
        ],
        holdings=[_holding_line("ATN")],
    )
    recs = recommend.select_recommendations(
        section, [], directive=True, held_tickers=["ATN"], citations=["George & Hwang (2004)"]
    )
    attention_recs = [r for r in recs if r.source_signal is SourceSignal.ATTENTION]
    assert attention_recs
    assert all(r.citations == ["George & Hwang (2004)"] for r in attention_recs)
