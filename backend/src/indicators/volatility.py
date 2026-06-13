import pandas as pd

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Wilder Average True Range."""
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = pd.Series(float("nan"), index=close.index)
    if len(true_range) < length:
        return atr
    atr.iloc[length - 1] = true_range.iloc[:length].mean()
    for idx in range(length, len(true_range)):
        atr.iloc[idx] = ((atr.iloc[idx - 1] * (length - 1)) + true_range.iloc[idx]) / length
    return atr

def calculate_adr(high: pd.Series, low: pd.Series, length: int = 20) -> pd.Series:
    """Average Daily Range (High/Low ratio)"""
    daily_range = (high / low) - 1.0
    return daily_range.rolling(window=length).mean()


def calculate_adr_ratio(high: pd.Series, low: pd.Series, recent_length: int = 20, prior_length: int = 20) -> pd.Series:
    """Recent ADR divided by the previous ADR window."""
    adr = calculate_adr(high, low, recent_length)
    prior_adr = adr.shift(prior_length)
    return adr / prior_adr
