from typing import Any, Callable, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, computed_field
import pandas as pd

from backend.src.screening.integrity.contract import OutputContract


class Modification(BaseModel):
    name: str
    description: str
    citation: str


class DataIntegrityWarning(BaseModel):
    """Per-candidate serialization of a candidate-severity contract violation
    (data-model §4). Distinct from the soft-gate ``warnings: list[str]`` — a
    data-integrity warning means a figure may be wrong, not that a soft gate is
    unmet. ``reason`` travels verbatim into the advisor prompt (FR-019)."""

    figure: Optional[str] = None
    rule: str
    reason: str


class FairValueEstimate(BaseModel):
    """Per-candidate fair-value estimate (feature 011 US3, contracts/fair-value.md).

    Pure-function output, no I/O. ``trust_flag`` gates downstream use: only
    ``trusted`` estimates may feed sizing conviction or the US2 reward ceiling —
    ``unavailable``/``stale``/``out_of_range`` fail open (FR-016/018).
    """

    fair_value: Optional[float] = None
    basis: str
    source_as_of: str
    provenance: str
    trust_flag: str  # "trusted" | "unavailable" | "stale" | "out_of_range"
    margin_of_safety: Optional[float] = None


class StrategyParameter(BaseModel):
    default: Any
    min: Optional[Any] = None
    max: Optional[Any] = None
    type: str
    description: str


class BacktestSummary(BaseModel):
    data_window_start: str
    data_window_end: str
    total_return: float
    max_drawdown: float
    hit_rate: float
    avg_win: float
    avg_loss: float
    turnover: float
    source_name: str
    source_as_of: str


class Strategy(BaseModel):
    slug: str
    name: str
    timeframe: str
    citation: str
    description: str
    holding_period_days: Dict[str, int]
    parameters: Dict[str, StrategyParameter]
    regime_favorability: Dict[str, str]
    default_exclude_earnings_within_days: int
    enabled_by_default: bool
    modifications: List[Modification]
    backtest_summary: Optional[BacktestSummary] = None
    rules: Callable[[pd.DataFrame], pd.DataFrame] = Field(exclude=True)
    # Optional so contract-less strategies still load (data-model §6); momentum
    # and value declare one. Predicates are excluded from serialization.
    output_contract: Optional[OutputContract] = None

    @computed_field
    @property
    def backtest_window_meets_v1_floor(self) -> bool:
        if self.backtest_summary is None:
            return False
        start = str(self.backtest_summary.data_window_start)
        end = str(self.backtest_summary.data_window_end)
        return start <= "2008-01-01" and end >= "2023-01-01"


class ScreenRunRequest(BaseModel):
    parameters: Dict[str, Any] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)
    shariah_overrides: Dict[str, Any] = Field(default_factory=dict)
    as_of_date: Optional[str] = None


class GateResult(BaseModel):
    gate: str
    status: str  # "pass" | "fail" | "skipped"
    detail: str


class EntryComponent(BaseModel):
    name: Literal[
        "pivot_proximity",
        "trend",
        "volume_confirmation",
        "base_maturity",
        "base_depth",
        "not_extended",
    ]
    status: Literal["pass", "fail", "undetermined"]
    value: float | None = None
    reason: str


class Disqualifier(BaseModel):
    name: Literal["climax_top", "huge_gap", "short_lived_catalyst"]
    triggered: bool
    value: float | None = None
    reason: str
    forces_not_entry_ready: bool


class EntryDiagnostics(BaseModel):
    pivot: float | None = None
    base_type: (
        Literal["flat", "cup", "cup_with_handle", "double_bottom", "none"] | None
    ) = None
    base_length_weeks: float | None = None
    base_depth: float | None = None
    breakout_volume_ratio: float | None = None
    dist_above_pivot: float | None = None
    dist_above_sma_200: float | None = None


class EntryTimingClassification(BaseModel):
    state: Literal["entry_ready", "not_entry_ready", "entry_undetermined"]
    components: list[EntryComponent]
    disqualifiers: list[Disqualifier] = Field(default_factory=list)
    diagnostics: EntryDiagnostics
    summary: str


class SkippedGate(BaseModel):
    gate: str
    reason: str


class Candidate(BaseModel):
    ticker: str
    name: str
    sector: str
    strategy_slug: Optional[str] = None
    strategy_name: Optional[str] = None
    timeframe: Optional[str] = None
    current_price: str
    entry: str
    stop_loss: str
    tighter_stop_loss: Optional[str] = None
    take_profit: str
    # Feature 011 (US2): bounded-levels metadata from `derive_bounded_levels`.
    # Optional/backward-compatible — existing entry/stop_loss/tighter_stop_loss/
    # take_profit consumers keep working unchanged (contracts/risk-levels.md).
    risk_distance: Optional[float] = None
    reward_distance: Optional[float] = None
    reward_ceiling_basis: Optional[str] = None
    bounds_applied: List[str] = Field(default_factory=list)
    levels_state: Optional[str] = None
    rationale: Optional[str] = None
    rank: int
    score: float
    reason: str
    # Ranking inputs + diagnostics (so an advisor can rank/triage, not just see
    # risk geometry). Optional: some are unavailable on the free data tier.
    return_12_1: Optional[float] = None
    vol_scalar: Optional[float] = None
    dist_to_high: Optional[float] = None
    atr: Optional[float] = None
    debt_to_equity: Optional[float] = None
    fcf_ttm: Optional[float] = None
    gp_to_assets: Optional[float] = None
    asset_growth: Optional[float] = None
    # Value-composite diagnostics (midterm_value_composite). Optional/None for
    # other strategies so existing responses and contracts are unaffected.
    value_composite: Optional[float] = None
    book_to_market: Optional[float] = None
    earnings_yield: Optional[float] = None
    cashflow_yield: Optional[float] = None
    sales_yield: Optional[float] = None
    f_score: Optional[int] = None
    f_score_evaluable: Optional[int] = None
    # Feature 011 (US3): fair-value estimate + trust flag (contracts/fair-value.md).
    # Optional/None when unavailable — fails open, never blocks the candidate.
    fair_value: Optional[float] = None
    fair_value_basis: Optional[str] = None
    fair_value_trust_flag: Optional[str] = None
    fair_value_margin_of_safety: Optional[float] = None
    gate_results: List[GateResult] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    # Feature 012: additive entry-timing diagnostics and opt-in expanded
    # coverage bookkeeping. Defaults are omitted during serialization to keep
    # default-off / non-momentum payloads unchanged.
    entry_timing: EntryTimingClassification | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    skipped_gates: list[SkippedGate] = Field(
        default_factory=list, exclude_if=lambda value: not value
    )
    # Feature 008: candidate-severity contract violations (data-model §5).
    # Additive + optional, so existing API consumers are unaffected. Kept
    # separate from the soft-gate ``warnings`` above.
    data_integrity_warnings: List[DataIntegrityWarning] = Field(default_factory=list)
    data_suspect: bool = False
    shariah_compliant: Optional[bool] = None
    shariah_source_kind: Optional[str] = None
    shariah_external_source_name: Optional[str] = None
    shariah_source_as_of: Optional[str] = None
    shariah_source_url: Optional[str] = None
    shariah_user_note: Optional[str] = None
    shariah_is_stale: Optional[bool] = None
    next_earnings_date: Optional[str] = None
    days_to_earnings: Optional[int] = None
    recent_8k_count_30d: int = 0
    events_source_as_of: Optional[str] = None
    # §8 Series-integrity signals
    series_dates_ok: Optional[bool] = None
    series_max_session_move: Optional[float] = None
    seam_consistent: Optional[bool] = None
    seam_factor: Optional[float] = None
    # Whether an overlapping-bar window was actually found to verify the seam.
    # Distinguishes "verified inconsistent" (overlap found, factor unstable) from
    # "unverified" (no overlapping bars to confirm one basis).
    seam_overlap_found: Optional[bool] = None
    corporate_action_in_window: Optional[bool] = None
    adj_close_basis_used: Optional[bool] = None
    share_class_consistent: Optional[bool] = None
    material_input_freshness: Dict[str, Optional[str]] = Field(default_factory=dict)


class ScreenResult(BaseModel):
    id: str
    strategy_slug: str
    as_of_date: str
    parameters_snapshot: Dict[str, Any]
    filters_snapshot: Dict[str, Any]
    candidate_count: int
    candidates: List[Candidate]
    computed_at: str
    data_as_of: str
    disclaimer: str
    stale_sources: List[str] = Field(default_factory=list)
    data_notes: List[str] = Field(default_factory=list)
    material_input_freshness: Dict[str, Optional[str]] = Field(default_factory=dict)
    regime: Optional[str] = None
    regime_allows_new_entries: Optional[bool] = None
    regime_note: Optional[str] = None


class AnalyzeResponse(BaseModel):
    ticker: str
    name: str
    sector: str
    strategy: str
    as_of: str
    would_be_selected: bool
    current_price: str
    entry: str
    stop_loss: str
    tighter_stop_loss: Optional[str] = None
    take_profit: str
    # Feature 011 (US2): bounded-levels metadata, mirrors Candidate above.
    risk_distance: Optional[float] = None
    reward_distance: Optional[float] = None
    reward_ceiling_basis: Optional[str] = None
    bounds_applied: List[str] = Field(default_factory=list)
    levels_state: Optional[str] = None
    rationale: Optional[str] = None
    return_12_1: Optional[float] = None
    vol_scalar: Optional[float] = None
    dist_to_high: Optional[float] = None
    atr: Optional[float] = None
    debt_to_equity: Optional[float] = None
    fcf_ttm: Optional[float] = None
    gp_to_assets: Optional[float] = None
    asset_growth: Optional[float] = None
    value_composite: Optional[float] = None
    book_to_market: Optional[float] = None
    earnings_yield: Optional[float] = None
    cashflow_yield: Optional[float] = None
    sales_yield: Optional[float] = None
    f_score: Optional[int] = None
    f_score_evaluable: Optional[int] = None
    # Feature 011 (US3): fair-value estimate + trust flag (contracts/fair-value.md).
    fair_value: Optional[float] = None
    fair_value_basis: Optional[str] = None
    fair_value_trust_flag: Optional[str] = None
    fair_value_margin_of_safety: Optional[float] = None
    gate_results: List[GateResult] = Field(default_factory=list)
    data_notes: List[str] = Field(default_factory=list)
    entry_timing: EntryTimingClassification | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    # Feature 012 US2: preferred gates retained-on under expanded coverage (FR-014).
    skipped_gates: List[SkippedGate] = Field(default_factory=list)
    # Feature 008: integrity warnings (data-model §5).
    data_integrity_warnings: List[DataIntegrityWarning] = Field(default_factory=list)
    data_suspect: bool = False
    material_input_freshness: Dict[str, Optional[str]] = Field(default_factory=dict)
    data_as_of: str
    disclaimer: str


class AdvisorPromptResponse(BaseModel):
    ticker: str
    strategy: str
    personal_use_directive: bool
    prompt: str
    data_as_of: str
    disclaimer: str


class ScreenAdvisorPromptResponse(BaseModel):
    strategy: str
    candidate_count: int
    personal_use_directive: bool
    prompt: str
    data_as_of: str
    disclaimer: str


class IndependentVerifyResponse(BaseModel):
    """On-demand independent cross-check of one candidate against a free-tier
    third-party vendor (Finnhub primary / Alpha Vantage fallback). Explicitly
    user-triggered — NOT part of the deterministic, network-free live screen
    (FR-002/FR-024). ``key_configured`` is False when no
    ``SCREENER_INDEPENDENT_QUOTE_API_KEY`` is set (→ verdict UNVERIFIED)."""

    ticker: str
    screener_price: Optional[float] = None
    screener_52w_high: Optional[float] = None
    independent_price: Optional[float] = None
    independent_52w_high: Optional[float] = None
    independent_source: str
    divergence_pct: Optional[float] = None
    verdict: str
    screener_flagged: bool = False
    key_configured: bool = False
    fetched_at: str
    data_as_of: str
    disclaimer: str


# Feature 006 — mid-term side-by-side variant comparison wire models. All
# additive: each variant reuses the existing ScreenResult, so no change to
# Candidate / ScreenResult / Strategy themselves (data-model.md).


class VariantResult(BaseModel):
    """One of the four fixed mid-term variants in a side-by-side comparison.

    `bias_check` is the strategy's survivorship verdict from
    `load_survivorship_status(slug)`; it is identical for both variants of a
    strategy because a screen-time toggle does not re-run the backtest
    (Decision 6).
    """

    key: str
    label: str
    strategy: Strategy
    toggle_param: str
    toggle_value: float
    toggle_on: bool
    screen: ScreenResult
    bias_check: Dict[str, Any]


class MidtermComparisonResponse(BaseModel):
    variants: List[VariantResult]
    regime: Optional[str] = None
    data_as_of: str
    disclaimer: str


class MidtermComparePromptResponse(BaseModel):
    prompt: str
    variant_count: int
    personal_use_directive: bool
    data_as_of: str
    disclaimer: str
