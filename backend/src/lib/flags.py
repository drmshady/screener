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


_FAIR_VALUE_BASES = {"valuation_yields", "intrinsic_model"}


def fair_value_basis() -> str:
    """Which free, point-in-time basis backs the fair-value estimate
    (indicators/fair_value.py): "valuation_yields" (book value per share from the
    existing book/market yield) or "intrinsic_model" (Graham number from the same
    yield-derived EPS/BVPS). Default "intrinsic_model" (placeholder, see Decision 6
    / contracts/fair-value.md — US4 picks empirically). Override with
    SCREENER_FAIR_VALUE_BASIS; an unrecognized value falls back to the default.
    """
    value = os.getenv("SCREENER_FAIR_VALUE_BASIS", "intrinsic_model").strip()
    return value if value in _FAIR_VALUE_BASES else "intrinsic_model"


_SIZING_CONVICTION_SIGNALS = {"fair_value", "inverse_vol", "strategy_rank", "none"}


def sizing_conviction_signal() -> str:
    """Which candidate conviction modulator (Decision 3) scales the risk-per-trade
    sizing backbone: "fair_value" (margin of safety), "inverse_vol" (lower
    volatility sized relatively larger), "strategy_rank" (higher-ranked candidate
    sized relatively larger), or "none" (the honest risk-per-trade-only baseline).
    Default "none" (placeholder, see Decision 6 — US4 picks the winner on real
    data; fair value is one candidate, not assumed). Override with
    SCREENER_SIZING_CONVICTION_SIGNAL; an unrecognized value falls back to "none".
    """
    value = os.getenv("SCREENER_SIZING_CONVICTION_SIGNAL", "none").strip()
    return value if value in _SIZING_CONVICTION_SIGNALS else "none"


def sizing_inverse_vol_baseline() -> float:
    """Reference ATR/price volatility the inverse-vol conviction modulator scales
    against (scale = baseline / candidate_volatility, clamped). Default 0.02
    (placeholder, see Decision 6). Only consulted when
    sizing_conviction_signal() == "inverse_vol". Override with
    SCREENER_SIZING_INVERSE_VOL_BASELINE.
    """
    return float(os.getenv("SCREENER_SIZING_INVERSE_VOL_BASELINE", "0.02"))


# --- Feature 012: entry-timing overlay knobs -------------------------------


def entry_pivot_max_extension() -> float:
    """Maximum allowed distance above the detected pivot for the entry overlay.

    Default 0.05 (5%). Override with SCREENER_ENTRY_PIVOT_MAX_EXT.
    """
    return float(os.getenv("SCREENER_ENTRY_PIVOT_MAX_EXT", "0.05"))


def entry_volume_ratio_min() -> float:
    """Minimum breakout-window volume ratio versus the 50-day average.

    Default 1.4x. Override with SCREENER_ENTRY_VOL_RATIO_MIN.
    """
    return float(os.getenv("SCREENER_ENTRY_VOL_RATIO_MIN", "1.4"))


def entry_volume_ratio_preferred() -> float:
    """Preferred/strong breakout-volume ratio label threshold.

    Default 1.5x. Override with SCREENER_ENTRY_VOL_RATIO_PREF.
    """
    return float(os.getenv("SCREENER_ENTRY_VOL_RATIO_PREF", "1.5"))


def entry_flat_base_min_weeks() -> float:
    """Minimum maturity for a detected flat base, in weeks."""
    return float(os.getenv("SCREENER_ENTRY_FLAT_BASE_MIN_WEEKS", "5"))


def entry_cup_base_min_weeks() -> float:
    """Minimum maturity for cup-family and double-bottom bases, in weeks."""
    return float(os.getenv("SCREENER_ENTRY_CUP_BASE_MIN_WEEKS", "7"))


def entry_base_depth_max() -> float:
    """Maximum supported base depth before the overlay marks the base as deep."""
    return float(os.getenv("SCREENER_ENTRY_BASE_DEPTH_MAX", "0.33"))


def entry_sma200_extension_max() -> float:
    """Maximum distance above SMA-200 before the overlay marks the name extended."""
    return float(os.getenv("SCREENER_ENTRY_SMA200_EXT_MAX", "0.40"))


def entry_climax_advance_min() -> float:
    """Trailing advance threshold for the climax-top disqualifier."""
    return float(os.getenv("SCREENER_ENTRY_CLIMAX_ADVANCE_MIN", "0.25"))


def entry_climax_prior_trend_weeks() -> float:
    """Required prior trend duration for the climax-top disqualifier."""
    return float(os.getenv("SCREENER_ENTRY_CLIMAX_PRIOR_TREND_WEEKS", "8"))


def entry_huge_gap_threshold() -> float:
    """Distance above pivot that marks a breakout gap as extended."""
    return float(os.getenv("SCREENER_ENTRY_HUGE_GAP_THRESHOLD", "0.05"))


# --- Feature 012 US2: expanded candidate coverage knobs --------------------

_GATE_TIERS = {"essential", "preferred", "disqualifier"}


def expanded_coverage() -> bool:
    """Whether a non-pass on a *preferred* gate retains + demotes the candidate
    instead of excluding it (FR-009/013).

    DEFAULT OFF — the screen is byte-identical to today's hard-mode behaviour
    (SC-009). The per-run screen ``expanded_coverage`` parameter takes precedence;
    this env default is the operator fallback. Override with
    SCREENER_EXPANDED_COVERAGE=1.
    """
    return os.getenv("SCREENER_EXPANDED_COVERAGE", "0").strip().lower() in _TRUTHY


def gate_tier_overrides() -> dict[str, str]:
    """Operator overrides for the per-strategy gate→tier map (FR-009).

    Format: ``SCREENER_GATE_TIER_OVERRIDES="sector strength=essential,relative
    strength=preferred"`` — a comma-separated list of ``<gate>=<tier>`` pairs.
    Gate names are matched case-insensitively; an unrecognized tier is ignored.
    """
    raw = os.getenv("SCREENER_GATE_TIER_OVERRIDES", "").strip()
    out: dict[str, str] = {}
    if not raw:
        return out
    for pair in raw.split(","):
        if "=" not in pair:
            continue
        gate, tier = pair.split("=", 1)
        gate = gate.strip().lower()
        tier = tier.strip().lower()
        if gate and tier in _GATE_TIERS:
            out[gate] = tier
    return out


# --- Feature 012 US3: Shariah cadence knobs --------------------------------


def shariah_refresh_interval_days() -> int:
    """Halal Terminal refresh cadence, in calendar days.

    Default 90 (~quarterly). Override with SCREENER_SHARIAH_REFRESH_INTERVAL_DAYS.
    """
    return int(os.getenv("SCREENER_SHARIAH_REFRESH_INTERVAL_DAYS", "90"))
