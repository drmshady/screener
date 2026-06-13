import pandas as pd

def calculate_n_day_high(high: pd.Series, length: int) -> pd.Series:
    """N-day highest high"""
    if len(high) < length:
        return pd.Series([None]*len(high), index=high.index)
    return high.rolling(window=length).max()

def calculate_n_day_low(low: pd.Series, length: int) -> pd.Series:
    """N-day lowest low"""
    if len(low) < length:
        return pd.Series([None]*len(low), index=low.index)
    return low.rolling(window=length).min()

def calculate_chandelier_exit_long(high: pd.Series, atr: pd.Series, length: int = 22, multiplier: float = 3.0) -> pd.Series:
    """Chandelier Exit Long"""
    highest_high = calculate_n_day_high(high, length)
    return highest_high - (atr * multiplier)
