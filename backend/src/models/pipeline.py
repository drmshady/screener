from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from .portfolio import PortfolioCaps, SizingResponse


class FitFacts(BaseModel):
    """The independent boolean facts ``score_fit`` consumes (pure input).

    The API layer computes each fact from existing outputs (entry timing, the
    real ``size_position`` result, regime favorability) — ``score_fit`` itself
    performs no I/O so it is deterministic and trivially golden-fixture tested.
    """

    entry_ready: bool
    meaningful_size_survives: bool
    heat_headroom_ok: bool
    sector_room_ok: bool
    not_overconcentrated: bool
    regime_allows_entries: bool
    reward_to_risk_ok: bool
    cash_sufficient: bool


class FitResult(BaseModel):
    """The pure synthesis output for one candidate.

    ``score`` is an internal, deterministic weighted sum used only for sort
    order; the UI shows ``fit_band`` + ``failed_facts`` + the neutral
    ``rationale``, never the raw number. ``directive_label`` is a *separate*
    optional field populated only when ``personal_use_directive()`` is on AND
    the app is not hosted (pydantic ``exclude_if`` keeps it out of the neutral /
    hosted payload entirely).
    """

    score: int
    fit_band: Literal["strong_fit", "partial_fit", "poor_fit", "blocked"]
    facts: FitFacts
    failed_facts: list[str] = Field(default_factory=list)
    rationale: str
    directive_label: Literal["consider_entry", "hold_off", "size_down", "pass"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class PipelineBoardItem(BaseModel):
    ticker: str
    entry_timing_state: str | None = None
    sizing_preview: SizingResponse | None = None
    fit: FitResult | None = None
    sector: str = "Unclassified"
    skipped_reason: str | None = None


class PipelineBoardResponse(BaseModel):
    items: list[PipelineBoardItem] = Field(default_factory=list)
    regime: dict | None = None
    regime_allows_new_entries: bool = False
    heat_ceiling_pct: float = 0.0
    heat_headroom_pct: float = 0.0
    available_cash: Decimal | None = None
    personal_use_directive: bool = False
    data_as_of: str = Field(default_factory=utc_now_iso)
    disclaimer: str = DISCLAIMER_TEXT


class PipelineBoardRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    strategy_slug: str = "midterm_52w_high_momentum"
    total_capital: Decimal
    available_cash: Decimal | None = None
    caps: PortfolioCaps = Field(default_factory=PortfolioCaps)
