from __future__ import annotations

import json
from datetime import date

import backend.src.strategies.shortterm_atr_breakout  # noqa: F401 (registers strategy)
import numpy as np
import pandas as pd
from backend.src.backtests.runner import run_backtest


def _bars(ticker: str, dates: pd.DatetimeIndex, close: np.ndarray) -> pd.DataFrame:
    close = np.asarray(close, dtype=float)
    return pd.DataFrame(
        {
            "ticker": ticker,
            "as_of_date": dates,
            "open": np.concatenate([[close[0]], close[:-1]]),
            "high": close,
            "low": close * 0.97,
            "close": close,
            "volume": 200_000,
        }
    )


def _synthetic_universe() -> pd.DataFrame:
    # A steady uptrend name (new highs, rising 200-SMA -> gets selected) plus flat
    # survivors. No fundamentals strategy, so no SEC/network is touched.
    up_dates = pd.bdate_range("2014-01-02", "2016-12-30")
    up = 20.0 * (1.0 + np.linspace(0, 1.6, len(up_dates)))
    trend = _bars("TREND", up_dates, up)
    rng = np.random.default_rng(7)
    survivors = [
        _bars(t, up_dates, 30.0 + rng.normal(0, 0.3, len(up_dates)))
        for t in ("AAAA", "BBBB")
    ]
    return pd.concat([trend, *survivors], ignore_index=True)


def _run() -> dict:
    return run_backtest(
        "shortterm_atr_breakout",
        date(2015, 1, 1),
        date(2016, 12, 31),
        prices=_synthetic_universe(),
    )


def test_backtest_output_is_byte_identical_for_same_snapshot_and_config(monkeypatch) -> None:
    monkeypatch.setenv("SCREENER_BACKTEST_REBALANCE", "Q")
    monkeypatch.setenv("SCREENER_BACKTEST_COST_BPS", "10")

    first = _run()
    second = _run()

    # Real proof of FR-015: the whole pipeline (cadence dates, snapshot, metrics,
    # cost model, bias check, equity curve) reproduces byte-for-byte.
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    # The run actually exercised cadence + cost, not an empty payload.
    assert first["rebalance_cadence"] == "Q"
    assert first["cost_model"] == {"per_side_bps": 10.0, "applied": True}
    assert sum(y["trades"] for y in first["yearly_metrics"]) >= 1
