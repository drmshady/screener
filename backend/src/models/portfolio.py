from __future__ import annotations

from datetime import date as date_type
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


class Transaction(BaseModel):
    """One buy or sell as persisted in the portfolio blob.

    The `id` field is a stable content hash computed by `portfolio/transactions.py`
    before the model is instantiated; the model stores it as-is.
    """

    id: str
    ticker: str
    action: Literal["buy", "sell"]
    quantity: Decimal
    price: Decimal
    trade_date: date_type
    fees: Decimal | None = None
    note: str | None = None
    source_row: int

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("Ticker is required")
        return symbol

    @field_validator("quantity")
    @classmethod
    def validate_positive_qty(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Quantity must be greater than zero")
        return value

    @field_validator("price")
    @classmethod
    def validate_and_quantize_price(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Price must be greater than zero")
        return money(value)

    @field_validator("fees")
    @classmethod
    def quantize_fees(cls, value: Decimal | None) -> Decimal | None:
        return money(value) if value is not None else None


class RejectedRow(BaseModel):
    """A sheet row that failed validation; always surfaced to the owner (FR-003, SC-002)."""

    source_row: int
    raw: dict[str, str]
    reason: str


class PortfolioTransactionsSlice(BaseModel):
    """Transactions sub-slice of the portfolio state blob owned by the server.

    Stored within `state` alongside the opaque frontend fields; the store
    functions read/write only these three keys, leaving the rest of the blob intact.
    """

    transactions: list[Transaction] = Field(default_factory=list)
    sheet_id: str | None = None
    sheet_range: str | None = None


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
    # Feature 011 (US3): risk-per-trade sizing needs the US2 stop; conviction
    # modulation is optional and fails open when its input is untrusted/absent
    # (contracts/sizing.md). Only one modulator is adopted by US4, but the
    # inputs for each candidate signal are threaded through so any can be wired.
    stop_loss: Decimal | None = None
    fair_value: Decimal | None = None
    fair_value_trust_flag: str | None = None
    volatility: float | None = None
    strategy_rank: int | None = None
    # Feature 016 (US2): optional cash-first hard limit. When present, the
    # suggested position is capped so `suggested_shares × entry ≤ available_cash`
    # and `binding_constraint = "available_cash"` when cash is the tightest limit.
    # Absent (None) ⇒ byte-identical to today (contracts/sizing-available-cash.md).
    available_cash: Decimal | None = None

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
    # Feature 011 (US3): risk-per-trade backbone + conviction-modulation
    # metadata (data-model.md "Sizing suggestion"). Optional/backward-compatible.
    risk_per_trade_target: Decimal | None = None
    risk_per_share: Decimal | None = None
    conviction_signal: str | None = None  # "fair_value" | "inverse_vol" | "strategy_rank" | "none"
    conviction_adjustment: str | None = None  # "none" | "boost" | "cap"
    # "risk_target" | "conviction" | "position_cap" | "sector_cap" | "portfolio_heat" |
    # "conservative_fallback" | "available_cash" (Feature 016 US2)
    binding_constraint: str | None = None
    conviction_used: bool = False
    # Feature 015 (US4): safe-fallback + portfolio-heat metadata (data-model.md §4).
    # Additive/backward-compatible; defaults keep a healthy request byte-identical.
    conservative_fallback: bool = False
    reward_to_risk: float | None = None
    portfolio_heat_after_pct: float | None = None
    data_as_of: str = Field(default_factory=utc_now_iso)
    disclaimer: str = DISCLAIMER_TEXT


class ImportRequest(BaseModel):
    """Body for POST /portfolio/import.

    `rows` are raw sheet rows — each dict is keyed by either descriptive header
    names (Date/Type/Stock/…) or canonical field names; values are raw strings
    as returned by the Google Sheets API. `source_row` (int) must be present in
    each row. The server performs all normalisation and validation.
    """

    rows: list[dict[str, object]]
    sheet_id: str | None = None
    sheet_range: str | None = None


class TransactionsRequest(BaseModel):
    """Body for POST /portfolio/transactions (manual in-app buy/sell entry).

    `rows` are raw transaction rows in the same shape the import validator accepts
    (ticker, action ∈ {buy, sell}, quantity, price, trade_date, optional fees/note).
    The server validates + assigns the stable content-hash `id` and appends to the
    retained transactions list (Feature 016 US4). No sheet metadata.
    """

    rows: list[dict[str, object]]


class ImportResult(BaseModel):
    """Response from POST /portfolio/import."""

    accepted_count: int
    duplicate_count: int
    rejected: list[RejectedRow]
    transactions_total: int
    data_as_of: str = Field(default_factory=utc_now_iso)
    disclaimer: str = DISCLAIMER_TEXT


class Holding(BaseModel):
    """One owner position derived from accepted transactions.

    Computed (not persisted); recomputed on every /portfolio/holdings call.
    Phase 3 (US1) includes the cost-basis facts; US2 adds levels and US3 adds risk.
    """

    ticker: str
    net_quantity: Decimal
    avg_cost: Decimal
    cost_basis: Decimal
    earliest_buy_date: date_type
    most_recent_buy_date: date_type
    realized_pl: Decimal
    status: Literal["open", "closed", "anomalous"]


class LevelBlock(BaseModel):
    entry: Decimal | None = None
    stop_loss: Decimal | None = None
    tighter_stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    risk_distance: Decimal | None = None
    reward_distance: Decimal | None = None
    reward_ceiling_basis: str | None = None
    bounds_applied: list[str] = Field(default_factory=list)
    levels_state: Literal["ok", "insufficient_data"] = "insufficient_data"
    rationale: str
    distance_to_stop_pct: float | None = None
    distance_to_target_pct: float | None = None
    status: Literal[
        "holding",
        "stop_breached",
        "target_reached",
        "gains_protected",
        "insufficient_data",
    ]


class HoldingLevels(BaseModel):
    original_plan: LevelBlock
    current_condition: LevelBlock
    # Feature 015 (US3): a third, current-price-anchored trailing block derived
    # from the chandelier exit. None when price <= cost or the chandelier value is
    # missing (graceful degradation, never a looser fabricated level — FR-008).
    trailing: LevelBlock | None = None


class HoldingRisk(BaseModel):
    recommended_shares: int
    recommended_value: Decimal
    actual_shares: Decimal
    actual_value: Decimal
    actual_capital_at_risk: Decimal
    actual_capital_at_risk_pct: float
    per_trade_risk_budget: Decimal
    over_risk: bool
    binding_constraint: Literal["per_trade_budget", "position_cap", "sector_cap"] | None = None
    sizing_reasoning: str
    fail_open: bool = False


class PortfolioHolding(Holding):
    priceable: bool = False
    sector: str = "Unclassified"
    current_price: Decimal | None = None
    unrealized_pl: Decimal | None = None
    unrealized_pl_pct: float | None = None
    data_notes: list[str] = Field(default_factory=list)
    data_as_of: str | None = None
    levels: HoldingLevels | None = None
    risk: HoldingRisk | None = None


class PortfolioHoldingsRequest(BaseModel):
    total_capital: Decimal
    caps: PortfolioCaps = Field(default_factory=PortfolioCaps)
    strategy_slug: str = "midterm_52w_high_momentum"
    # Feature 016 (US2): optional cash-first limit threaded into each holding's
    # recommended size (size_position). Absent ⇒ byte-identical to today.
    available_cash: Decimal | None = None

    @field_validator("total_capital")
    @classmethod
    def validate_positive_capital(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Total capital must be greater than zero")
        return money(value)


class RealizedTrade(BaseModel):
    """One FIFO realized round-trip (a sell matched against an earlier buy lot).

    Feature 016 (US4). Informational only — never feeds sizing/levels/board.
    """

    ticker: str
    shares: Decimal
    buy_date: date_type
    sell_date: date_type
    proceeds: Decimal
    cost_basis: Decimal
    fees: Decimal
    realized_pnl: Decimal
    outcome: Literal["win", "loss", "flat"]
    holding_days: int


class RealizedPnl(BaseModel):
    """Portfolio-level realized P&L: the FIFO round-trip history plus aggregates.

    All aggregates are None/0 when there are no closed lots ⇒ byte-identical to
    today's buy-only portfolios (Feature 016 US4).
    """

    trades: list[RealizedTrade] = Field(default_factory=list)
    realized_pnl: Decimal | None = None
    closed_trade_count: int = 0
    winning_trade_count: int = 0
    win_rate: float | None = None


class PortfolioTotals(BaseModel):
    total_invested: Decimal
    total_capital_at_risk: Decimal = Decimal("0.00")
    total_capital_at_risk_pct: float = 0.0
    # Feature 015 (US4/US7): aggregate open-risk (portfolio heat) ceiling and
    # remaining headroom, populated by the holdings assembly path (FR-010/FR-019).
    heat_ceiling_pct: float = 0.0
    heat_headroom_pct: float = 0.0
    # Feature 016 (US4): additive/optional win/loss + mark-to-market P&L.
    # All None/0 when there are no closed lots ⇒ byte-identical to today.
    realized_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    total_pnl: Decimal | None = None
    win_rate: float | None = None
    closed_trade_count: int = 0
    winning_trade_count: int = 0


class PortfolioHoldingsResponse(BaseModel):
    holdings: list[PortfolioHolding]
    totals: PortfolioTotals
    # Feature 016 (US4): FIFO realized round-trip history (empty when no closed
    # lots). Informational only; the table renders win/loss detail from it.
    realized_trades: list[RealizedTrade] = Field(default_factory=list)
    data_as_of: str = Field(default_factory=utc_now_iso)
    disclaimer: str = DISCLAIMER_TEXT


class HoldingAdvisorPromptResponse(BaseModel):
    """Response from POST /portfolio/holdings/{ticker}/advisor-prompt."""

    ticker: str
    strategy: str
    personal_use_directive: bool
    prompt: str
    data_as_of: str = Field(default_factory=utc_now_iso)
    disclaimer: str = DISCLAIMER_TEXT


class PortfolioAdvisorPromptResponse(BaseModel):
    """Response from POST /portfolio/holdings/advisor-prompt (whole portfolio)."""

    strategy: str
    holding_count: int
    personal_use_directive: bool
    prompt: str
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
    # Feature 011 (US3): so the frontend can pass a trusted fair value into the
    # /sizing request without a second lookup. Optional/backward-compatible.
    fair_value: Decimal | None = None
    fair_value_trust_flag: str | None = None
    is_stale: bool = False
    data_notes: list[str] = Field(default_factory=list)
    data_as_of: str


class PortfolioQuotesResponse(BaseModel):
    quotes: list[PortfolioQuote]
    data_as_of: str = Field(default_factory=utc_now_iso)
    disclaimer: str = DISCLAIMER_TEXT
