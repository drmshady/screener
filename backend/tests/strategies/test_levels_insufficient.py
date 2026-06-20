import pytest

from backend.src.strategies.levels import derive_bounded_levels


def _derive(row):
    return derive_bounded_levels(
        row,
        risk_distance_atr_lo=1.0,
        risk_distance_atr_hi=4.0,
        take_profit_r_multiple=3.0,
        reward_ceiling_z=2.5,
        reward_ceiling_use_fair_value=False,
        holding_period_days={"min": 60, "max": 180},
        structure_stop_buffer_atr=0.25,
        stop_mode="trend",
    )


@pytest.mark.parametrize(
    "row",
    [
        {"close": 100.0, "atr": None, "sma_200": 80.0, "contraction_low_20": 95.0},
        {"close": 100.0, "atr": 2.0, "sma_200": None, "contraction_low_20": 95.0},
        {"close": 100.0, "atr": 2.0, "sma_200": 80.0, "contraction_low_20": None},
    ],
)
def test_missing_required_inputs_return_explicit_insufficient_state(row):
    levels = _derive(row)

    assert levels["levels_state"] == "insufficient_data"
    assert levels["stop_loss"] is None
    assert levels["take_profit"] is None
    assert levels["risk_distance"] is None
    assert levels["reward_distance"] is None
    assert levels["rationale"]
