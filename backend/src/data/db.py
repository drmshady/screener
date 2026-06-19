from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    JSON,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    create_engine,
)

metadata_obj = MetaData()

tickers = Table(
    "tickers",
    metadata_obj,
    Column("ticker", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("exchange", String, nullable=False),
    Column("cik", String, nullable=True),
    Column("sic_code", String, nullable=True),
    Column("sector", String, nullable=True, default="Unclassified"),
    Column("industry", String, nullable=True),
    Column("listed_at", Date, nullable=False),
    Column("delisted_at", Date, nullable=True),
    Column("source_name", String, nullable=False),
    Column("source_as_of", DateTime, nullable=False),
)

fundamentals = Table(
    "fundamentals",
    metadata_obj,
    Column("ticker", String, nullable=False),
    Column("period_end", Date, nullable=False),
    Column("filing_date", Date, nullable=False),
    Column("form_type", String, nullable=False),
    Column("revenue", Float, nullable=False),
    Column("eps_basic", Float, nullable=False),
    Column("eps_diluted", Float, nullable=False),
    Column("net_income", Float, nullable=False),
    Column("total_assets", Float, nullable=False),
    Column("total_liabilities", Float, nullable=False),
    Column("shares_outstanding", Float, nullable=False),
    Column("accession_number", String, nullable=False),
    Column("source_name", String, nullable=False),
    Column("source_as_of", DateTime, nullable=False),
)

shariah_sources = Table(
    "shariah_sources",
    metadata_obj,
    Column("ticker", String, nullable=False),
    Column("source_name", String, nullable=False),
    Column("source_kind", String, nullable=False),
    Column("source_as_of", DateTime, nullable=False),
    Column("source_url", String, nullable=False),
    PrimaryKeyConstraint("ticker", "source_name"),
)

ticker_events = Table(
    "ticker_events",
    metadata_obj,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", String, nullable=False),
    Column("event_type", String, nullable=False),
    Column("event_date", Date, nullable=False),
    Column("event_time", String, nullable=True),
    Column("source_name", String, nullable=False),
    Column("source_as_of", DateTime, nullable=False),
    Column("source_url", String, nullable=False),
    Column("metadata", JSON, nullable=False),
)

market_events = Table(
    "market_events",
    metadata_obj,
    Column("event_id", String, primary_key=True),
    Column("event_type", String, nullable=False),
    Column("scheduled_at", DateTime, nullable=False),
    Column("expected_value", String, nullable=True),
    Column("actual_value", String, nullable=True),
    Column("status", String, nullable=False),
    Column("source_name", String, nullable=False),
    Column("source_as_of", DateTime, nullable=False),
    Column("source_url", String, nullable=False),
)

events_sources = Table(
    "events_sources",
    metadata_obj,
    Column("source_id", String, primary_key=True),
    Column("display_name", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("refresh_interval_days", Integer, nullable=False),
    Column("last_refreshed_at", DateTime, nullable=False),
    Column("is_stale", Boolean, nullable=False),
)

backtest_runs = Table(
    "backtest_runs",
    metadata_obj,
    Column("id", String, primary_key=True),
    Column("strategy_slug", String, nullable=False),
    Column("data_window_start", Date, nullable=False),
    Column("data_window_end", Date, nullable=False),
    Column("data_sources", JSON, nullable=False),
    Column("bias_check", JSON, nullable=False),
    Column("yearly_metrics", JSON, nullable=False),
    Column("summary_metrics", JSON, nullable=False),
    Column("code_version", String, nullable=False),
    Column("computed_at", DateTime, nullable=False),
)

def get_engine(db_path: str = "sqlite:///backend/data/catalog.db"):
    return create_engine(db_path)
