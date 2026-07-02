from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso

RegimeName = Literal["Trending up", "Range-bound", "Trending down"]
Favorability = Literal["Favorable", "Neutral", "Unfavorable"]


class RegimeInputs(BaseModel):
    spy_close: Decimal | None = None
    spy_sma200: Decimal | None = None
    spy_above_sma200: bool | None = None
    breadth_pct_above_sma200: float | None = None
    breadth_above_count: int = 0
    breadth_eligible_count: int = 0
    breadth_total_constituents: int = 0
    price_source_name: str
    unavailable_reason: str | None = None
    breadth_source_name: str
    breadth_source_as_of: str | None = None


class StrategyFavorability(BaseModel):
    slug: str
    name: str
    favorability: Favorability
    explanation: str


class RegimeResponse(BaseModel):
    regime: RegimeName
    rule_summary: str
    inputs: RegimeInputs
    as_of_date: date
    per_strategy_favorability: list[StrategyFavorability] = Field(default_factory=list)
    data_as_of: str = Field(default_factory=utc_now_iso)
    disclaimer: str = DISCLAIMER_TEXT
