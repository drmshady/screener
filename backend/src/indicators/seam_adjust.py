from __future__ import annotations

import pandas as pd
import numpy as np


def calculate_seam_factor(
    stooq_part: pd.DataFrame, yfinance_part: pd.DataFrame
) -> tuple[float, bool]:
    """
    Derive the median adjustment factor (yfinance adj_close / stooq close) 
    over a shared overlap (typically 5 days).
    
    Returns (factor, consistent). 
    'consistent' is False if overlap is too small or factor is unstable.
    """
    if stooq_part.empty or yfinance_part.empty:
        return 1.0, False

    # Find shared dates
    shared_dates = set(stooq_part["as_of_date"]) & set(yfinance_part["as_of_date"])
    if len(shared_dates) < 2:
        # We need at least 2 points to judge stability, though 5 is preferred.
        return 1.0, False

    # Align on shared dates
    s = stooq_part[stooq_part["as_of_date"].isin(shared_dates)].sort_values("as_of_date")
    y = yfinance_part[yfinance_part["as_of_date"].isin(shared_dates)].sort_values("as_of_date")
    
    # Calculate factors per day
    factors = y["adj_close"].values / s["close"].values

    # Median is robust to single-day bad prints
    median_factor = float(np.median(factors))

    # Stability check: the factor should be ~constant over the overlap. It is NOT
    # constant when a split/material dividend lands mid-overlap (can't cleanly
    # stitch -> flag). But the factor is yfinance_adj_close / stooq_close across
    # TWO vendors, so a day of normal sub-percent vendor price disagreement must
    # NOT flag an otherwise-clean name (SC-002 false-positive guard).
    #
    # Measure spread as the MAX deviation from the robust median center and flag
    # only past 2%: well above routine cross-vendor noise (tens of bps), well
    # below a split (50%+) or a material corporate action. The old 0.1% std/mean
    # bound tripped on benign vendor noise.
    if len(factors) >= 2:
        max_dev = float(
            np.max(np.abs(factors - median_factor)) / (abs(median_factor) + 1e-9)
        )
        if max_dev > 0.02:
            return median_factor, False

    return median_factor, True


def apply_seam_adjustment(
    stooq_part: pd.DataFrame, factor: float
) -> pd.DataFrame:
    """
    Back-adjust the Stooq segment onto the yfinance basis.

    ``adj_close`` is ALWAYS materialized (== the possibly-back-adjusted close),
    even when ``factor == 1.0`` (single-source / no usable overlap). Stooq has no
    native ``adj_close``; without this, a no-overlay ticker keeps a NaN adj_close
    downstream and its row is silently dropped from the screen (return_12_1 NaN)
    instead of being surfaced + flagged ``seam_consistent=False``.
    """
    if stooq_part.empty:
        return stooq_part

    adjusted = stooq_part.copy()
    if factor != 1.0:
        for col in ["open", "high", "low", "close"]:
            if col in adjusted.columns:
                adjusted[col] = adjusted[col] * factor

    if "close" in adjusted.columns:
        adjusted["adj_close"] = adjusted["close"]
    return adjusted
