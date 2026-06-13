import pandas as pd

def calculate_n_month_return(close: pd.Series, months: int) -> pd.Series:
    """N-month momentum (typically 12-1 month return, skipping the most recent month)"""
    # Assuming daily data, 1 month ~ 21 trading days
    days = months * 21
    if len(close) <= days:
        return pd.Series([None]*len(close), index=close.index)
    
    # 12-1 month means comparing current close shifted 1 month ago vs 12 months ago
    # Wait, usually it is (Close_current / Close_12m_ago) - 1
    # If skipping most recent month: (Close_1m_ago / Close_12m_ago) - 1
    # We will implement generic n-month return
    return close.pct_change(periods=days)


def calculate_12_1_return(close: pd.Series) -> pd.Series:
    """12-1 month momentum: close one month ago versus close twelve months ago."""
    one_month = 21
    twelve_months = 252
    return (close.shift(one_month) / close.shift(twelve_months)) - 1.0


def sector_relative_rank(df: pd.DataFrame, sector_column: str = "sector", score_column: str = "score") -> pd.Series:
    """Percentile rank within sector, higher score is better."""
    return df.groupby(sector_column)[score_column].rank(ascending=False, pct=True, method="first")
