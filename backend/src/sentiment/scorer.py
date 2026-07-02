from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..lib import flags
from ..models.sentiment import SentimentLabel

MODEL_DIR = Path(__file__).resolve().parents[2] / "data" / "finbert_onnx"

POSITIVE_TERMS = {
    "accelerate",
    "beat",
    "beats",
    "growth",
    "improve",
    "improves",
    "improved",
    "record",
    "raise",
    "raises",
    "raised",
    "strong",
    "upgrade",
}
NEGATIVE_TERMS = {
    "accounting",
    "cut",
    "cuts",
    "decline",
    "fraud",
    "investigation",
    "lawsuit",
    "probe",
    "restatement",
    "sec",
    "weak",
}


@dataclass(frozen=True)
class ScoreResult:
    label: SentimentLabel
    score: float | None
    basis: str
    item_scores: tuple[float, ...]
    scorer_id: str


def score_texts(texts: list[str] | tuple[str, ...]) -> ScoreResult:
    cleaned = tuple(text.strip() for text in texts if text and text.strip())
    if not cleaned:
        return ScoreResult(
            label=SentimentLabel.NO_SIGNAL,
            score=None,
            basis="No qualifying sourced text.",
            item_scores=(),
            scorer_id=flags.sentiment_scorer(),
        )
    if flags.sentiment_scorer() == "finbert" and _finbert_available():
        return _score_finbert(cleaned)
    return _score_lexicon(cleaned, fallback=flags.sentiment_scorer() == "finbert")


def _score_lexicon(texts: tuple[str, ...], *, fallback: bool) -> ScoreResult:
    scores: list[float] = []
    pos_total = 0
    neg_total = 0
    for text in texts:
        words = set(re.findall(r"[a-z]+", text.lower()))
        pos = len(words & POSITIVE_TERMS)
        neg = len(words & NEGATIVE_TERMS)
        pos_total += pos
        neg_total += neg
        denom = max(pos + neg, 1)
        scores.append((pos - neg) / denom)
    mean = sum(scores) / len(scores)
    label = _label_from_counts(pos_total, neg_total, mean)
    prefix = "FinBERT unavailable; lexicon fallback" if fallback else "Lexicon"
    return ScoreResult(
        label=label,
        score=round(mean, 6),
        basis=f"{prefix} score {mean:+.2f} from {pos_total} positive and {neg_total} negative term hits.",
        item_scores=tuple(round(score, 6) for score in scores),
        scorer_id="lexicon-v1" if not fallback else "finbert-fallback-lexicon-v1",
    )


def _label_from_counts(pos: int, neg: int, mean: float) -> SentimentLabel:
    if pos == 0 and neg == 0:
        return SentimentLabel.MIXED
    if pos > 0 and neg > 0:
        return SentimentLabel.MIXED
    if mean >= 0.25:
        return SentimentLabel.POSITIVE
    if mean <= -0.25:
        return SentimentLabel.NEGATIVE
    return SentimentLabel.MIXED


@lru_cache(maxsize=1)
def _finbert_available() -> bool:
    return (MODEL_DIR / "model.onnx").exists()


def _score_finbert(texts: tuple[str, ...]) -> ScoreResult:
    # The ONNX runtime path is intentionally lazy and isolated. If the baked
    # files are present but loading fails on a host, deterministic lexicon scoring
    # keeps the report usable instead of breaking the request.
    try:
        import numpy as np
        from tokenizers import Tokenizer

        session = _finbert_session()
        tokenizer = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
        encoded = tokenizer.encode_batch(list(texts))
        max_len = max(len(item.ids) for item in encoded)
        input_ids = np.array([item.ids + [0] * (max_len - len(item.ids)) for item in encoded], dtype=np.int64)
        attention_mask = np.array(
            [item.attention_mask + [0] * (max_len - len(item.attention_mask)) for item in encoded],
            dtype=np.int64,
        )
        # Feed only the inputs THIS exported graph declares. FinBERT (a BERT model)
        # exported via Optimum requires token_type_ids; omitting it made session.run
        # raise "Required inputs (token_type_ids) are missing", which the except
        # below swallowed into a permanent lexicon fallback. token_type_ids is all
        # zeros for the single-sequence inputs we score.
        declared = {spec.name for spec in session.get_inputs()}
        feed = {"input_ids": input_ids, "attention_mask": attention_mask}
        if "token_type_ids" in declared:
            feed["token_type_ids"] = np.zeros_like(input_ids)
        feed = {name: array for name, array in feed.items() if name in declared}
        logits = session.run(None, feed)[0]
        exp = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp / exp.sum(axis=1, keepdims=True)
        # ProsusAI/finbert convention: positive, negative, neutral.
        scores = probs[:, 0] - probs[:, 1]
        mean = float(scores.mean())
        label = SentimentLabel.POSITIVE if mean >= 0.15 else SentimentLabel.NEGATIVE if mean <= -0.15 else SentimentLabel.MIXED
        return ScoreResult(
            label=label,
            score=round(mean, 6),
            basis=f"FinBERT mean score {mean:+.2f} over {len(texts)} sourced items (P(pos)-P(neg)).",
            item_scores=tuple(round(float(score), 6) for score in scores),
            scorer_id="finbert-onnx-int8-v1",
        )
    except Exception:
        return _score_lexicon(texts, fallback=True)


@lru_cache(maxsize=1)
def _finbert_session():
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return ort.InferenceSession(
        str(MODEL_DIR / "model.onnx"),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
