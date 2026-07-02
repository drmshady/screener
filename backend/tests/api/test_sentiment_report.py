from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.src.api.app import app
from backend.src.models.sentiment import SentimentLabel, SourceClass, SourceItem


client = TestClient(app)


def _source(ticker: str) -> SourceItem:
    return SourceItem(
        id=f"fixture:{ticker}:1",
        source_class=SourceClass.NEWS,
        title=f"{ticker} raises guidance after strong demand",
        publisher="Fixture News",
        published_at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        reference_url=f"https://example.test/{ticker}",
        is_stale=False,
    )


def test_sentiment_report_contract_failsoft_capture_and_scope(monkeypatch, tmp_path) -> None:
    from backend.src.api import sentiment as sentiment_api
    from backend.src.sentiment.scorer import ScoreResult

    calls: list[str] = []

    def fake_collect_sources(ticker: str, **_kwargs):
        calls.append(ticker)
        if ticker == "NVDA":
            return [_source(ticker)]
        return []

    def fake_score_texts(texts):
        assert list(texts) == ["NVDA raises guidance after strong demand"]
        return ScoreResult(
            label=SentimentLabel.POSITIVE,
            score=0.42,
            basis="Lexicon score +1.00 from 2 positive and 0 negative term hits.",
            item_scores=(0.42,),
            scorer_id="fixture-scorer-v1",
        )

    monkeypatch.setattr(sentiment_api, "collect_sources", fake_collect_sources)
    monkeypatch.setattr(sentiment_api, "score_texts", fake_score_texts)
    monkeypatch.setattr(
        sentiment_api,
        "CapturedReportStore",
        lambda: sentiment_api._CapturedReportStore(tmp_path / "reports.sqlite"),
    )
    monkeypatch.setattr(
        sentiment_api,
        "BudgetGuard",
        lambda: sentiment_api._BudgetGuard(tmp_path / "spend.json"),
    )

    empty = client.post("/sentiment/report", json={"selections": []})
    assert empty.status_code == 400
    assert empty.json()["detail"] == "Select at least one stock."

    body = {
        "selections": [
            {"ticker": "NVDA", "origin": "screener", "as_of": "2026-07-01"},
            {"ticker": "ZZZZZZ", "origin": "manual"},
        ]
    }
    first = client.post("/sentiment/report", json=body)
    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["data_as_of"]
    assert payload["disclaimer"]
    assert payload["period_spend_usd"] == "0"
    assert payload["monthly_cap_usd"] == "5.00"
    assert [report["ticker"] for report in payload["reports"]] == ["NVDA", "ZZZZZZ"]

    nvda = payload["reports"][0]
    assert nvda["label"] == "positive"
    assert nvda["origin"] == "screener"
    assert nvda["sources"][0]["score"] == 0.42
    assert nvda["fingerprint"].startswith("sha256:")
    assert "buy" not in nvda["narrative"].lower()

    unresolved = payload["reports"][1]
    assert unresolved["label"] == "no_signal"
    assert unresolved["resolution"] == "symbol_not_found"
    assert unresolved["budget_state"] == "unavailable"
    assert unresolved["sources"] == []

    second = client.post("/sentiment/report", json=body)
    assert second.status_code == 200, second.text
    assert second.json()["reports"][0] == nvda
    assert second.json()["period_spend_usd"] == "0"
    assert calls == ["NVDA", "ZZZZZZ", "NVDA", "ZZZZZZ"]
