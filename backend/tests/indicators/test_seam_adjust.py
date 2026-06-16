import pandas as pd
import numpy as np
from backend.src.indicators.seam_adjust import calculate_seam_factor, apply_seam_adjustment

def test_seam_factor_stable_overlap():
    # Stooq segment (split-adjusted, not dividend-adjusted)
    stooq = pd.DataFrame({
        "as_of_date": pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03"]),
        "close": [100.0, 101.0, 102.0]
    })
    # yfinance segment (fully adjusted, e.g. 0.95 factor due to historical dividend)
    yfinance = pd.DataFrame({
        "as_of_date": pd.to_datetime(["2026-06-02", "2026-06-03", "2026-06-04"]),
        "adj_close": [101.0 * 0.95, 102.0 * 0.95, 103.0 * 0.95]
    })
    
    factor, consistent = calculate_seam_factor(stooq, yfinance)
    assert consistent is True
    assert factor == pytest.approx(0.95)

def test_seam_factor_unstable_overlap():
    stooq = pd.DataFrame({
        "as_of_date": pd.to_datetime(["2026-06-01", "2026-06-02"]),
        "close": [100.0, 100.0]
    })
    yfinance = pd.DataFrame({
        "as_of_date": pd.to_datetime(["2026-06-01", "2026-06-02"]),
        "adj_close": [100.0, 50.0]  # Factor changed from 1.0 to 0.5 (unstable)
    })
    
    factor, consistent = calculate_seam_factor(stooq, yfinance)
    assert consistent is False

def test_seam_factor_tolerates_single_day_vendor_noise():
    # 5-day overlap, no corporate action: factors ~constant except ONE day where
    # the two vendors disagree by ~0.3% (normal cross-vendor noise). Must stay
    # consistent (SC-002: no false-positive seam flag on a clean name).
    dates = pd.to_datetime(
        ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05"]
    )
    stooq = pd.DataFrame({"as_of_date": dates, "close": [100.0, 100.0, 100.3, 100.0, 100.0]})
    yfinance = pd.DataFrame({"as_of_date": dates, "adj_close": [95.0, 95.0, 95.0, 95.0, 95.0]})
    factor, consistent = calculate_seam_factor(stooq, yfinance)
    assert consistent is True
    assert factor == pytest.approx(0.95, rel=1e-3)


def test_seam_factor_flags_real_midoverlap_split():
    # A genuine action mid-overlap shifts the factor on ~half the days -> flag.
    dates = pd.to_datetime(
        ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05"]
    )
    stooq = pd.DataFrame({"as_of_date": dates, "close": [100.0, 100.0, 100.0, 50.0, 50.0]})
    yfinance = pd.DataFrame({"as_of_date": dates, "adj_close": [95.0, 95.0, 95.0, 95.0, 95.0]})
    _factor, consistent = calculate_seam_factor(stooq, yfinance)
    assert consistent is False


def test_seam_factor_empty_overlap():
    stooq = pd.DataFrame({
        "as_of_date": pd.to_datetime(["2026-06-01"]),
        "close": [100.0]
    })
    yfinance = pd.DataFrame({
        "as_of_date": pd.to_datetime(["2026-06-02"]),
        "adj_close": [100.0]
    })
    
    factor, consistent = calculate_seam_factor(stooq, yfinance)
    assert consistent is False
    assert factor == 1.0

def test_apply_seam_adjustment():
    stooq = pd.DataFrame({
        "ticker": ["TEST"],
        "as_of_date": pd.to_datetime(["2026-06-01"]),
        "open": [100.0],
        "high": [110.0],
        "low": [90.0],
        "close": [100.0]
    })
    factor = 0.5
    adjusted = apply_seam_adjustment(stooq, factor)

    assert adjusted["close"].iloc[0] == 50.0
    assert adjusted["high"].iloc[0] == 55.0
    assert adjusted["adj_close"].iloc[0] == 50.0


def test_apply_seam_adjustment_factor_one_still_sets_adj_close():
    # Single-source / no usable overlap -> factor 1.0. adj_close MUST still be
    # materialized (== raw close) so the row is not later dropped on a NaN
    # adj_close (which silently removed Stooq-only names from the screen).
    stooq = pd.DataFrame({
        "ticker": ["TEST"],
        "as_of_date": pd.to_datetime(["2026-06-01"]),
        "open": [100.0],
        "high": [110.0],
        "low": [90.0],
        "close": [100.0],
    })  # NOTE: no native adj_close, like the real Stooq archive
    adjusted = apply_seam_adjustment(stooq, 1.0)
    assert "adj_close" in adjusted.columns
    assert adjusted["adj_close"].iloc[0] == 100.0  # raw close, unscaled
    assert adjusted["close"].iloc[0] == 100.0  # factor 1.0 leaves OHLC untouched

import pytest
