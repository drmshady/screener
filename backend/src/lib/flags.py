from __future__ import annotations

import os

from . import hosting

# Operator-override flags, following the same env-var convention used inside the
# strategy modules (e.g. SCREENER_TREAT_STRATEGY_VALID, SCREENER_GATE_MODE).

_TRUTHY = {"1", "true", "yes", "on"}


def personal_use_directive() -> bool:
    """Whether the advisor prompt may use directive (take/pass/size) framing.

    DEFAULT OFF. The app's no-advice boundary (constitution Principle V) applies
    by default; this flag enables the personal-use, single-user exception. It may
    only be defaulted on after the Principle V amendment scoping that exception
    (see specs/004-advisor-prompt-export/plan.md, Complexity Tracking).
    Override with SCREENER_PERSONAL_USE_DIRECTIVE=1.
    """
    if hosting.hosted_mode():
        return False
    return os.getenv("SCREENER_PERSONAL_USE_DIRECTIVE", "0").strip().lower() in _TRUTHY


# --- Feature 011: realistic-levels / risk-aware-sizing knobs --------------
# Placeholder defaults below are finalized empirically by the US4 comparison
# artifact (specs/011-auto-refresh-risk-sizing/research.md Decision 6); the
# applied final values land in T035. Each is env-overridable like the flags
# above and like the existing per-strategy StrategyParameter idiom
# (see midterm_52w_high_momentum.PARAMETERS).


def risk_distance_atr_lo() -> float:
    """Lower bound on the level risk distance (entry - stop), in multiples of ATR.

    Range: 0.5-2.0x ATR. Default 1.0 (placeholder, see Decision 6).
    Override with SCREENER_RISK_DISTANCE_ATR_LO.
    """
    return float(os.getenv("SCREENER_RISK_DISTANCE_ATR_LO", "1.0"))


def risk_distance_atr_hi() -> float:
    """Upper bound on the level risk distance (entry - stop), in multiples of ATR.

    Range: 2.0-6.0x ATR. Default 4.0 (placeholder, see Decision 6). Clamping the
    risk distance into [lo, hi]*ATR keeps a far-below-trend stop from blowing up
    the R-multiple reward target (FR-008).
    Override with SCREENER_RISK_DISTANCE_ATR_HI.
    """
    return float(os.getenv("SCREENER_RISK_DISTANCE_ATR_HI", "4.0"))


def reward_ceiling_z() -> float:
    """Volatility/horizon reward-ceiling multiplier (z * ATR * sqrt(horizon-days)).

    Range: 1.5-4.0. Default 2.5 (placeholder, see Decision 6). Bounds take_profit
    so it never implies an implausible move (FR-009).
    Override with SCREENER_REWARD_CEILING_Z.
    """
    return float(os.getenv("SCREENER_REWARD_CEILING_Z", "2.5"))


def reward_ceiling_use_fair_value() -> bool:
    """Whether the reward ceiling may also be capped by a trusted fair-value estimate.

    Default OFF (placeholder, see Decision 6) until US4 selects the fair-value
    basis and validates it as a reliable ceiling input (FR-009/018).
    Override with SCREENER_REWARD_CEILING_USE_FAIR_VALUE=1.
    """
    return os.getenv("SCREENER_REWARD_CEILING_USE_FAIR_VALUE", "0").strip().lower() in _TRUTHY


def risk_per_trade_fraction() -> float:
    """Capital fraction risked to the stop on a single position (the sizing backbone).

    Range: 0.0025-0.02 (0.25%-2% of capital). Default 0.01 (placeholder, see
    Decision 6). Used as `f` in `shares ~= f*capital / (entry - stop_loss)` (FR-013).
    Override with SCREENER_RISK_PER_TRADE_FRACTION.
    """
    return float(os.getenv("SCREENER_RISK_PER_TRADE_FRACTION", "0.01"))
