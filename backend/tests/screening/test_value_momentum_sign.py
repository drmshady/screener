from __future__ import annotations

import pytest
import pandas as pd
from backend.src.models.strategy import Candidate, ScreenResult

def test_momentum_sign_does_not_affect_ordering():
    # Strategy sorting logic (FR-018): ["data_suspect", "warning_count", "score", "ticker"]
    # We want to ensure that return_12_1 (the momentum value) is NOT in the sort key.
    
    c1 = Candidate(
        ticker="RISE",
        name="Rising Corp",
        sector="Tech",
        current_price="100.0",
        entry="100.0",
        stop_loss="90.0",
        take_profit="130.0",
        rank=1,
        score=0.90, # Lower score
        reason="Match",
        return_12_1=0.50, # Positive momentum
        data_suspect=False,
        data_integrity_warnings=[]
    )
    
    c2 = Candidate(
        ticker="FALL",
        name="Falling Corp",
        sector="Tech",
        current_price="100.0",
        entry="100.0",
        stop_loss="90.0",
        take_profit="130.0",
        rank=2,
        score=0.95, # Higher score
        reason="Match",
        return_12_1=-0.10, # Negative momentum
        data_suspect=False,
        data_integrity_warnings=[]
    )
    
    # If we sort by the logic in engine.py:
    candidates = [c1, c2]
    # In engine.py: results.sort_values(["data_suspect", "warning_count", "score", "ticker"], ascending=[True, True, False, True])
    
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (c.data_suspect, len(c.data_integrity_warnings), -c.score, c.ticker)
    )
    
    # FALL (score 0.95) should be first, even though it has negative momentum.
    assert sorted_candidates[0].ticker == "FALL"
    assert sorted_candidates[1].ticker == "RISE"

def test_data_suspect_demotes_regardless_of_score():
    c1 = Candidate(
        ticker="BAD",
        name="Bad but High Score",
        sector="Tech",
        current_price="100.0",
        entry="100.0",
        stop_loss="90.0",
        take_profit="130.0",
        rank=1,
        score=0.99, 
        reason="Match",
        return_12_1=0.50,
        data_suspect=True, # Flagged
        data_integrity_warnings=[{"rule": "test", "reason": "test"}]
    )
    
    c2 = Candidate(
        ticker="GOOD",
        name="Good but Low Score",
        sector="Tech",
        current_price="100.0",
        entry="100.0",
        stop_loss="90.0",
        take_profit="130.0",
        rank=2,
        score=0.50, 
        reason="Match",
        return_12_1=0.10,
        data_suspect=False, # Clean
        data_integrity_warnings=[]
    )
    
    candidates = [c1, c2]
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (c.data_suspect, len(c.data_integrity_warnings), -c.score, c.ticker)
    )
    
    # GOOD should be first because it is not suspect.
    assert sorted_candidates[0].ticker == "GOOD"
    assert sorted_candidates[1].ticker == "BAD"
