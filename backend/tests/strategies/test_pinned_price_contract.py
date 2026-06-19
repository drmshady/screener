"""Regression: the momentum contract catches a price pinned under a pending
all-cash acquisition (the EA-at-its-$210-offer defect, feature 009 bug scan).

EA passed the 2026-06-17 screen and ranked #1 because its realized volatility had
collapsed to ~6% annualized (price pinned near the $210 cash offer), saturating the
Barroso-Santa-Clara ``vol_scalar`` at its 2.0 cap and inflating the score. The data
itself was correct (seam-consistent, no jumps), so no prior invariant fired. The
``value_domain.realized_vol_floor`` invariant closes that gap: detect + demote +
warn, no strategy rule/default/baseline change.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.src.screening.integrity.engine import evaluate_contract
from backend.src.strategies.midterm_52w_high_momentum import OUTPUT_CONTRACT


def _candidate(ticker: str, *, annualized_vol: float, vol_scalar: float) -> dict:
    """A candidate row that satisfies every OTHER momentum invariant, carrying a
    realistic ``daily_returns`` window at the requested realized volatility."""
    close, atr, ret = 200.0, 3.0, 0.33
    high = round(close / (1 - 0.01), 4)  # ~1% below the 52-week high
    dist = (high - close) / close
    stop = round(close - 3 * atr, 4)
    score = ret * vol_scalar / (1.0 + dist)
    take_profit = close + 3.0 * (close - stop)
    rng = np.random.default_rng(abs(hash(ticker)) % (2**32))
    daily = pd.Series(rng.normal(0.0, annualized_vol / np.sqrt(252), 126))
    return {
        "ticker": ticker,
        "name": ticker,
        "sector": "Communication Services",
        "close": close,
        "52w_high": high,
        "dist_to_high": dist,
        "entry": close,
        "atr": atr,
        "stop_loss": stop,
        "take_profit": take_profit,
        "vol_scalar": vol_scalar,
        "score": score,
        "return_12_1": ret,
        "daily_returns": daily,
        # clean §8 signals
        "series_dates_ok": True,
        "series_max_session_move": 0.10,
        "seam_consistent": True,
        "seam_factor": 1.0,
        "seam_overlap_found": True,
        "corporate_action_in_window": False,
        "series_max_move_explained": True,
        "adj_close_basis_used": True,
        "share_class_consistent": True,
    }


def test_pinned_acquisition_name_is_flagged_and_demoted():
    frame = pd.DataFrame(
        [
            # EA-like merger-arb pin: 6% realized vol, vol_scalar saturated at 2.0.
            _candidate("EA", annualized_vol=0.06, vol_scalar=2.0),
            # A normal momentum name with healthy realized vol.
            _candidate("CLEAN", annualized_vol=0.30, vol_scalar=1.0),
        ]
    )
    annotated = evaluate_contract(frame, OUTPUT_CONTRACT)
    by_ticker = {r["ticker"]: r for _, r in annotated.iterrows()}

    ea = by_ticker["EA"]
    assert bool(ea["data_suspect"]) is True
    fired = {v.invariant_name for v in ea["data_integrity_warnings"]}
    assert "value_domain.realized_vol_floor" in fired
    # the pin is isolated to its own invariant (the data was otherwise correct)
    assert fired == {"value_domain.realized_vol_floor"}

    clean = by_ticker["CLEAN"]
    assert bool(clean["data_suspect"]) is False
