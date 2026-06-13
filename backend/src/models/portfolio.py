from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso

MONEY_QUANT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT)


def pct(value: Decimal, total: Decimal) -> float:
    if total <= 0:
        return 0.0
    return float(value / total)


class PortfolioCaps(BaseModel):
    per_position_cap_pct: float = 0.10
    per_sector_cap_pct: float = 0.25

    @field_validator("per_position_cap_pct", "per_sector_cap_pct")
    @classmethod
    def validate_positive_pct(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Caps must be greater than zero")
        return value


class SizingHolding(BaseModel):
    ticker: str
    shares: Decimal
    current_price: Decimal
    sector: str = "Unclassified"

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("Ticker is required")
        return symbol

    @field_validator("shares", "current_price")
    @classmethod
    def validate_non_negative_decimal(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("Holding values cannot be negative")
        return value


class ConcentrationFlag(BaseModel):
    kind: Literal["position", "sector"]
    label: str
    percent_of_capital: float
    cap_pct: float
    message: str


class SectorExposure(BaseModel):
    sector: str
    dollar_value: Decimal
    percent_of_capital: float
    cap_pct: float
    over_cap: bool


class PortfolioExposure(BaseModel):
    total_capital: Decimal
    total_invested: Decimal
    cash_balance: Decimal
    sectors: list[SectorExposure]
    concentration_flags: list[ConcentrationFlag]


class SizingRequest(BaseModel):
    candidate_ticker: str
    entry: Decimal
    candidate_sector: str = "Unclassified"
    total_capital: Decimal
    holdings: list[SizingHolding] = Field(default_factory=list)
    caps: PortfolioCaps = Field(default_factory=PortfolioCaps)

    @field_validator("candidate_ticker")
    @classmethod
    def normalize_candidate_ticker(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("Candidate ticker is required")
        return symbol

    @field_validator("entry", "total_capital")
    @classmethod
    def validate_positive_decimal(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Entry and total capital must be greater than zero")
        return value


class SizingResponse(BaseModel):
    suggested_shares: int
    suggested_position_value: Decimal
    resulting_position_pct_of_capital: float
    resulting_sector_pct_of_capital: float
    caps_respected: bool
    reasoning: str
    data_as_of: str = Field(default_factory=utc_now_iso)
    disclaimer: str = DISCLAIMER_TEXT


class PortfolioQuoteRequestItem(BaseModel):
    ticker: str
    strategy_slug: str = "midterm_52w_high_momentum"

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("Ticker is required")
        return symbol


class PortfolioQuotesRequest(BaseModel):
    holdings: list[PortfolioQuoteRequestItem] = Field(default_factory=list)


class PortfolioQuote(BaseModel):
    ticker: str
    name: str
    sector: str
    strategy_slug: str
    latest_price: Decimal | None = None
    entry: Decimal | None = None
    stop_loss: Decimal | None = None
    tighter_stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    is_stale: bool = False
    data_notes: list[str] = Field(default_factory=list)
    data_as_of: str


class PortfolioQuotesResponse(BaseModel):
    quotes: list[PortfolioQuote]
    data_as_of: str = Field(default_factory=utc_now_iso)
    disclaimer: str = DISCLAIMER_TEXT
