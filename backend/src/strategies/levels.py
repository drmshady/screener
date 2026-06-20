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

from typing import Any, Mapping


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
) -> dict[str, Any]:
    """Derive bounded entry/stop/target levels for one screen row.

    Stub (T007): no derivation logic yet — every call returns the
    ``insufficient_data`` shape. US2/T018 implements the real clamp + ceiling
    + rationale per ``contracts/risk-levels.md``.
    """

    return {
        "entry": None,
        "stop_loss": None,
        "tighter_stop_loss": None,
        "take_profit": None,
        "risk_distance": None,
        "reward_distance": None,
        "reward_ceiling_basis": None,
        "bounds_applied": [],
        "levels_state": "insufficient_data",
        "rationale": "Insufficient data to derive levels.",
    }
