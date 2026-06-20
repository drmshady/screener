from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.src.backtests.runner import _modeled_exit_return


def _prices(rows: list[dict]) -> pd.core.groupby.DataFrameGroupBy:
    frame = pd.DataFrame(rows)
    frame["as_of_date"] = pd.to_datetime(frame["as_of_date"])
    return frame.groupby("ticker", sort=False)


def test_modeled_exit_checks_stop_before_target_intrabar() -> None:
    by_ticker = _prices(
        [
            {"ticker": "ABC", "as_of_date": "2026-01-31", "open": 100, "high": 100, "low": 100, "close": 100},
            {"ticker": "ABC", "as_of_date": "2026-02-02", "open": 100, "high": 101, "low": 99, "close": 100},
            {"ticker": "ABC", "as_of_date": "2026-02-03", "open": 100, "high": 110, "low": 90, "close": 105},
        ]
    )

    result = _modeled_exit_return(
        by_ticker,
        "ABC",
        date(2026, 1, 31),
        stop_loss=95,
        take_profit=108,
        horizon_days=10,
    )

    assert result == pytest.approx(-0.05)


def test_modeled_exit_gap_at_open_is_deterministic() -> None:
    by_ticker = _prices(
        [
            {"ticker": "ABC", "as_of_date": "2026-01-31", "open": 100, "high": 100, "low": 100, "close": 100},
            {"ticker": "ABC", "as_of_date": "2026-02-02", "open": 100, "high": 101, "low": 99, "close": 100},
            {"ticker": "ABC", "as_of_date": "2026-02-03", "open": 93, "high": 110, "low": 92, "close": 105},
        ]
    )

    first = _modeled_exit_return(
        by_ticker,
        "ABC",
        date(2026, 1, 31),
        stop_loss=95,
        take_profit=108,
        horizon_days=10,
    )
    second = _modeled_exit_return(
        by_ticker,
        "ABC",
        date(2026, 1, 31),
        stop_loss=95,
        take_profit=108,
        horizon_days=10,
    )

    assert first == second
    assert first == pytest.approx(-0.07)
