import pandas as pd
from datetime import date, timedelta
from backend.src.screening.engine import _compute_snapshot_rows

def test_compute_snapshot_rows_signals():
    # Create a clean series
    today = date(2026, 6, 12)
    dates = pd.date_range(end=today, periods=300, freq="B")
    prices = pd.DataFrame({
        "ticker": ["AAPL"] * 300,
        "as_of_date": dates,
        "open": [100.0] * 300,
        "high": [105.0] * 300,
        "low": [95.0] * 300,
        "close": [100.0] * 300,
        "adj_close": [100.0] * 300,
        "volume": [1000000] * 300,
        "seam_consistent": [True] * 300,
        "seam_factor": [1.0] * 300
    })
    
    liquid = {"AAPL"}
    profiles = {"AAPL": {"name": "Apple Inc", "sector": "Technology"}}
    
    snapshot = _compute_snapshot_rows(prices, liquid, today, profiles)
    
    assert not snapshot.empty
    # Verify §8 columns exist (once implemented)
    for col in [
        "series_dates_ok", "series_max_session_move", "seam_consistent", 
        "seam_factor", "corporate_action_in_window", "adj_close_basis_used",
        "share_class_consistent"
    ]:
        assert col in snapshot.columns, f"Missing signal column: {col}"
    
    assert snapshot.iloc[0]["series_dates_ok"] == True
    assert snapshot.iloc[0]["seam_consistent"] == True
    assert snapshot.iloc[0]["seam_factor"] == 1.0
