"""Shared, pure level-derivation helper (feature 011 US2).

`derive_bounded_levels` is the single implementation both
`midterm_52w_high_momentum.derive_levels` and `midterm_value_composite.derive_levels`
delegate to, so the two mid-term strategies compute realistic, bounded risk levels
identically (contracts/risk-levels.md). It does not change either strategy's
screening rules, gates, ranking, or citation — levels are a post-screen overlay.

Contract (contracts/risk-levels.md):

1. ``entry = close``.
2. Start from the existing technical stop, then clamp
   ``risk_distance = entry - stop_loss`` into ``[lo, hi] * atr`` (plus a
   low-price fraction cap) so ``0 < stop_loss < entry``.
3. ``take_profit = entry + R * risk_distance``, capped at the reward ceiling —
   ``min(volatility_horizon_limit, fair_value_if_trusted, measured_move_if_used)``
   — recording which basis bound it (``reward_ceiling_basis``).
4. A missing required input (close/atr/sma_200/swing-low, depending on stop
   mode) yields ``levels_state = "insufficient_data"`` with
   ``stop_loss = take_profit = None`` — never a degenerate number.
5. The returned ``rationale`` is neutral and zero-directive: it names the stop
   rule used and the binding reward ceiling, never "buy"/"sell"/"recommended".

This module currently only declares the signature (US2/T018 fills in the real
derivation); calling it returns the ``insufficient_data`` stub for every input.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _horizon_days(holding_period_days: Mapping[str, Any] | None) -> float:
    if not holding_period_days:
        return 180.0
    value = _as_float(holding_period_days.get("max"))
    return value if value and value > 0 else 180.0


def _insufficient(entry: float | None = None, reason: str | None = None) -> dict[str, Any]:
    return {
        "entry": entry,
        "stop_loss": None,
        "tighter_stop_loss": None,
        "take_profit": None,
        "risk_distance": None,
        "reward_distance": None,
        "reward_ceiling_basis": None,
        "bounds_applied": [],
        "levels_state": "insufficient_data",
        "rationale": reason or "Insufficient data to derive bounded levels.",
    }


def derive_bounded_levels(
    row: Mapping[str, Any],
    *,
    risk_distance_atr_lo: float,
    risk_distance_atr_hi: float,
    take_profit_r_multiple: float,
    reward_ceiling_z: float,
    reward_ceiling_use_fair_value: bool,
    fair_value: float | None = None,
    fair_value_trusted: bool = False,
    holding_period_days: Mapping[str, Any] | None = None,
    structure_stop_buffer_atr: float = 0.25,
    stop_mode: str = "trend",
) -> dict[str, Any]:
    """Derive bounded entry/stop/target levels for one screen row.

    Return the backward-compatible level keys plus feature-011 metadata. The
    helper is pure and deterministic; callers provide already-resolved knobs.
    """

    entry = _as_float(row.get("close"))
    atr = _as_float(row.get("atr"))
    sma_200 = _as_float(row.get("sma_200"))
    contraction_low_20 = _as_float(row.get("contraction_low_20"))

    if entry is None or entry <= 0:
        return _insufficient(entry, "Insufficient price data to derive bounded levels.")
    if atr is None or atr <= 0:
        return _insufficient(entry, "Insufficient ATR data to derive bounded levels.")
    if sma_200 is None or sma_200 <= 0:
        return _insufficient(entry, "Insufficient 200-day SMA data to derive bounded levels.")
    if contraction_low_20 is None or contraction_low_20 <= 0:
        return _insufficient(entry, "Insufficient swing-low data to derive bounded levels.")

    atr_stop = entry - (3.0 * atr)
    trend_stop = sma_200 if 0 < sma_200 < entry else atr_stop
    structure_stop = contraction_low_20 - (structure_stop_buffer_atr * atr)
    if structure_stop <= 0 or structure_stop >= entry:
        structure_stop = atr_stop

    active_mode = str(stop_mode).strip().lower()
    raw_stop = structure_stop if active_mode == "structure" else trend_stop
    stop_rule = (
        "20-day swing-low structure stop"
        if active_mode == "structure"
        else "200-day SMA trend stop"
    )
    if raw_stop <= 0 or raw_stop >= entry:
        raw_stop = atr_stop
        stop_rule = "3-ATR fallback stop"

    raw_risk = entry - raw_stop
    lo = max(0.0, float(risk_distance_atr_lo)) * atr
    hi = max(lo, float(risk_distance_atr_hi) * atr)
    # Keep low-priced names from receiving a stop that is implausibly far below
    # entry even when ATR is large relative to price.
    max_risk = max(0.01, min(hi, entry * 0.5, entry - 0.01))
    min_risk = min(lo, max_risk)

    bounds_applied: list[str] = []
    risk_distance = raw_risk
    if risk_distance < min_risk:
        risk_distance = min_risk
        bounds_applied.append("risk_floor")
    if risk_distance > max_risk:
        risk_distance = max_risk
        bounds_applied.append("risk_cap")

    stop_loss = entry - risk_distance
    if not (0 < stop_loss < entry):
        return _insufficient(entry, "Insufficient data to derive a positive bounded stop.")

    r_distance = max(0.0, float(take_profit_r_multiple)) * risk_distance
    vol_distance = max(0.0, float(reward_ceiling_z)) * atr * math.sqrt(
        _horizon_days(holding_period_days)
    )
    reward_distance = r_distance
    reward_ceiling_basis = "r_multiple"

    if vol_distance > 0 and vol_distance < reward_distance:
        reward_distance = vol_distance
        reward_ceiling_basis = "volatility_horizon"
        bounds_applied.append("reward_ceiling")

    trusted_fair_value = _as_float(fair_value)
    if (
        reward_ceiling_use_fair_value
        and fair_value_trusted
        and trusted_fair_value is not None
        and trusted_fair_value > entry
    ):
        fair_value_distance = trusted_fair_value - entry
        if fair_value_distance < reward_distance:
            reward_distance = fair_value_distance
            reward_ceiling_basis = "fair_value"
            bounds_applied.append("reward_ceiling")

    if reward_distance <= 0:
        return _insufficient(entry, "Insufficient reward room to derive bounded levels.")

    take_profit = entry + reward_distance

    # Honest rationale (Decision 8 / FR-012, FR-013): name the constraint that
    # actually set the stop, and only claim a reward ceiling when one bound.
    if "risk_cap" in bounds_applied:
        stop_clause = (
            f"Stop set by the ATR risk cap, which bounded the risk distance to "
            f"{risk_distance:.2f}"
        )
    elif "risk_floor" in bounds_applied:
        stop_clause = (
            f"Stop set by the ATR risk floor, which held the risk distance at "
            f"{risk_distance:.2f}"
        )
    else:
        stop_clause = (
            f"Stop uses the {stop_rule} with risk distance {risk_distance:.2f}"
        )

    if "reward_ceiling" in bounds_applied:
        reward_clause = (
            f"target uses {take_profit_r_multiple:g}R, capped by the "
            f"{reward_ceiling_basis.replace('_', ' ')} ceiling"
        )
    else:
        reward_clause = f"target uses {take_profit_r_multiple:g}R"

    rationale = f"{stop_clause}; {reward_clause}."

    return {
        "entry": entry,
        "stop_loss": stop_loss,
        "tighter_stop_loss": structure_stop if 0 < structure_stop < entry else None,
        "take_profit": take_profit,
        "risk_distance": risk_distance,
        "reward_distance": reward_distance,
        "reward_ceiling_basis": reward_ceiling_basis,
        "bounds_applied": bounds_applied,
        "levels_state": "ok",
        "rationale": rationale,
    }
