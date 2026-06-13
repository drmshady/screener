from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field, computed_field
import pandas as pd


class Modification(BaseModel):
    name: str
    description: str
    citation: str


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
    rank: int
    score: float
    reason: str
    gate_results: List[GateResult] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
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
    gate_results: List[GateResult] = Field(default_factory=list)
    data_notes: List[str] = Field(default_factory=list)
    data_as_of: str
    disclaimer: str
