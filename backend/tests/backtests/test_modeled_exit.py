from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.src.backtests.runner import _modeled_exit_return
from backend.src.strategies.levels import derive_bounded_levels


def _prices(rows: list[dict]) -> pd.core.groupby.DataFrameGroupBy:
    frame = pd.DataFrame(rows)
    frame["as_of_date"] = pd.to_datetime(frame["as_of_date"])
    return frame.groupby("ticker", sort=False)


def test_modeled_exit_uses_live_bounded_levels_and_conservative_intrabar_rule() -> None:
    levels = derive_bounded_levels(
        {
            "close": 100.0,
            "atr": 2.0,
            "sma_200": 94.0,
            "contraction_low_20": 96.0,
        },
        risk_distance_atr_lo=2.0,
        risk_distance_atr_hi=4.0,
        take_profit_r_multiple=3.0,
        reward_ceiling_z=20.0,
        reward_ceiling_use_fair_value=False,
        holding_period_days={"max": 126},
    )
    assert levels["stop_loss"] == pytest.approx(94.0)
    assert levels["take_profit"] == pytest.approx(118.0)

    by_ticker = _prices(
        [
            {"ticker": "ABC", "as_of_date": "2026-01-31", "open": 100, "high": 100, "low": 100, "close": 100},
            {"ticker": "ABC", "as_of_date": "2026-02-02", "open": 100, "high": 101, "low": 99, "close": 100},
            {"ticker": "ABC", "as_of_date": "2026-02-03", "open": 100, "high": 120, "low": 93, "close": 110},
        ]
    )

    result = _modeled_exit_return(
        by_ticker,
        "ABC",
        date(2026, 1, 31),
        stop_loss=levels["stop_loss"],
        take_profit=levels["take_profit"],
        horizon_days=10,
    )

    assert result == pytest.approx(-0.06)
