"""US6 / FR-012, FR-013 — honest level rationale (Decision 8).

The rationale must name the constraint that *actually set* the stop (the ATR
risk cap/floor when it bound, not the SMA/structure rule that it overrode), and
must not present a non-binding reward ceiling as if it constrained the target.
Structure-stop mode with a missing swing low stays ``insufficient_data`` rather
than silently relabelling the ATR fallback.
"""

from backend.src.strategies.levels import derive_bounded_levels


BANNED_DIRECTIVE_WORDS = ("buy", "sell", "recommended", "strong buy")


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


# (a) When the ATR risk cap bound the stop, attribute it to the cap, not the SMA rule.
def test_rationale_attributes_stop_to_risk_cap_not_sma_rule():
    # sma_200 far below entry ⇒ raw risk (30) exceeds the 4*ATR cap (8) ⇒ risk_cap binds.
    levels = _bounded(
        {"close": 100.0, "atr": 2.0, "sma_200": 70.0, "contraction_low_20": 96.0}
    )

    assert levels["levels_state"] == "ok"
    assert "risk_cap" in levels["bounds_applied"]

    rationale = levels["rationale"].lower()
    assert "risk cap" in rationale
    # The SMA rule did not set the stop, so it must not be credited for it.
    assert "sma" not in rationale
    assert "200-day" not in rationale
    for word in BANNED_DIRECTIVE_WORDS:
        assert word not in rationale


def test_rationale_attributes_stop_to_risk_floor_when_it_binds():
    # sma_200 just below entry ⇒ raw risk (0.5) under the 1*ATR floor (2.0) ⇒ risk_floor binds.
    levels = _bounded(
        {"close": 100.0, "atr": 2.0, "sma_200": 99.5, "contraction_low_20": 98.0}
    )

    assert levels["levels_state"] == "ok"
    assert "risk_floor" in levels["bounds_applied"]

    rationale = levels["rationale"].lower()
    assert "risk floor" in rationale
    assert "sma" not in rationale


def test_rationale_names_stop_rule_when_no_atr_bound_applies():
    # Raw SMA risk (8) sits inside [1,4]*ATR=[2,8] ⇒ the SMA rule genuinely set the stop.
    levels = _bounded(
        {"close": 100.0, "atr": 2.0, "sma_200": 92.0, "contraction_low_20": 96.0}
    )

    assert levels["levels_state"] == "ok"
    assert "risk_cap" not in levels["bounds_applied"]
    assert "risk_floor" not in levels["bounds_applied"]

    rationale = levels["rationale"].lower()
    assert "200-day sma" in rationale


# (b) The reward ceiling is only claimed when it actually bound.
def test_rationale_omits_reward_ceiling_when_none_binds():
    # Default vol-horizon ceiling (2.5*ATR*sqrt(180) ~ 33.5*ATR) can never bind a
    # <=12*ATR target, and fair-value is off ⇒ no ceiling should be claimed.
    levels = _bounded(
        {"close": 100.0, "atr": 2.0, "sma_200": 92.0, "contraction_low_20": 96.0}
    )

    assert levels["levels_state"] == "ok"
    assert levels["reward_ceiling_basis"] == "r_multiple"
    assert "reward_ceiling" not in levels["bounds_applied"]
    assert "ceiling" not in levels["rationale"].lower()


def test_rationale_names_reward_ceiling_when_it_binds():
    # A trusted fair value just above entry gives a genuinely binding ceiling.
    levels = _bounded(
        {"close": 100.0, "atr": 2.0, "sma_200": 92.0, "contraction_low_20": 96.0},
        reward_ceiling_use_fair_value=True,
        fair_value=105.0,
        fair_value_trusted=True,
    )

    assert levels["levels_state"] == "ok"
    assert levels["reward_ceiling_basis"] == "fair_value"
    assert "reward_ceiling" in levels["bounds_applied"]

    rationale = levels["rationale"].lower()
    assert "fair value ceiling" in rationale


# (c) Structure-stop mode with a missing swing low stays honest.
def test_structure_mode_missing_swing_low_is_insufficient_not_relabelled():
    levels = _bounded(
        {"close": 100.0, "atr": 2.0, "sma_200": 92.0, "contraction_low_20": None},
        stop_mode="structure",
    )

    assert levels["levels_state"] == "insufficient_data"
    assert levels["stop_loss"] is None
    assert levels["take_profit"] is None
    # No fabricated structure-stop rationale for a stop that was never derived.
    rationale = levels["rationale"].lower()
    assert "swing-low" in rationale or "swing low" in rationale
    assert "structure stop" not in rationale
