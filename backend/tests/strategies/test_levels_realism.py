import math

import pandas as pd
import pytest

from backend.src.strategies import midterm_52w_high_momentum as momentum
from backend.src.strategies import midterm_value_composite as value
from backend.src.strategies.levels import derive_bounded_levels


def _bounded(row: dict, **overrides):
    params = {
        "risk_distance_atr_lo": 1.0,
        "risk_distance_atr_hi": 4.0,
        "take_profit_r_multiple": 3.0,
        "reward_ceiling_z": 2.5,
        "reward_ceiling_use_fair_value": False,
        "holding_period_days": {"min": 60, "max": 180},
        "structure_stop_buffer_atr": 0.25,
        "stop_mode": "trend",
    }
    params.update(overrides)
    return derive_bounded_levels(row, **params)


def _momentum_row(ticker: str, close: float, atr: float, sma_200: float) -> dict:
    return {
        "ticker": ticker,
        "name": ticker,
        "sector": "Technology",
        "close": close,
        "52w_high": close * 1.02,
        "return_12_1": 0.4,
        "fcf_ttm": 10_000_000,
        "debt_to_equity": 0.4,
        "atr": atr,
        "sma_200": sma_200,
        "contraction_low_20": close - (2 * atr),
        "gp_to_assets": 0.5,
        "asset_growth": 0.05,
    }


def test_bounded_levels_respect_realism_bounds_on_frozen_rows():
    rows = [
        {"close": 100.0, "atr": 2.0, "sma_200": 92.0, "contraction_low_20": 96.0},
        {"close": 75.0, "atr": 1.5, "sma_200": 60.0, "contraction_low_20": 72.0},
        {"close": 42.0, "atr": 0.8, "sma_200": 36.0, "contraction_low_20": 40.2},
    ]

    for row in rows:
        levels = _bounded(row)
        assert levels["levels_state"] == "ok"
        assert 0 < levels["stop_loss"] < levels["entry"] < levels["take_profit"]

        risk = levels["risk_distance"]
        reward = levels["reward_distance"]
        assert risk == pytest.approx(levels["entry"] - levels["stop_loss"])
        assert reward == pytest.approx(levels["take_profit"] - levels["entry"])
        assert 1.0 * row["atr"] <= risk <= 4.0 * row["atr"]

        ceiling_distance = 2.5 * row["atr"] * math.sqrt(180)
        assert reward <= ceiling_distance
        assert levels["take_profit"] <= levels["entry"] + ceiling_distance
        assert levels["reward_ceiling_basis"] in {"r_multiple", "volatility_horizon"}
        assert isinstance(levels["bounds_applied"], list)
        assert levels["rationale"]


def test_far_below_sma_200_risk_is_clamped_not_extrapolated():
    levels = _bounded(
        {"close": 100.0, "atr": 2.0, "sma_200": 20.0, "contraction_low_20": 95.0}
    )

    assert levels["levels_state"] == "ok"
    assert levels["risk_distance"] == pytest.approx(8.0)
    assert levels["stop_loss"] == pytest.approx(92.0)
    assert levels["take_profit"] < 130.0
    assert "risk_cap" in levels["bounds_applied"]


def test_midterm_rules_emit_bounded_level_metadata(monkeypatch):
    monkeypatch.setenv("SCREENER_GATE_MODE", "hard")
    universe = pd.DataFrame(
        [
            _momentum_row("AAA", close=100.0, atr=2.0, sma_200=80.0),
            _momentum_row("BBB", close=90.0, atr=1.5, sma_200=84.0),
        ]
    )

    out = momentum.rules(universe)

    assert set(out["ticker"]) == {"AAA", "BBB"}
    for _, row in out.iterrows():
        assert row["levels_state"] == "ok"
        assert 0 < row["stop_loss"] < row["entry"] < row["take_profit"]
        assert row["risk_distance"] == pytest.approx(row["entry"] - row["stop_loss"])
        assert 1.0 * row["atr"] <= row["risk_distance"] <= 4.0 * row["atr"]
        assert row["reward_distance"] == pytest.approx(row["take_profit"] - row["entry"])
        assert row["reward_ceiling_basis"] in {"r_multiple", "volatility_horizon"}
        assert row["rationale"]


def test_value_rules_use_same_bounded_level_helper(monkeypatch):
    monkeypatch.delenv("SCREENER_VALUE_MIN_MOMENTUM", raising=False)
    universe = pd.DataFrame(
        [
            {
                "ticker": "GOOD",
                "name": "GOOD",
                "sector": "Technology",
                "close": 50.0,
                "atr": 1.0,
                "sma_200": 40.0,
                "contraction_low_20": 48.0,
                "debt_to_equity": 1.0,
                "fcf_ttm": 10.0,
                "book_to_market": 0.9,
                "earnings_yield": 0.12,
                "cashflow_yield": 0.10,
                "sales_yield": 2.0,
                "f_score": 8,
                "f_score_evaluable": 9,
            }
        ]
    )

    out = value.rules(universe)

    row = out.iloc[0]
    assert row["levels_state"] == "ok"
    assert row["risk_distance"] == pytest.approx(row["entry"] - row["stop_loss"])
    assert 1.0 * row["atr"] <= row["risk_distance"] <= 4.0 * row["atr"]
    assert row["rationale"]
