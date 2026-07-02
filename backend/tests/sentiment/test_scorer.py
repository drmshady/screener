from __future__ import annotations

from backend.src.models.sentiment import SentimentLabel
from backend.src.sentiment.scorer import score_texts


def test_lexicon_scores_financial_golden_fixtures(monkeypatch):
    monkeypatch.setenv("SCREENER_SENTIMENT_SCORER", "lexicon")

    assert score_texts(["Company raises guidance after record demand"]).label == SentimentLabel.POSITIVE
    assert score_texts(["SEC investigation follows accounting restatement"]).label == SentimentLabel.NEGATIVE
    assert score_texts(["Company announces investor conference participation"]).label == SentimentLabel.MIXED


def test_finbert_path_is_deterministic_when_model_missing(monkeypatch):
    monkeypatch.setenv("SCREENER_SENTIMENT_SCORER", "finbert")
    first = score_texts(["Company raises guidance after record demand"])
    second = score_texts(["Company raises guidance after record demand"])

    assert first == second
    assert first.label == SentimentLabel.POSITIVE
    assert "fallback" in first.basis.lower() or "finbert" in first.basis.lower()
