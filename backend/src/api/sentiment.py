from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..lib import flags
from ..models.sentiment import (
    BudgetState,
    NarrativeSource,
    ReportRequest,
    Selection,
    SelectionOrigin,
    SentimentLabel,
    SentimentReport,
    SourceItem,
)
from ..sentiment.budget import BudgetGuard as _BudgetGuard
from ..sentiment.composite import recency_weighted_composite
from ..sentiment.narrative import build_template_narrative, validate_no_directive_language
from ..sentiment.narrative_risk import assess_narrative_risk
from ..sentiment.scorer import score_texts
from ..sentiment.sources import collect_sources
from ..sentiment.store import CapturedReportStore as _CapturedReportStore

router = APIRouter(prefix="/sentiment", tags=["sentiment"])

# Kept as module globals so tests can inject temp stores and avoid live providers.
CapturedReportStore = _CapturedReportStore
BudgetGuard = _BudgetGuard

_OMITTABLE_CLASSES = ["filing_8k", "earnings", "analyst_opinion", "social"]


class SentimentReportResponse(BaseModel):
    reports: list[SentimentReport]
    period_spend_usd: str
    monthly_cap_usd: str


@router.post("/report", response_model=SentimentReportResponse)
def post_sentiment_report(request: ReportRequest) -> SentimentReportResponse:
    if not request.selections:
        raise HTTPException(status_code=400, detail="Select at least one stock.")

    store = CapturedReportStore()
    budget = BudgetGuard()
    reports = [
        _safe_report_for_selection(selection, store=store, budget=budget)
        for selection in request.selections
    ]
    ledger = budget.current()
    return SentimentReportResponse(
        reports=reports,
        period_spend_usd=_decimal_text(ledger.estimated_spend_usd),
        monthly_cap_usd=_money_text(ledger.cap_usd),
    )


def _safe_report_for_selection(
    selection: Selection,
    *,
    store: _CapturedReportStore,
    budget: _BudgetGuard,
) -> SentimentReport:
    try:
        return _report_for_selection(selection, store=store, budget=budget)
    except Exception:
        return _unavailable_report(selection)


def _report_for_selection(
    selection: Selection,
    *,
    store: _CapturedReportStore,
    budget: _BudgetGuard,
) -> SentimentReport:
    now = _capture_time(selection)
    sources = collect_sources(selection.ticker, now=now)
    fingerprint = _fingerprint(selection, sources)
    cached = store.get(fingerprint)
    if cached is not None:
        return cached

    if not sources:
        report = _no_signal_report(selection, fingerprint=fingerprint)
        if selection.origin != SelectionOrigin.MANUAL:
            store.put(report)
        return report

    score = score_texts([source.title for source in sources])
    scored_sources = _with_item_scores(sources, score.item_scores)
    present = sorted({source.source_class.value for source in scored_sources})
    budget_state = BudgetState.OK
    narrative_source = NarrativeSource.TEMPLATE

    if not budget.reserve_if_allowed(Decimal("0")):
        budget_state = BudgetState.BUDGET_EXHAUSTED

    narrative = build_template_narrative(selection.ticker, scored_sources)
    validate_no_directive_language(score.basis)
    risk = assess_narrative_risk(scored_sources, now=now)
    validate_no_directive_language(risk.label)

    report = SentimentReport(
        ticker=selection.ticker,
        origin=selection.origin,
        label=score.label,
        label_basis=score.basis,
        sentiment_composite=recency_weighted_composite(scored_sources, now=now),
        narrative_risk=risk,
        narrative=narrative,
        narrative_source=narrative_source,
        budget_state=budget_state,
        source_classes_present=present,
        source_classes_omitted=[name for name in _OMITTABLE_CLASSES if name not in present],
        sources=scored_sources,
        fingerprint=fingerprint,
    )
    store.put(report)
    return report


def _no_signal_report(selection: Selection, *, fingerprint: str) -> SentimentReport:
    resolution = "symbol_not_found" if selection.origin == SelectionOrigin.MANUAL else None
    narrative = f"{selection.ticker} has no qualifying sourced sentiment items in the current capture."
    return SentimentReport(
        ticker=selection.ticker,
        origin=selection.origin,
        label=SentimentLabel.NO_SIGNAL,
        label_basis="No qualifying sourced text.",
        sentiment_composite=None,
        narrative_risk=None,
        narrative=narrative,
        narrative_source=NarrativeSource.ABSENT,
        budget_state=BudgetState.UNAVAILABLE if resolution else BudgetState.OK,
        source_classes_present=[],
        source_classes_omitted=[*_OMITTABLE_CLASSES, "news"],
        sources=[],
        fingerprint=fingerprint,
        resolution=resolution,
    )


def _unavailable_report(selection: Selection) -> SentimentReport:
    return SentimentReport(
        ticker=selection.ticker,
        origin=selection.origin,
        label=SentimentLabel.NO_SIGNAL,
        label_basis="Sentiment report unavailable for this selection.",
        sentiment_composite=None,
        narrative_risk=None,
        narrative=f"{selection.ticker} sentiment report is unavailable for the current capture.",
        narrative_source=NarrativeSource.ABSENT,
        budget_state=BudgetState.UNAVAILABLE,
        source_classes_present=[],
        source_classes_omitted=[*_OMITTABLE_CLASSES, "news"],
        sources=[],
        fingerprint=_fingerprint(selection, []),
        resolution="report_unavailable",
    )


def _with_item_scores(sources: list[SourceItem], scores: tuple[float, ...]) -> list[SourceItem]:
    out: list[SourceItem] = []
    for index, source in enumerate(sources):
        score = scores[index] if index < len(scores) else source.score
        out.append(source.model_copy(update={"score": score}))
    return out


def _fingerprint(selection: Selection, sources: list[SourceItem]) -> str:
    parts = [
        selection.ticker,
        selection.origin.value,
        selection.as_of or "current",
        flags.sentiment_scorer(),
        flags.sentiment_llm_provider(),
        flags.sentiment_llm_model() or "default-model",
        *[
            f"{source.id}:{source.published_at.isoformat()}"
            for source in sorted(sources, key=lambda item: (item.id, item.published_at))
        ],
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _capture_time(selection: Selection) -> datetime:
    if selection.as_of:
        try:
            return datetime.fromisoformat(selection.as_of).replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def _decimal_text(value: Decimal) -> str:
    return str(value)


def _money_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")
