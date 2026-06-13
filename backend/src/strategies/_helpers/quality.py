import pandas as pd


def gross_profitability_mask(series: pd.Series, min_percentile: float = 0.5) -> pd.Series:
    """
    Novy-Marx (2013) gross-profitability quality gate, applied cross-sectionally.

    `series` is gross profit / total assets per ticker. Returns a boolean mask
    keeping tickers at or above the `min_percentile` cut of the universe
    (default median -> top 50%). Tickers with missing GP/Assets fail the gate,
    matching the conservative behavior of `passes_quality_screen`.
    """
    valid = series.dropna()
    if valid.empty:
        return pd.Series(False, index=series.index)
    threshold = valid.quantile(min_percentile)
    return series.notna() & (series >= threshold)


def passes_quality_screen(debt_to_equity: float, fcf_ttm: float, max_debt_equity: float = 1.0) -> bool:
    """
    Quality screen helper.
    Requires Debt/Equity to be below max_debt_equity (default 1.0) and trailing 12-month Free Cash Flow to be positive.
    """
    if pd.isna(debt_to_equity) or pd.isna(fcf_ttm):
        return False
        
    if debt_to_equity > max_debt_equity:
        return False
        
    if fcf_ttm <= 0:
        return False
        
    return True
