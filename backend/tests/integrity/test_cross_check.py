"""T017 [US2] — independent cross-check verdict logic (FR-010/FR-011, SC-003/SC-004).

Written FIRST: must FAIL before ``integrity/harness.py`` exists (T019).

Verdict assignment from a screener-vs-independent figure pair:
  * ``AGREES``                — divergence < 10%;
  * ``DIVERGES_AND_FLAGGED``  — divergence ≥ 10% AND the screener flagged the name;
  * ``DIVERGES_UNFLAGGED``    — divergence ≥ 10% AND no warning (a FAILURE, SC-004);
  * ``UNVERIFIED``            — the independent source had no figure;
  * ``STALE``                 — divergence attributable to an honestly-old last bar,
    NOT a defect (FR-011) — must be classified STALE, not DIVERGES_UNFLAGGED.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.src.data.independent_quote import IndependentQuote
from backend.src.screening.integrity.harness import (
    CrossCheckVerdict,
    classify_verdict,
    compute_divergence,
    cross_check,
)
from backend.src.strategies.midterm_52w_high_momentum import OUTPUT_CONTRACT


def test_compute_divergence_is_symmetric_relative_to_independent():
    assert compute_divergence(110.0, 100.0) == pytest.approx(0.10)
    assert compute_divergence(90.0, 100.0) == pytest.approx(0.10)
    assert compute_divergence(100.0, 100.0) == pytest.approx(0.0)
    assert compute_divergence(100.0, None) is None
    assert compute_divergence(100.0, 0.0) is None


def test_agrees_under_threshold():
    v = classify_verdict(
        screener_price=101.0, independent_price=100.0, has_warning=False, stale=False
    )
    assert v == "AGREES"


def test_diverges_and_flagged_when_warning_present():
    v = classify_verdict(
        screener_price=135.0, independent_price=100.0, has_warning=True, stale=False
    )
    assert v == "DIVERGES_AND_FLAGGED"


def test_diverges_unflagged_is_a_failure():
    v = classify_verdict(
        screener_price=135.0, independent_price=100.0, has_warning=False, stale=False
    )
    assert v == "DIVERGES_UNFLAGGED"


def test_unverified_when_no_independent_price():
    v = classify_verdict(
        screener_price=100.0, independent_price=None, has_warning=False, stale=False
    )
    assert v == "UNVERIFIED"


def test_genuine_staleness_is_stale_not_diverges_unflagged():
    """FR-011: an honestly-old last bar that diverges is STALE, not a failure."""
    v = classify_verdict(
        screener_price=135.0, independent_price=100.0, has_warning=False, stale=True
    )
    assert v == "STALE"


def test_threshold_boundary_is_ten_percent():
    # Exactly 10% diverges; just under agrees.
    assert (
        classify_verdict(
            screener_price=110.0, independent_price=100.0, has_warning=True, stale=False
        )
        == "DIVERGES_AND_FLAGGED"
    )
    assert (
        classify_verdict(
            screener_price=109.99,
            independent_price=100.0,
            has_warning=True,
            stale=False,
        )
        == "AGREES"
    )


def _row(ticker, close, ret, *, high_mult=1.03):
    high = close * high_mult
    dist = (high - close) / close
    stop = close - 6.0
    return {
        "ticker": ticker,
        "name": ticker,
        "sector": "Industrials",
        "close": close,
        "52w_high": high,
        "dist_to_high": dist,
        "entry": close,
        "atr": 2.0,
        "stop_loss": stop,
        "take_profit": close + 3.0 * (close - stop),
        "vol_scalar": 1.0,
        "score": ret / (1.0 + dist),
        "return_12_1": ret,
        "series_dates_ok": True,
        "series_max_session_move": 0.08,
        "seam_consistent": True,
        "seam_factor": 1.0,
        "corporate_action_in_window": False,
        "adj_close_basis_used": True,
        "share_class_consistent": True,
    }


class _FakeProvider:
    def __init__(self, quotes):
        self._quotes = quotes

    def quote(self, ticker):
        return self._quotes.get(
            ticker,
            IndependentQuote(
                ticker=ticker,
                price=None,
                high_52w=None,
                source="fake",
                available=False,
            ),
        )


def test_cross_check_resolves_belfb_diverges_and_flagged_clean_agree():
    # BELFB carries a spurious +1200% return → flagged by the contract; the
    # independent price diverges ~35% from the screener price.
    snapshot = pd.DataFrame(
        [
            {**_row("BELFB", 120.0, 12.0), "52w_high": 123.6},
            _row("JBHT", 180.0, 0.22),
            _row("CW", 300.0, 0.30),
        ]
    )
    quotes = {
        "BELFB": IndependentQuote("BELFB", 79.0, 123.6, "finnhub", True),
        "JBHT": IndependentQuote("JBHT", 181.0, 185.0, "finnhub", True),
        "CW": IndependentQuote("CW", 298.0, 309.0, "finnhub", True),
    }
    verdicts = cross_check(snapshot, OUTPUT_CONTRACT, _FakeProvider(quotes))
    by = {v.ticker: v for v in verdicts}
    assert isinstance(verdicts[0], CrossCheckVerdict)
    assert by["BELFB"].verdict == "DIVERGES_AND_FLAGGED"
    assert by["JBHT"].verdict == "AGREES"
    assert by["CW"].verdict == "AGREES"
    # No DIVERGES_UNFLAGGED anywhere (SC-004).
    assert all(v.verdict != "DIVERGES_UNFLAGGED" for v in verdicts)


def test_cross_check_missing_source_is_unverified_no_crash():
    snapshot = pd.DataFrame([_row("JBHT", 180.0, 0.22)])
    verdicts = cross_check(snapshot, OUTPUT_CONTRACT, _FakeProvider({}))
    assert verdicts[0].verdict == "UNVERIFIED"


def test_cross_check_honours_stale_override():
    snapshot = pd.DataFrame([_row("OLD", 135.0, 0.20)])
    quotes = {"OLD": IndependentQuote("OLD", 100.0, 140.0, "finnhub", True)}
    verdicts = cross_check(
        snapshot, OUTPUT_CONTRACT, _FakeProvider(quotes), stale_tickers={"OLD"}
    )
    assert verdicts[0].verdict == "STALE"


def test_cross_check_caps_at_top_n():
    rows = [_row(f"T{i}", 100.0 + i, 0.20) for i in range(15)]
    snapshot = pd.DataFrame(rows)
    verdicts = cross_check(
        snapshot, OUTPUT_CONTRACT, _FakeProvider({}), top_n=10
    )
    assert len(verdicts) == 10
