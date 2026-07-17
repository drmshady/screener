"""Pydantic v2 entities for the Daily AI Portfolio Brief (feature 018).

These are **synthesis containers** over existing screener outputs — no new
financial field is computed here (FR-002). Money/percent fields reuse the
`models/portfolio.py` conventions (`Decimal` money). The determinism contract
(FR-013/SC-005) is encoded in `BriefModel.content_hash`, which hashes every
field EXCEPT the presentational `generated_at`, so two runs on the same
snapshot + portfolio compare equal.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso


# --- Enums -----------------------------------------------------------------


class AttentionReason(str, Enum):
    """Why a holding is flagged for attention, in ranker precedence order."""

    RISK_BREACH = "risk_breach"
    HEAT_BREACH = "heat_breach"
    STOP_PROXIMITY = "stop_proximity"
    STAGE_CHANGE = "stage_change"


class SubjectKind(str, Enum):
    HOLDING = "holding"
    WATCHLIST = "watchlist"
    PORTFOLIO = "portfolio"


class SourceSignal(str, Enum):
    """Which ranking tier produced a recommendation (auditable, FR-005)."""

    ATTENTION = "attention"
    NEWS_SENTIMENT = "news_sentiment"
    PORTFOLIO_ACTION = "portfolio_action"


class DeliveryStatus(str, Enum):
    DELIVERED = "delivered"
    SKIPPED = "skipped"
    FAILED = "failed"


# --- Section entities ------------------------------------------------------


class HoldingLine(BaseModel):
    """One per-holding row in the portfolio-status section."""

    ticker: str
    quantity: Decimal
    avg_cost: Decimal
    current_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    unrealized_pnl_pct: float | None = None
    status: str


class AttentionItem(BaseModel):
    """One holding flagged as needing attention.

    Ordered by the same precedence the recommendation ranker uses
    (risk/heat breach > stop proximity > pipeline stage change).
    """

    ticker: str
    reason_code: AttentionReason
    detail: str
    severity: int


class PortfolioStatusSection(BaseModel):
    total_value: Decimal
    realized_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    total_pnl: Decimal | None = None
    win_rate: float | None = None
    total_capital_at_risk_pct: float = 0.0
    heat_ceiling_pct: float = 0.0
    heat_headroom_pct: float = 0.0
    holdings: list[HoldingLine] = Field(default_factory=list)
    attention: list[AttentionItem] = Field(default_factory=list)
    is_empty: bool = False


class NewsItem(BaseModel):
    """A single dated news/sentiment signal mapped to the ticker(s) it affects.

    Sourced from the feature-014 pipeline; not re-derived here.
    """

    tickers: list[str] = Field(default_factory=list)
    headline: str
    sentiment_label: str | None = None
    source: str
    as_of: str
    narrative_risk_label: str | None = None


class MarketContextLine(BaseModel):
    regime: str
    regime_detail: str
    market_events: list[str] = Field(default_factory=list)
    source: str
    as_of: str


class RecommendationItem(BaseModel):
    """One of exactly five prioritized entries. Wording gated by `directive`."""

    rank: int
    subject: str
    subject_kind: SubjectKind
    reason: str
    source_signal: SourceSignal
    citations: list[str] = Field(default_factory=list)
    text: str


# --- Assembled brief -------------------------------------------------------


class BriefModel(BaseModel):
    """The fully-assembled, deterministic content for one target session.

    Produced by `brief/assemble.py`, consumed by `brief/render.py`. The
    exactly-five recommendation invariant (FR-005, SC-003) is enforced at
    construction. `content_hash` excludes `generated_at` (FR-013).
    """

    target_session: str
    generated_at: str = Field(default_factory=utc_now_iso)
    portfolio: PortfolioStatusSection
    news: list[NewsItem] = Field(default_factory=list)
    market_context: MarketContextLine | None = None
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    directive: bool = False
    data_as_of: str
    disclaimer: str = DISCLAIMER_TEXT
    warnings: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_exactly_five(self) -> "BriefModel":
        if len(self.recommendations) != 5:
            raise ValueError(
                "BriefModel requires exactly five recommendations "
                f"(got {len(self.recommendations)}); the ranker fills to five "
                "(FR-005, SC-003)."
            )
        return self

    def content_hash(self) -> str:
        """SHA-256 over the determinism-relevant fields (excludes `generated_at`).

        Lets `GET /brief/status` and tests assert that the same snapshot +
        portfolio yields a byte-identical brief (FR-013/SC-005).
        """
        payload = self.model_dump(mode="json", exclude={"generated_at"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- Delivery run record ---------------------------------------------------


class BriefDeliveryRecord(BaseModel):
    """Persisted in `brief_runs.json`; powers idempotency (FR-010) and status."""

    target_session: str
    status: DeliveryStatus
    recipient: str
    reason: str | None = None
    attempts: int = 0
    directive: bool = False
    content_hash: str
    timestamp: str = Field(default_factory=utc_now_iso)


# --- API response models ---------------------------------------------------


class BriefRunResponse(BaseModel):
    status: Literal["delivered", "skipped", "failed", "dry_run"]
    target_session: str
    record: BriefDeliveryRecord | None = None
    brief: BriefModel | None = None
    data_as_of: str = Field(default_factory=utc_now_iso)
    disclaimer: str = DISCLAIMER_TEXT


class BriefStatusResponse(BaseModel):
    enabled: bool
    last_run: BriefDeliveryRecord | None = None
    data_as_of: str = Field(default_factory=utc_now_iso)
    disclaimer: str = DISCLAIMER_TEXT
