import json

from backend.src.strategies.levels import derive_bounded_levels


BANNED_DIRECTIVE_WORDS = ("buy", "sell", "recommended", "strong buy")


def _derive():
    return derive_bounded_levels(
        {
            "close": 100.0,
            "atr": 2.0,
            "sma_200": 70.0,
            "contraction_low_20": 96.0,
        },
        risk_distance_atr_lo=1.0,
        risk_distance_atr_hi=4.0,
        take_profit_r_multiple=3.0,
        reward_ceiling_z=2.5,
        reward_ceiling_use_fair_value=True,
        fair_value=115.0,
        fair_value_trusted=True,
        holding_period_days={"min": 60, "max": 180},
        structure_stop_buffer_atr=0.25,
        stop_mode="trend",
    )


def test_bounded_levels_are_byte_identical_for_fixed_input():
    first = json.dumps(_derive(), sort_keys=True, separators=(",", ":"))
    second = json.dumps(_derive(), sort_keys=True, separators=(",", ":"))

    assert first == second


def test_rationale_names_stop_rule_and_binding_ceiling_without_directive_language():
    levels = _derive()
    rationale = levels["rationale"].lower()

    assert "stop" in rationale
    assert "ceiling" in rationale
    assert levels["reward_ceiling_basis"] == "fair_value"
    for word in BANNED_DIRECTIVE_WORDS:
        assert word not in rationale
