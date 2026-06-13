"""Survivorship-bias test fixture: inject a synthetic *delisted* ticker (rises to
a breakout, then collapses and stops trading) plus flat survivors, and verify the
backtest (a) detects delisted coverage, (b) selects the delisted name, and
(c) captures its catastrophic loss instead of silently dropping it.

This is the A1 ("synthetic sample") validation of the survivorship fix — it proves
the pipeline behaves correctly once real delisted data (T049b) is supplied.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

import backend.src.strategies.shortterm_atr_breakout  # noqa: F401 (registers strategy)
from backend.src.backtests.runner import detect_delisted_coverage, run_backtest


def _bars(ticker, dates, close):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame(
        {
            "ticker": ticker,
            "as_of_date": dates,
            "open": np.concatenate([[close[0]], close[:-1]]),
            "high": close,                # high == close keeps breakout logic simple
            "low": close * 0.97,          # non-zero daily range so ATR > 0
            "close": close,
            "volume": 200_000,            # close ~ $30-50 -> dollar volume >> $1M gate
        }
    )


def _synthetic_universe() -> pd.DataFrame:
    # Delisted name: 2 yrs of steady uptrend (new highs, rising 200-SMA), then a
    # hard collapse over ~2 weeks after the 2016-01-31 rebalance, last bar 2016-05.
    up_dates = pd.bdate_range("2014-01-02", "2016-01-29")
    up = 20.0 * (1.0 + np.linspace(0, 1.6, len(up_dates)))  # 20 -> ~52, monotonic
    crash_dates = pd.bdate_range("2016-02-01", "2016-05-13")
    crash = np.concatenate([
        52.0 * (0.78 ** np.arange(14)),                     # ~52 -> ~1 in 2 weeks
        np.full(len(crash_dates) - 14, 0.40),               # flatline near zero, then delist
    ])
    zomb = _bars("ZOMB", up_dates.append(crash_dates), np.concatenate([up, crash]))

    # Survivors: flat/noisy (200-SMA not rising -> never selected), run to 2017-12-31.
    surv_dates = pd.bdate_range("2014-01-02", "2017-12-31")
    rng = np.random.default_rng(7)
    survivors = [
        _bars(t, surv_dates, 30.0 + rng.normal(0, 0.3, len(surv_dates)))
        for t in ("AAAA", "BBBB", "CCCC")
    ]
    return pd.concat([zomb, *survivors], ignore_index=True)


def test_delisted_coverage_detection():
    frame = _synthetic_universe()
    assert detect_delisted_coverage(frame) is True
    survivors_only = frame[frame["ticker"] != "ZOMB"]
    assert detect_delisted_coverage(survivors_only) is False


def test_backtest_selects_delisted_name_and_captures_the_loss():
    frame = _synthetic_universe()
    result = run_backtest(
        "shortterm_atr_breakout",
        date(2015, 1, 1),
        date(2016, 12, 31),
        prices=frame,
    )

    # survivorship_bias now PASSES because the archive carries a delisted ticker.
    assert result["bias_check"]["survivorship_bias"]["passed"] is True

    # The collapse was actually traded, not silently skipped: at least one trade,
    # and the worst trade is a near-total loss (the delisted name).
    assert sum(y["trades"] for y in result["yearly_metrics"]) >= 1
    worst = min(
        (y["avg_loss"] for y in result["yearly_metrics"] if y["trades"] > 0 and y["avg_loss"] > 0),
        default=0.0,
    )
    assert worst > 0.8  # avg_loss is stored as a positive magnitude
