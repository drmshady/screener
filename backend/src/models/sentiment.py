from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class SourceClass(StrEnum):
    NEWS = "news"
    FILING_8K = "filing_8k"
    EARNINGS = "earnings"
    ANALYST_OPINION = "analyst_opinion"
    SOCIAL = "social"


class SentimentLabel(StrEnum):
    POSITIVE = "positive"
    MIXED = "mixed"
    NEGATIVE = "negative"
    NO_SIGNAL = "no_signal"


class NarrativeSource(StrEnum):
    MODEL = "model"
    TEMPLATE = "template"
    ABSENT = "absent"


class BudgetState(StrEnum):
    OK = "ok"
    BUDGET_EXHAUSTED = "budget_exhausted"
    UNAVAILABLE = "unavailable"


class SelectionOrigin(StrEnum):
    SCREENER = "screener"
    HOLDING = "holding"
    MANUAL = "manual"


class SourceItem(BaseModel):
    id: str
    source_class: SourceClass
    title: str
    publisher: str | None = None
    published_at: datetime
    reference_url: str | None = None
    is_stale: bool = False
    score: float | None = None


class NarrativeRisk(BaseModel):
    score: int = Field(ge=0, le=100)
    label: str
    signals: list[str] = Field(default_factory=list)


class SentimentReport(BaseModel):
    ticker: str
    origin: SelectionOrigin
    label: SentimentLabel
    label_basis: str = ""
    sentiment_composite: float | None = None
    narrative_risk: NarrativeRisk | None = None
    narrative: str = ""
    narrative_source: NarrativeSource
    budget_state: BudgetState
    source_classes_present: list[str] = Field(default_factory=list)
    source_classes_omitted: list[str] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)
    fingerprint: str
    resolution: str | None = None

    @field_validator("ticker")
    @classmethod
    def _uppercase_ticker(cls, value: str) -> str:
        return value.strip().upper()


class Selection(BaseModel):
    ticker: str
    origin: SelectionOrigin
    as_of: str | None = None

    @field_validator("ticker")
    @classmethod
    def _clean_ticker(cls, value: str) -> str:
        return value.strip().upper()


class ReportRequest(BaseModel):
    selections: list[Selection] = Field(default_factory=list)


class SpendLedger(BaseModel):
    period: str
    estimated_spend_usd: Decimal = Decimal("0")
    cap_usd: Decimal = Decimal("5.00")
