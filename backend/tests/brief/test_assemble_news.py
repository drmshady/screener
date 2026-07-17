"""Feature 018 T022 (US2) — news-section assemble.

Held + watched ticker mapping (held before watched), the since-last-delivered
window (older items dropped, Decision 7), empty ⇒ no items ("nothing material"
copy is rendered downstream), and fail-soft (no reports ⇒ empty).
"""
from __future__ import annotations

from datetime import datetime, timezone

from backend.src.api import portfolio as portfolio_api
from backend.src.brief import assemble
from backend.src.models.sentiment import (
    NarrativeRisk,
    SelectionOrigin,
    SentimentLabel,
    SentimentReport,
    SourceClass,
    SourceItem,
)


def _report(ticker: str, label: SentimentLabel, published: datetime) -> SentimentReport:
    return SentimentReport(
        ticker=ticker,
        origin=SelectionOrigin.HOLDING,
        label=label,
        label_basis="test",
        sentiment_composite=0.5,
        narrative_risk=NarrativeRisk(score=20, label="Elevated attention"),
        narrative=f"{ticker} recent context.",
        narrative_source="template",
        budget_state="ok",
        source_classes_present=["news"],
        sources=[
            SourceItem(
                id=f"{ticker}-1",
                source_class=SourceClass.NEWS,
                title=f"{ticker} headline",
                publisher="Acme Newswire",
                published_at=published,
            )
        ],
        fingerprint=f"sha256:{ticker}",
    )


def _patch_reports(monkeypatch, mapping) -> None:
    monkeypatch.setattr(
        portfolio_api,
        "_resolve_or_generate_sentiment",
        lambda tickers, *, origin: {t: mapping[t] for t in tickers if t in mapping},
    )


def test_maps_held_before_watched(monkeypatch) -> None:
    now = datetime(2026, 7, 8, 12, tzinfo=timezone.utc)
    _patch_reports(
        monkeypatch,
        {
            "WAT": _report("WAT", SentimentLabel.POSITIVE, now),
            "HELD": _report("HELD", SentimentLabel.NEGATIVE, now),
        },
    )
    items = assemble.build_news(["HELD"], ["WAT"], since="2026-07-01")
    assert [i.tickers[0] for i in items] == ["HELD", "WAT"]
    for item in items:
        assert item.source == "Acme Newswire"
        assert item.as_of == "2026-07-08"


def test_no_signal_reports_excluded(monkeypatch) -> None:
    now = datetime(2026, 7, 8, 12, tzinfo=timezone.utc)
    _patch_reports(monkeypatch, {"HELD": _report("HELD", SentimentLabel.NO_SIGNAL, now)})
    assert assemble.build_news(["HELD"], [], since=None) == []


def test_older_than_window_dropped(monkeypatch) -> None:
    old = datetime(2026, 6, 1, 12, tzinfo=timezone.utc)
    _patch_reports(monkeypatch, {"HELD": _report("HELD", SentimentLabel.POSITIVE, old)})
    # since is after the item's publish date ⇒ dropped (not repeated).
    assert assemble.build_news(["HELD"], [], since="2026-07-01") == []


def test_empty_tickers_returns_empty(monkeypatch) -> None:
    _patch_reports(monkeypatch, {})
    assert assemble.build_news([], [], since=None) == []


def test_fail_soft_when_resolution_raises(monkeypatch) -> None:
    def _boom(tickers, *, origin):
        raise RuntimeError("provider down")

    monkeypatch.setattr(portfolio_api, "_resolve_or_generate_sentiment", _boom)
    assert assemble.build_news(["HELD"], ["WAT"], since=None) == []
