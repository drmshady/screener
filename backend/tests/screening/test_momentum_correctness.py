import pandas as pd
import numpy as np
from datetime import date
from backend.src.indicators.seam_adjust import apply_seam_adjustment, calculate_seam_factor
from backend.src.screening.engine import _compute_snapshot_rows
from backend.src.screening.integrity.invariants import series_integrity


def _merge_like_overlay(stooq: pd.DataFrame, fresh: pd.DataFrame) -> pd.DataFrame:
    """Reproduce _overlay_fresh_prices' per-ticker seam merge for one ticker."""
    factor, consistent = calculate_seam_factor(stooq, fresh)
    overlap_found = len(set(stooq["as_of_date"]) & set(fresh["as_of_date"])) >= 2
    base = apply_seam_adjustment(stooq, factor)
    base = base.assign(
        seam_factor=factor, seam_consistent=consistent,
        seam_overlap_found=overlap_found, _src=0,
    )
    fresh = fresh.assign(
        seam_factor=1.0, seam_consistent=True, seam_overlap_found=True, _src=1,
    )
    merged = pd.concat([base, fresh], ignore_index=True).sort_values(
        ["ticker", "as_of_date", "_src"]
    )
    merged = (
        merged.drop_duplicates(["ticker", "as_of_date"], keep="last")
        .drop(columns=["_src"])
        .reset_index(drop=True)
    )
    merged["as_of_date"] = pd.to_datetime(merged["as_of_date"])
    return merged


def test_window_dividend_does_not_mask_unrelated_bad_bar():
    # A genuine bad-bar spike in the Stooq region co-occurring with a routine
    # dividend in the recent yfinance overlay must STILL be flagged: a window-wide
    # corporate action must not excuse an unrelated jump (feature 008 masking fix).
    today = date(2026, 6, 12)
    dates = pd.date_range(end=today, periods=300, freq="B")
    raw = np.full(300, 100.0)
    raw[100] = 160.0  # +60% erroneous print, reverts next session
    stooq = pd.DataFrame({
        "ticker": ["TST"] * 295, "as_of_date": dates[:295],
        "open": raw[:295], "high": raw[:295], "low": raw[:295], "close": raw[:295],
        "volume": [1_000_000] * 295,
    })  # no native adj_close
    ov = dates[293:300]
    fresh = pd.DataFrame({
        "ticker": ["TST"] * len(ov), "as_of_date": ov,
        "open": [100.0] * len(ov), "high": [100.0] * len(ov), "low": [100.0] * len(ov),
        "close": [100.0] * len(ov),
        # dividend ex within the overlay: pre-ex adj_close < close
        "adj_close": [99.0, 99.0, 99.0, 100.0, 100.0, 100.0, 100.0][: len(ov)],
        "volume": [1_000_000] * len(ov),
    })
    merged = _merge_like_overlay(stooq, fresh)
    snap = _compute_snapshot_rows(merged, {"TST"}, today, {"TST": {"name": "T", "sector": "Tech"}})
    row = snap.iloc[0]
    assert row["series_max_session_move"] > 0.40  # the bad bar is present
    assert row["corporate_action_in_window"] is True or row["corporate_action_in_window"] == True
    # The localized signal correctly reports the max move is NOT explained.
    assert bool(row["series_max_move_explained"]) is False
    jump = {i.name: i for i in series_integrity()}["series.no_unexplained_jump"]
    assert jump.predicate(row, row) is False  # flagged, not masked


def test_real_corporate_action_at_jump_is_not_flagged():
    # A 2:1 split reflected by yfinance's adjusted series leaves NO jump on the
    # adjusted basis, so nothing to flag; if a residual jump lines up with the
    # ratio change it is explained. Confirms we did not over-correct.
    today = date(2026, 6, 12)
    dates = pd.date_range(end=today, periods=300, freq="B")
    close = [100.0] * 150 + [50.0] * 150       # raw halves at the split
    adj_close = [50.0] * 300                    # adjusted is continuous
    prices = pd.DataFrame({
        "ticker": ["AAPL"] * 300, "as_of_date": dates,
        "open": close, "high": close, "low": close, "close": close,
        "adj_close": adj_close, "volume": [1_000_000] * 300,
        "seam_consistent": [True] * 300, "seam_factor": [1.0] * 300,
    })
    snap = _compute_snapshot_rows(prices, {"AAPL"}, today, {"AAPL": {"name": "A", "sector": "Tech"}})
    row = snap.iloc[0]
    assert row["series_max_session_move"] <= 0.40  # absorbed -> no jump
    jump = {i.name: i for i in series_integrity()}["series.no_unexplained_jump"]
    assert jump.predicate(row, row) is True


def test_stooq_only_no_overlay_is_flagged_not_dropped():
    # A liquid name present in Stooq but with no usable yfinance overlay used to
    # vanish from the screen (NaN adj_close -> return_12_1 NaN -> row dropped).
    # It must now survive (raw-close basis) and carry seam_consistent=False.
    today = date(2026, 6, 12)
    dates = pd.date_range(end=today, periods=300, freq="B")
    raw = np.linspace(80.0, 100.0, 300)
    stooq = pd.DataFrame({
        "ticker": ["SO"] * 300, "as_of_date": dates,
        "open": raw, "high": raw, "low": raw, "close": raw,
        "volume": [1_000_000] * 300,
    })  # no native adj_close
    empty_fresh = stooq.iloc[0:0].assign(adj_close=pd.Series(dtype=float))
    merged = _merge_like_overlay(stooq, empty_fresh)
    assert merged["adj_close"].notna().all()  # Fix 2: no NaN adj_close
    snap = _compute_snapshot_rows(merged, {"SO"}, today, {"SO": {"name": "S", "sector": "Tech"}}, exclude_stale=False)
    assert len(snap) == 1  # not dropped
    row = snap.iloc[0]
    assert bool(row["seam_consistent"]) is False  # surfaced for verification
    # Tri-state (Option 1): no overlap -> SOFT unverified flag, NOT the strong
    # "verified inconsistent / price may be erroneous" flag.
    assert bool(row["seam_overlap_found"]) is False
    by_name = {i.name: i for i in series_integrity()}
    assert by_name["series.seam_unverified"].predicate(row, row) is False  # soft fires
    assert by_name["series.seam_consistent"].predicate(row, row) is True   # strong silent

def test_momentum_correctness_with_split():
    # Simulate a 2:1 split in the middle of the window
    today = date(2026, 6, 12)
    dates = pd.date_range(end=today, periods=300, freq="B")
    
    # Raw close has a jump from 100 to 50 due to split
    close = [100.0] * 150 + [50.0] * 150
    # Adjusted close is constant 50.0
    adj_close = [50.0] * 300
    
    prices = pd.DataFrame({
        "ticker": ["AAPL"] * 300,
        "as_of_date": dates,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "adj_close": adj_close,
        "volume": [1000000] * 300,
        "seam_consistent": [True] * 300,
        "seam_factor": [1.0] * 300
    })
    
    liquid = {"AAPL"}
    profiles = {"AAPL": {"name": "Apple Inc", "sector": "Technology"}}
    
    snapshot = _compute_snapshot_rows(prices, liquid, today, profiles)
    
    # momentum should be 0.0 (constant adj_close), not -50% (raw close)
    assert snapshot.iloc[0]["return_12_1"] == 0.0
    # 52w high should be 50.0 (adjusted), not 100.0 (raw)
    assert snapshot.iloc[0]["52w_high"] == 50.0
    # entry (close) should still be raw 50.0
    assert snapshot.iloc[0]["close"] == 50.0

def test_share_class_inconsistency():
    today = date(2026, 6, 12)
    dates = pd.date_range(end=today, periods=300, freq="B")
    
    # Case: ticker is BELFB but fundamentals ticker is BELFA (mismatch)
    prices = pd.DataFrame({
        "ticker": ["BELFB"] * 300,
        "as_of_date": dates,
        "open": [100.0] * 300,
        "high": [100.0] * 300,
        "low": [100.0] * 300,
        "close": [100.0] * 300,
        "adj_close": [100.0] * 300,
        "volume": [1000000] * 300,
        "seam_consistent": [True] * 300,
        "seam_factor": [1.0] * 300
    })
    
    liquid = {"BELFB"}
    # profile has 'ticker': 'BELFA' but we looked it up by 'BELFB'
    profiles = {"BELFB": {"name": "Bel Fuse Inc. B", "ticker": "BELFA"}}
    
    snapshot = _compute_snapshot_rows(prices, liquid, today, profiles)
    assert snapshot.iloc[0]["share_class_consistent"] == False
