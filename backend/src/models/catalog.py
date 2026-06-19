from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional, Dict, List, Any
from pydantic import BaseModel
from enum import Enum

from .provenance import SourceProvenance

class Exchange(str, Enum):
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    NYSE_AMERICAN = "NYSE_AMERICAN"

class FormType(str, Enum):
    FORM_10_Q = "10-Q"
    FORM_10_K = "10-K"

class TickerEventType(str, Enum):
    EARNINGS_SCHEDULED = "earnings_scheduled"
    EIGHT_K_FILED = "8K_filed"

class MarketEventType(str, Enum):
    FOMC = "FOMC"
    CPI = "CPI"
    NFP = "NFP"
    PCE = "PCE"
    PPI = "PPI"

class MarketEventStatus(str, Enum):
    UPCOMING = "upcoming"
    RELEASED = "released"
    CANCELLED = "cancelled"

class EventsSourceKind(str, Enum):
    TICKER_EVENTS = "ticker_events"
    MARKET_EVENTS = "market_events"

class ShariahSourceKind(str, Enum):
    EXTERNAL = "external"

class Ticker(SourceProvenance):
    ticker: str
    name: str
    exchange: Exchange
    cik: Optional[str] = None
    sic_code: Optional[str] = None
    sector: Optional[str] = "Unclassified"
    industry: Optional[str] = None
    listed_at: date
    delisted_at: Optional[date] = None

class FundamentalsSnapshot(SourceProvenance):
    ticker: str
    period_end: date
    filing_date: date
    form_type: FormType
    revenue: Decimal
    eps_basic: Decimal
    eps_diluted: Decimal
    net_income: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    shares_outstanding: Decimal
    accession_number: str

class ShariahSourceRow(SourceProvenance):
    ticker: str
    source_kind: ShariahSourceKind
    source_url: str

class TickerEvent(SourceProvenance):
    ticker: str
    event_type: TickerEventType
    event_date: date
    event_time: Optional[time] = None
    source_url: str
    metadata: Dict[str, Any] = {}

class MarketEvent(SourceProvenance):
    event_id: str
    event_type: MarketEventType
    scheduled_at: datetime
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    status: MarketEventStatus
    source_url: str

class EventsSource(BaseModel):
    source_id: str
    display_name: str
    kind: EventsSourceKind
    refresh_interval_days: int
    last_refreshed_at: datetime
    is_stale: bool

class BacktestBiasCheck(BaseModel):
    passed: bool
    note: str

class BacktestYearlyMetric(BaseModel):
    year: int
    trades: int
    hit_rate: float
    avg_win: float
    avg_loss: float
    total_return: float
    max_drawdown: float

class BacktestSummaryMetrics(BaseModel):
    total_return: float
    max_drawdown: float
    hit_rate: float
    avg_win: float
    avg_loss: float
    turnover: float

class BacktestRun(BaseModel):
    id: str
    strategy_slug: str
    data_window_start: date
    data_window_end: date
    data_sources: List[SourceProvenance]
    bias_check: Dict[str, BacktestBiasCheck]
    yearly_metrics: List[BacktestYearlyMetric]
    summary_metrics: BacktestSummaryMetrics
    code_version: str
    computed_at: datetime
