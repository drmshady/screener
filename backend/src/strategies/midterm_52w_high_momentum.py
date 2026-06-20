import json
import os
from pathlib import Path

import pandas as pd

from ..lib import flags
from ..models.strategy import BacktestSummary, Modification, Strategy, StrategyParameter
from ..screening.integrity.contract import OutputContract
from ..screening.integrity.invariants import (
    aggregate_flag_count,
    coherence_dist_to_high,
    coherence_entry_eq_close,
    gate_satisfied,
    identity_single_share_class,
    level_sanity,
    score_reproduces,
    series_integrity,
    value_domain_finite,
    value_domain_high_plausible,
    value_domain_positive,
    value_domain_realized_vol_floor,
    value_domain_return_plausible,
)
from ._helpers.quality import gross_profitability_mask, passes_quality_screen
from ._helpers.reference_thresholds import load_reference_thresholds
from ._helpers.sector_rank import rank_within_sector
from ._helpers.vol_scaling import calculate_volatility_scalar
from ._registry import registry
from .levels import derive_bounded_levels

# Operator override (2026-06-10): treat this strategy as valid / enabled-by-default
# for now, even though the backtest's survivorship_bias check still FAILS (the free
# Stooq bundle has no delisted tickers — see T049b). This does NOT alter the bias
# check or the backtest artifact, which continue to report survivorship as failed and
# stay visible in the UI; it only flips the enable flag. Set SCREENER_TREAT_STRATEGY_VALID=0
# (or change the default below to False) to restore strict constitutional gating.
OPERATOR_TREAT_AS_VALID = os.getenv("SCREENER_TREAT_STRATEGY_VALID", "1") != "0"

# Stop-loss exit mode (T148b). "trend" (default) = Faber 200-day SMA trailing
# stop; "structure" = a hard stop just below the recent consolidation support
# (the 20-day swing low), matching the canonical 52-week-high breakout workflow.
# The default stays "trend" so the committed backtest baseline is unchanged;
# set SCREENER_MIDTERM_STOP_MODE=structure to switch without editing code.
_VALID_STOP_MODES = {"trend", "structure"}

NAME = "Mid-Term 52-Week High Momentum"
CITATION = "George & Hwang (2004)"
TIMEFRAME = "Mid-term"
DESCRIPTION = "Ranks liquid stocks near their 52-week high using momentum, quality, and sector concentration gates."

HOLDING_PERIOD = {"min": 60, "max": 180}

PARAMETERS = {
    "lookback_days": StrategyParameter(
        default=252, type="int", description="Lookback window for high"
    ),
    "proximity_pct": StrategyParameter(
        default=0.05,
        min=0.01,
        max=0.20,
        type="float",
        description="Max distance from high",
    ),
    "max_per_sector": StrategyParameter(
        default=5, type="int", description="Max candidates per sector"
    ),
    "max_debt_equity": StrategyParameter(
        default=1.5,
        min=0.0,
        max=5.0,
        type="float",
        description="Debt/equity quality ceiling",
    ),
    "target_volatility": StrategyParameter(
        default=0.12,
        min=0.05,
        max=0.30,
        type="float",
        description="Annualized volatility target",
    ),
    "trend_sma_length": StrategyParameter(
        default=200,
        min=50,
        max=300,
        type="int",
        description="Per-stock trend SMA length for confirmation and exit",
    ),
    "min_gp_assets_percentile": StrategyParameter(
        default=0.5,
        min=0.0,
        max=0.95,
        type="float",
        description="Minimum universe percentile of gross profit / total assets to keep (0.5 = top half)",
    ),
    "max_asset_growth_percentile": StrategyParameter(
        default=0.5,
        min=0.05,
        max=1.0,
        type="float",
        description="Keep only firms in the LOW asset-growth bottom fraction of the universe (0.5 = bottom half; 1.0 disables). George-Hwang-Lin q-theory: the 52w-high premium concentrates in low-asset-growth firms. Fails open when asset_growth is unavailable.",
    ),
    "take_profit_r_multiple": StrategyParameter(
        default=3.0,
        min=1.0,
        max=10.0,
        type="float",
        description="Take-profit target as a multiple of risk (entry minus stop)",
    ),
    "min_volume_ratio": StrategyParameter(
        default=0.7,
        min=0.0,
        max=5.0,
        type="float",
        description="Volume not fading: recent 5-day average volume must be >= this multiple of the 50-day average (0 disables). Smoothed recent-window measure avoids single-day noise and does not penalize the quiet drift-up names the 52w-high effect rewards.",
    ),
    "sector_strength_top_fraction": StrategyParameter(
        default=1.0,
        min=0.0,
        max=1.0,
        type="float",
        description="Keep candidates only in the strongest top fraction of sectors by median proximity to 52w high (1.0 disables). DISABLED by default (2026-06-12): the median-over-all-names metric scored each sector by its far-from-high majority, so near-high names in broadly-weak sectors were excluded — it collapsed the live screen to ~0 and hurt the backtest. Re-enable only with a proper industry-momentum metric (sector breadth near highs).",
    ),
    "stop_mode": StrategyParameter(
        default="trend",
        type="enum",
        description="Exit mode: 'trend' = 200-day SMA trailing stop (Faber); 'structure' = hard stop below the 20-day consolidation low (breakout-workflow style). Override with SCREENER_MIDTERM_STOP_MODE.",
    ),
    "structure_stop_buffer_atr": StrategyParameter(
        default=0.25,
        min=0.0,
        max=2.0,
        type="float",
        description="When stop_mode='structure', place the stop this many ATRs below the 20-day swing low ('just below support').",
    ),
}

REGIME_FAVORABILITY = {
    "Trending up": "Favorable",
    "Range-bound": "Neutral",
    "Trending down": "Unfavorable",
}

MODIFICATIONS = [
    Modification(
        name="Volatility scaling",
        description="Scales exposure by trailing six-month realized volatility.",
        citation="Barroso & Santa-Clara (2015), Momentum has its moments",
    ),
    Modification(
        name="Sector-relative ranking",
        description="Ranks within sectors and caps the result list per sector.",
        citation="Documented risk-control overlay for sector concentration",
    ),
    Modification(
        name="Quality screen",
        description="Excludes high leverage or negative trailing free cash flow.",
        citation="Asness, Frazzini & Pedersen (2019), Quality Minus Junk",
    ),
    Modification(
        name="Gross-profitability gate",
        description="Keeps only the top half of the universe by gross profit / total assets.",
        citation="Novy-Marx (2013), The Other Side of Value: The Gross Profitability Premium",
    ),
    Modification(
        name="Low asset-growth gate",
        description="Keeps only the bottom half of the universe by year-over-year total-asset growth. The 52-week-high premium concentrates in high-momentum, LOW asset-growth firms; high investment/asset growth predicts lower returns. Fails open when point-in-time asset growth is unavailable.",
        citation="George, Hwang & Li (2018), The 52-Week High, q-Theory, and the Cross-Section of Stock Returns; Hou, Xue & Zhang (2015), Digesting Anomalies: An Investment Approach",
    ),
    Modification(
        name="Trend confirmation & exit",
        description="Requires price above its 200-day SMA at entry and uses the 200-day SMA as the trend-following stop.",
        citation="Faber (2007), A Quantitative Approach to Tactical Asset Allocation",
    ),
    Modification(
        name="Volume confirmation",
        description="Requires recent (5-day average) volume to hold near or above the 50-day average so proximity to the high is not on collapsing participation. Smoothed recent-window measure (not a single-day spike) — the 52w-high anchoring effect favors quiet underreaction drift, so this only screens out fading names.",
        citation="Standard liquidity/participation check (the 52w-high literature does not itself prescribe a volume rule)",
    ),
    Modification(
        name="Sector strength gate",
        description="Keeps candidates only in sectors whose own breadth is near 52-week highs; the 52-week-high effect is materially stronger when the stock's industry is also leading.",
        citation="Moskowitz & Grinblatt (1999), Do Industries Explain Momentum?",
    ),
]


def _load_backtest_summary() -> BacktestSummary | None:
    path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "backtests"
        / "midterm_52w_high_momentum.json"
    )
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary_metrics", {})
    source = (payload.get("data_sources") or [{}])[0]
    return BacktestSummary(
        data_window_start=payload["data_window_start"],
        data_window_end=payload["data_window_end"],
        total_return=float(summary.get("total_return", 0)),
        max_drawdown=float(summary.get("max_drawdown", 0)),
        hit_rate=float(summary.get("hit_rate", 0)),
        avg_win=float(summary.get("avg_win", 0)),
        avg_loss=float(summary.get("avg_loss", 0)),
        turnover=float(summary.get("turnover", 0)),
        source_name=str(source.get("source_name", "unknown")),
        source_as_of=str(source.get("source_as_of", payload.get("computed_at", ""))),
    )


def _backtest_bias_passes() -> bool:
    path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "backtests"
        / "midterm_52w_high_momentum.json"
    )
    if not path.exists():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    bias_check = payload.get("bias_check", {})
    return bool(bias_check) and all(
        item.get("passed") is True for item in bias_check.values()
    )


def _is_missing(value) -> bool:
    return value is None or pd.isna(value)


def _as_float(value) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _status(ok: bool) -> str:
    return "pass" if ok else "fail"


def evaluation_context(
    universe_df: pd.DataFrame,
    *,
    strong_sectors: set[str] | None = None,
    vol_col: str | None = None,
    gp_applied: bool = False,
    ag_applied: bool = False,
    single_ticker: bool = False,
) -> dict:
    """Build row-evaluation context for screen and single-ticker paths."""
    return {
        "trend_applied": "sma_200" in universe_df.columns,
        "volume_applied": PARAMETERS["min_volume_ratio"].default > 0
        and vol_col is not None,
        "vol_col": vol_col,
        "min_volume_ratio": PARAMETERS["min_volume_ratio"].default,
        "sector_applied": strong_sectors is not None,
        "strong_sectors": strong_sectors,
        "gp_applied": gp_applied,
        "ag_applied": ag_applied,
        "single_ticker": single_ticker,
    }


def evaluate(row, context: dict | None = None) -> list[dict]:
    """Evaluate one strategy row without filtering it out."""
    context = context or evaluation_context(
        pd.DataFrame([dict(row)]), single_ticker=True
    )
    out: list[dict] = []

    close = _as_float(row.get("close"))
    high_52w = _as_float(row.get("52w_high"))
    dist = _as_float(row.get("dist_to_high"))
    if dist is None and close and high_52w is not None:
        dist = (high_52w - close) / close
    proximity_limit = float(PARAMETERS["proximity_pct"].default)
    if dist is None:
        out.append(
            {
                "gate": "52-week-high proximity",
                "status": "skipped",
                "detail": "close or 52-week high is unavailable",
            }
        )
    else:
        passed = dist <= proximity_limit
        out.append(
            {
                "gate": "52-week-high proximity",
                "status": _status(passed),
                "detail": (
                    f"{dist * 100:.1f}% below the 52-week high "
                    f"({'within' if passed else 'above'} the {proximity_limit * 100:.0f}% limit)"
                ),
            }
        )

    sma_200 = _as_float(row.get("sma_200"))
    if context.get("trend_applied") and close is not None and sma_200 is not None:
        passed = close > sma_200
        out.append(
            {
                "gate": "Trend (above 200-day SMA)",
                "status": _status(passed),
                "detail": f"close ${close:.2f} is {'above' if passed else 'at/below'} the 200-day SMA ${sma_200:.2f}",
            }
        )
    else:
        out.append(
            {
                "gate": "Trend (above 200-day SMA)",
                "status": "skipped",
                "detail": "200-day SMA unavailable for this name",
            }
        )

    vol_col = context.get("vol_col")
    min_volume_ratio = float(
        context.get("min_volume_ratio", PARAMETERS["min_volume_ratio"].default)
    )
    volume_value = _as_float(row.get(vol_col)) if vol_col is not None else None
    if context.get("volume_applied") and volume_value is not None:
        passed = volume_value >= min_volume_ratio
        out.append(
            {
                "gate": "Volume confirmation",
                "status": _status(passed),
                "detail": f"recent volume {volume_value:.2f}x the 50-day average (min {min_volume_ratio:g}x)",
            }
        )
    else:
        out.append(
            {
                "gate": "Volume confirmation",
                "status": "skipped",
                "detail": (
                    "volume history unavailable (passed through)"
                    if context.get("volume_applied")
                    else "volume-confirmation gate not applied"
                ),
            }
        )

    if context.get("sector_applied"):
        sector = str(row.get("sector", "Unclassified"))
        strong = set(context.get("strong_sectors") or set())
        passed = sector in strong
        out.append(
            {
                "gate": "Sector strength",
                "status": _status(passed),
                "detail": f"{sector} is {'among' if passed else 'outside'} the leading sectors by proximity to highs",
            }
        )
    else:
        detail = (
            "needs universe context to rank sector breadth"
            if context.get("single_ticker")
            else "universe too small/narrow to rank sector breadth"
        )
        out.append({"gate": "Sector strength", "status": "skipped", "detail": detail})

    de = _as_float(row.get("debt_to_equity"))
    fcf = _as_float(row.get("fcf_ttm"))
    max_de = float(PARAMETERS["max_debt_equity"].default)
    if de is None or fcf is None:
        out.append(
            {
                "gate": "Quality (leverage + cash flow)",
                "status": "skipped",
                "detail": "debt/equity or free cash flow unavailable",
            }
        )
    else:
        passed = passes_quality_screen(de, fcf, max_de)
        out.append(
            {
                "gate": "Quality (leverage + cash flow)",
                "status": _status(passed),
                "detail": f"debt/equity {de:.2f} {'<=' if de <= max_de else '>'} {max_de:g}; free cash flow {'positive' if fcf > 0 else 'not positive'}",
            }
        )

    if context.get("gp_applied"):
        gpa = _as_float(row.get("gp_to_assets"))
        gp_pass = bool(row.get("_gp_pass", True))
        out.append(
            {
                "gate": "Gross profitability",
                "status": _status(gp_pass),
                "detail": (
                    f"gross profit/assets {gpa:.2f} is {'in' if gp_pass else 'below'} the universe's top half"
                    if gpa is not None
                    else "gross-profit/assets percentile evaluated"
                ),
            }
        )
    else:
        detail = (
            "needs universe context to compute the gross-profitability percentile"
            if context.get("single_ticker")
            else "gross-profit/assets data unavailable for this universe"
        )
        out.append(
            {"gate": "Gross profitability", "status": "skipped", "detail": detail}
        )

    if context.get("ag_applied"):
        ag = _as_float(row.get("asset_growth"))
        if ag is None:
            out.append(
                {
                    "gate": "Low asset growth",
                    "status": "skipped",
                    "detail": "asset-growth data unavailable (passed through)",
                }
            )
        else:
            ag_pass = bool(row.get("_ag_pass", True))
            out.append(
                {
                    "gate": "Low asset growth",
                    "status": _status(ag_pass),
                    "detail": f"asset growth {ag * 100:.1f}% is {'in' if ag_pass else 'above'} the low (bottom-half) group",
                }
            )
    else:
        detail = (
            "needs universe context to compute the asset-growth percentile"
            if context.get("single_ticker")
            else "asset-growth data unavailable for this universe"
        )
        out.append({"gate": "Low asset growth", "status": "skipped", "detail": detail})

    # Tier reclassification is opt-in. The default contract remains hard
    # pass/fail/skipped so the OpenAPI schema and regression tests stay stable.
    if _gate_mode() == "tiered":
        for gate in out:
            if gate["gate"] != "52-week-high proximity" and gate["status"] == "fail":
                gate["status"] = "warn"
    return out


def _gate_results_for_row(
    row,
    *,
    trend_applied: bool,
    volume_applied: bool,
    vol_col: str | None,
    min_volume_ratio: float,
    sector_applied: bool,
    gp_applied: bool,
    ag_applied: bool,
) -> list[dict]:
    """Backward-compatible wrapper for older tests/imports."""
    return evaluate(
        row,
        {
            "trend_applied": trend_applied,
            "volume_applied": volume_applied,
            "vol_col": vol_col,
            "min_volume_ratio": min_volume_ratio,
            "sector_applied": sector_applied,
            "strong_sectors": None,
            "gp_applied": gp_applied,
            "ag_applied": ag_applied,
            "single_ticker": False,
        },
    )


def derive_levels(row) -> dict[str, float | str | list[str] | None]:
    level_row = dict(row)
    swing_low = _as_float(level_row.get("contraction_low_20"))
    if swing_low is None or swing_low <= 0:
        close = _as_float(level_row.get("close"))
        atr = _as_float(level_row.get("atr"))
        buffer = float(PARAMETERS["structure_stop_buffer_atr"].default)
        if close is not None and atr is not None:
            level_row["contraction_low_20"] = close - ((3.0 - buffer) * atr)
    return derive_bounded_levels(
        level_row,
        risk_distance_atr_lo=flags.risk_distance_atr_lo(),
        risk_distance_atr_hi=flags.risk_distance_atr_hi(),
        take_profit_r_multiple=float(PARAMETERS["take_profit_r_multiple"].default),
        reward_ceiling_z=flags.reward_ceiling_z(),
        reward_ceiling_use_fair_value=flags.reward_ceiling_use_fair_value(),
        fair_value=level_row.get("fair_value"),
        fair_value_trusted=level_row.get("fair_value_trust_flag") == "trusted",
        holding_period_days=HOLDING_PERIOD,
        structure_stop_buffer_atr=float(PARAMETERS["structure_stop_buffer_atr"].default),
        stop_mode=_active_stop_mode(),
    )


def _attach_bounded_levels(frame: pd.DataFrame) -> pd.DataFrame:
    keys = (
        "entry",
        "stop_loss",
        "tighter_stop_loss",
        "take_profit",
        "risk_distance",
        "reward_distance",
        "reward_ceiling_basis",
        "bounds_applied",
        "levels_state",
        "rationale",
    )
    if frame.empty:
        for key in keys:
            frame[key] = []
        return frame
    level_rows = [derive_levels(row) for _, row in frame.iterrows()]
    for key in keys:
        frame[key] = [levels.get(key) for levels in level_rows]
    return frame


def _active_stop_mode() -> str:
    """Resolve the stop mode: env override wins, else the declared default."""
    mode = os.getenv("SCREENER_MIDTERM_STOP_MODE", PARAMETERS["stop_mode"].default)
    mode = str(mode).strip().lower()
    return mode if mode in _VALID_STOP_MODES else "trend"


def _gate_mode() -> str:
    """Gate mode. Default hard mode preserves the published validation contract:
    every declared gate filters. Set SCREENER_GATE_MODE=tiered for the Decision 7
    research variant where non-proximity gates warn and rank instead."""
    mode = os.getenv("SCREENER_GATE_MODE", "hard").strip().lower()
    return mode if mode in {"tiered", "hard"} else "hard"


def _strong_sectors_by_breadth(df: pd.DataFrame, top_fraction: float) -> set[str] | None:
    """Industry-momentum via sector BREADTH: a sector is 'leading' when a high
    fraction of its names are in an uptrend (above their 200-day SMA). Keep the top
    `top_fraction` of sectors by that breadth. Computed over the full universe so it
    reflects genuine sector participation (Moskowitz-Grinblatt industry momentum),
    NOT the old median-distance metric that was dominated by each sector's
    far-from-high majority. Returns None (gate not applied) when sector coverage is
    too thin for a stable estimate."""
    if not (0.0 < top_fraction < 1.0) or "sector" not in df.columns or "sma_200" not in df.columns:
        return None
    c = df[(df["sector"] != "Unclassified") & df["sma_200"].notna() & df["close"].notna()]
    counts = c.groupby("sector").size()
    eligible = counts[counts >= 3].index  # need a few names for a stable breadth
    c = c[c["sector"].isin(eligible)]
    if c["sector"].nunique() < 3:
        return None
    breadth = (
        (c["close"] > c["sma_200"]).groupby(c["sector"]).mean().sort_values(ascending=False)
    )
    keep_n = max(1, int(round(len(breadth) * top_fraction)))
    return set(breadth.head(keep_n).index)


def _sector_top_fraction(df: pd.DataFrame) -> float:
    """Sector-strength gate fraction: a per-run override passed via ``df.attrs``
    (so the UI can toggle the gate without changing the parameter default), else
    the parameter default. 1.0 disables the gate; 0 < f < 1 keeps the top f of
    sectors by breadth."""
    override = df.attrs.get("sector_strength_top_fraction") if hasattr(df, "attrs") else None
    if override is None:
        return float(PARAMETERS["sector_strength_top_fraction"].default)
    try:
        return float(override)
    except (TypeError, ValueError):
        return float(PARAMETERS["sector_strength_top_fraction"].default)


def _apply_cross_sectional_gates(df: pd.DataFrame) -> dict:
    """Set ``df['_gp_pass']`` (gross profitability) and ``df['_ag_pass']`` (low
    asset growth). Prefers FIXED reference-universe thresholds when cached, so a
    name's verdict doesn't flip with the screened slice (Shariah on/off, universe
    size); otherwise falls back to the contemporaneous-universe quantile. Returns
    a dict describing what ran, for honest gate accounting. Mutates ``df``."""
    ref = load_reference_thresholds()
    gp_pct = PARAMETERS["min_gp_assets_percentile"].default
    ag_top = PARAMETERS["max_asset_growth_percentile"].default

    # Gross profitability: keep names at/above the cut; missing GP fails closed.
    gp_applied = "gp_to_assets" in df.columns and df["gp_to_assets"].notna().any()
    gp_ref = bool(ref and ref.get("gp_threshold") is not None)
    if gp_applied and gp_ref:
        df["_gp_pass"] = df["gp_to_assets"].notna() & (df["gp_to_assets"] >= ref["gp_threshold"])
    elif gp_applied:
        df["_gp_pass"] = gross_profitability_mask(df["gp_to_assets"], gp_pct)
    else:
        df["_gp_pass"] = True

    # Low asset growth: keep names at/below the cut; missing AG fails OPEN.
    ag_applied = (
        ag_top < 1.0 and "asset_growth" in df.columns and df["asset_growth"].notna().any()
    )
    ag_ref = bool(ref and ref.get("ag_threshold") is not None)
    if ag_applied:
        threshold = ref["ag_threshold"] if ag_ref else df["asset_growth"].dropna().quantile(ag_top)
        df["_ag_pass"] = df["asset_growth"].isna() | (df["asset_growth"] <= threshold)
    else:
        df["_ag_pass"] = True

    return {
        "gp_applied": gp_applied,
        "ag_applied": ag_applied,
        "gp_ref": gp_ref and gp_applied,
        "ag_ref": ag_ref and ag_applied,
        "n_missing_ag": int(df["asset_growth"].isna().sum()) if "asset_growth" in df.columns else 0,
        "ag_disabled": ag_top >= 1.0,
        "ref_as_of": ref.get("as_of") if ref else None,
    }


def prepare_universe_gates(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, set[str] | None, bool, bool]:
    """Compute the cross-sectional gate inputs over a universe DataFrame:
    `_gp_pass` (top-half gross profitability), `_ag_pass` (bottom-half asset
    growth), `dist_to_high`, and the strong-sectors set. Returns
    (df, strong_sectors, gp_applied, ag_applied).

    Shared by the screen (`rules`) and single-ticker analysis so the percentile/
    rank gates are evaluated against the SAME universe distribution instead of
    being skipped for a single symbol.
    """
    df = df.copy()

    info = _apply_cross_sectional_gates(df)
    gp_applied = info["gp_applied"]
    ag_applied = info["ag_applied"]

    if "52w_high" in df.columns and "close" in df.columns:
        df["dist_to_high"] = (df["52w_high"] - df["close"]) / df["close"]

    strong_sectors = _strong_sectors_by_breadth(df, _sector_top_fraction(df))

    return df, strong_sectors, gp_applied, ag_applied


def rules(universe_df: pd.DataFrame) -> pd.DataFrame:
    """
    Evaluates the rules against the universe.
    universe_df must contain at least:
    - ticker, sector, close, 52w_high, fcf_ttm, debt_to_equity, atr
    Optional columns enable additional gates when the engine supplies them:
    - sma_200: per-stock trend confirmation + trend-following stop
    - gp_to_assets: Novy-Marx gross-profitability gate
    """
    if universe_df.empty:
        return pd.DataFrame()

    df = universe_df.copy()

    # Honest gate accounting (surfaced in ScreenResult.data_notes): every gate the
    # strategy declares either runs or is recorded as skipped with the reason why.
    gates_applied: list[str] = []
    gates_skipped: list[str] = []

    def _with_notes(frame: pd.DataFrame) -> pd.DataFrame:
        frame.attrs["gates_applied"] = list(gates_applied)
        frame.attrs["gates_skipped"] = list(gates_skipped)
        return frame

    # Cross-sectional gross-profitability (Novy-Marx) + low asset-growth
    # (George-Hwang-Li q-theory) gates. Thresholds come from a FIXED reference
    # universe when cached (so a name's verdict doesn't flip with the screened
    # slice — Shariah on/off, universe size); otherwise from this universe's own
    # quantile. See _apply_cross_sectional_gates / reference_thresholds.
    xs = _apply_cross_sectional_gates(df)
    ref_tag = " (vs reference universe)"
    if xs["gp_applied"]:
        gates_applied.append("top-half gross profitability" + (ref_tag if xs["gp_ref"] else ""))
    else:
        gates_skipped.append(
            "gross-profitability gate skipped: missing gp_to_assets fundamentals for this universe"
        )
    if xs["ag_applied"]:
        gates_applied.append("low asset growth" + (ref_tag if xs["ag_ref"] else ""))
        if xs["n_missing_ag"]:
            gates_skipped.append(
                f"asset-growth gate passed-through for {xs['n_missing_ag']} name(s) missing"
                " point-in-time asset growth (fails open)"
            )
    else:
        gates_skipped.append(
            "asset-growth gate disabled (max_asset_growth_percentile=1.0)"
            if xs["ag_disabled"]
            else "asset-growth gate skipped: missing asset_growth fundamentals for this universe"
        )

    # 1. 52-week high proximity
    df["dist_to_high"] = (df["52w_high"] - df["close"]) / df["close"]

    # Sector strength via BREADTH (industry momentum): keep names only in sectors
    # where a high fraction of members are in an uptrend (above their 200-day SMA).
    # Replaces the old median-distance-to-high metric, which was dominated by each
    # sector's far-from-high majority and excluded near-high names in broadly-weak
    # sectors. Skipped (fail-open) when sector coverage is too thin or disabled.
    strong_sectors = _strong_sectors_by_breadth(df, _sector_top_fraction(df))
    if strong_sectors is not None:
        gates_applied.append("leading sector")
    else:
        gates_skipped.append(
            "sector-strength gate skipped (disabled or too few classified sectors)"
        )

    # HARD gate (always filters): 52-week-high proximity — it IS the strategy.
    gates_applied.insert(0, "within 5% of 52-week high")
    matched = df[df["dist_to_high"] <= PARAMETERS["proximity_pct"].default]
    if matched.empty:
        return _with_notes(matched)

    # Decision 7: in TIERED mode the remaining gates are soft — they DON'T filter,
    # they warn + rank (computed later from per-row gate_results). In HARD mode
    # (legacy / backtest A/B) each one still excludes. Notes are recorded in both.
    hard_mode = _gate_mode() == "hard"

    # 1b. Sector strength gate (soft)
    if strong_sectors is not None and hard_mode:
        matched = matched[matched["sector"].isin(strong_sectors)]
        if matched.empty:
            return _with_notes(matched)

    # 1c. Volume confirmation: recent participation must not be collapsing (soft).
    min_volume_ratio = PARAMETERS["min_volume_ratio"].default
    vol_col = (
        "volume_ratio_recent"
        if "volume_ratio_recent" in matched.columns
        else ("volume_ratio_50" if "volume_ratio_50" in matched.columns else None)
    )
    if min_volume_ratio > 0 and vol_col is not None:
        vr = matched[vol_col]
        gates_applied.append("volume-confirmed")
        if vr.isna().any():
            gates_skipped.append(
                f"volume confirmation passed-through for {int(vr.isna().sum())} name(s)"
                " missing recent/50-day volume history"
            )
        if hard_mode:
            matched = matched[vr.isna() | (vr >= min_volume_ratio)]
            if matched.empty:
                return _with_notes(matched)
    else:
        gates_skipped.append(
            "volume-confirmation gate skipped: volume ratio unavailable"
            if min_volume_ratio > 0
            else "volume-confirmation gate disabled (min_volume_ratio=0)"
        )

    # 2. Trend confirmation: price above its long-term SMA (soft).
    if "sma_200" in matched.columns:
        gates_applied.append("above 200-day SMA")
        if hard_mode:
            matched = matched[
                matched["sma_200"].notna() & (matched["close"] > matched["sma_200"])
            ]
            if matched.empty:
                return _with_notes(matched)
    else:
        gates_skipped.append("trend-confirmation gate skipped: sma_200 unavailable")

    # 3. Quality screen — leverage + free cash flow (soft; "confirmed momentum").
    quality_input_missing = int(
        (matched["debt_to_equity"].isna() | matched["fcf_ttm"].isna()).sum()
    )
    gates_applied.append("low leverage + positive FCF")
    if quality_input_missing:
        gates_skipped.append(
            f"quality screen: {quality_input_missing} name(s) have missing fundamentals"
        )
    if hard_mode:
        matched = matched[
            matched.apply(
                lambda row: passes_quality_screen(
                    row["debt_to_equity"],
                    row["fcf_ttm"],
                    PARAMETERS["max_debt_equity"].default,
                ),
                axis=1,
            )
        ]
        if matched.empty:
            return _with_notes(matched)

    # 4. Gross-profitability gate (soft).
    if hard_mode:
        matched = matched[matched["_gp_pass"]]
        if matched.empty:
            return _with_notes(matched)

    # 4b. Low asset-growth gate (soft).
    if hard_mode:
        matched = matched[matched["_ag_pass"]]
        if matched.empty:
            return _with_notes(matched)

    # 5. Score candidates (closer to high is better)
    if "return_12_1" in matched.columns:
        matched["vol_scalar"] = matched.get(
            "daily_returns", pd.Series([None] * len(matched))
        ).apply(
            lambda value: (
                calculate_volatility_scalar(
                    value, PARAMETERS["target_volatility"].default
                )
                if isinstance(value, pd.Series)
                else 1.0
            )
        )
        matched["score"] = (
            matched["return_12_1"]
            * matched["vol_scalar"]
            / (1.0 + matched["dist_to_high"])
        )
    else:
        matched["score"] = 1.0 / (1.0 + matched["dist_to_high"])

    # 6. Sector-relative ranking
    matched = rank_within_sector(
        matched,
        score_column="score",
        max_per_sector=PARAMETERS["max_per_sector"].default,
    )

    matched = _attach_bounded_levels(matched)
    matched = matched[matched["levels_state"] == "ok"]
    if matched.empty:
        return _with_notes(matched)
    stop_label = "bounded risk-level overlay"
    # Per-candidate gate-by-gate breakdown (pass / warn / skipped, with values).
    gate_context = evaluation_context(
        matched,
        strong_sectors=strong_sectors,
        vol_col=vol_col,
        gp_applied=xs["gp_applied"],
        ag_applied=xs["ag_applied"],
    )
    matched["gate_results"] = [evaluate(r, gate_context) for _, r in matched.iterrows()]
    # Decision 7: per-row warnings (soft gates the name failed). In tiered mode a
    # listed candidate cleared the HARD gate (proximity) and carries these as
    # warnings; in hard mode there are none (those names were filtered out).
    matched["warnings"] = matched["gate_results"].apply(
        lambda gr: [g["gate"] for g in gr if g["status"] == "warn"]
    )
    matched["warning_count"] = matched["warnings"].apply(len)

    if hard_mode:
        matched["reason"] = f"{', '.join(gates_applied).capitalize()}; {stop_label}"
    else:
        def _row_reason(row) -> str:
            gr = row["gate_results"]
            passed = [g["gate"] for g in gr if g["status"] == "pass"]
            warned = [g["gate"] for g in gr if g["status"] == "warn"]
            parts: list[str] = []
            if passed:
                parts.append("Passed " + ", ".join(passed))
            if warned:
                parts.append("Warnings: " + ", ".join(warned))
            parts.append(stop_label)
            return "; ".join(parts)

        matched["reason"] = matched.apply(_row_reason, axis=1)

    # Tiered mode: rank the cleanest (fewest warnings) first, then by momentum.
    if not hard_mode and len(matched) > 1:
        matched = matched.sort_values(
            ["warning_count", "score"], ascending=[True, False]
        ).reset_index(drop=True)

    return _with_notes(matched.drop(columns=["_gp_pass", "_ag_pass"], errors="ignore"))


# Output-integrity contract (feature 008, T012; contracts/momentum-contract.md).
# The machine-checkable properties every returned candidate row must satisfy. The
# strategy-agnostic engine (screening/integrity/engine.py) validates each candidate
# against this on every live screen and in the offline harness — one definition,
# two enforcement points. This changes NOTHING about rules(), defaults, the
# citation, or REGIME_FAVORABILITY (FR-023); it only DECLARES what correct output
# looks like. Plausibility bounds marked [A/B] are initial defaults to calibrate on
# the 2026-06-12 snapshot (research Decision 9); the 10% divergence flag is fixed by
# the spec and lives in the harness cross-check, not here.
_RETURN_MIN = -0.95
_RETURN_MAX = 9.0  # [A/B] +900%
_HIGH_MAX_MULT = 12.0  # [A/B] 52w high at most 12x the close
_JUMP_MAX = 0.40  # [A/B] largest plausible single-session move absent a known action
# Realized-volatility floor (annualized). Below this, the vol_scalar saturates at
# its 2.0 cap (cap is reached at target_volatility/2.0 = 0.06) and inflates the
# score — the signature of a price pinned under a pending all-cash acquisition /
# cash tender (the EA-at-its-$210-offer defect, realized vol ~6%). Set at 0.08 to
# also catch the near-saturated band, while staying far below any genuine momentum
# candidate's realized vol. Detect + demote + warn only (no rule/default change).
_REALIZED_VOL_FLOOR = 0.08
_FINITE_FIGURES = (
    "close",
    "52w_high",
    "return_12_1",
    "atr",
    "score",
    "stop_loss",
    "take_profit",
)


def _momentum_score(row, signals):
    """Reproduce the rules() score: return_12_1 · vol_scalar / (1 + dist_to_high),
    with the no-momentum fallback rules() uses when return_12_1 is unavailable."""
    dist = row.get("dist_to_high")
    if dist is None or pd.isna(dist):
        return None
    ret = row.get("return_12_1")
    vol = row.get("vol_scalar")
    if ret is not None and not pd.isna(ret) and vol is not None and not pd.isna(vol):
        return float(ret) * float(vol) / (1.0 + float(dist))
    return 1.0 / (1.0 + float(dist))


OUTPUT_CONTRACT = OutputContract(
    strategy_slug="midterm_52w_high_momentum",
    invariants=[
        # coherence — surfaced figures agree with each other
        coherence_dist_to_high(),
        coherence_entry_eq_close(),
        # gate — a listed name actually clears the hard proximity gate
        gate_satisfied(
            name="gate.proximity",
            figure="dist_to_high",
            column="dist_to_high",
            threshold=float(PARAMETERS["proximity_pct"].default),
            message=(
                "candidate is listed but does not actually satisfy the "
                f"{PARAMETERS['proximity_pct'].default:.0%} proximity-to-high gate; "
                "verify before acting"
            ),
        ),
        # score — the ranking figure reproduces its declared formula
        score_reproduces(compute=_momentum_score, rel_tol=1e-3),
        # level — risk geometry is sane and matches the declared R-multiple
        *level_sanity(r_multiple=float(PARAMETERS["take_profit_r_multiple"].default)),
        # value_domain — figures finite, positive, and within plausible bounds
        value_domain_finite(_FINITE_FIGURES),
        value_domain_positive(["close", "atr"]),
        value_domain_return_plausible(lower=_RETURN_MIN, upper=_RETURN_MAX),
        value_domain_high_plausible(h_max=_HIGH_MAX_MULT),
        # pinned-price / merger-arb guard: collapsed realized vol saturates the
        # vol_scalar and inflates the score (the EA pending-acquisition defect).
        value_domain_realized_vol_floor(min_annualized_vol=_REALIZED_VOL_FLOOR),
        # series — the backing history is well-formed and adjustment-consistent
        # (reads the §8 signals computed in US3; defaults safe until then)
        *series_integrity(jump_max=_JUMP_MAX),
        # identity — price and fundamentals are one share class (FR-014)
        identity_single_share_class(),
        # aggregate — informational flagged-count note
        aggregate_flag_count(),
    ],
)


strategy = Strategy(
    slug="midterm_52w_high_momentum",
    name=NAME,
    timeframe=TIMEFRAME,
    citation=CITATION,
    description=DESCRIPTION,
    holding_period_days=HOLDING_PERIOD,
    parameters=PARAMETERS,
    regime_favorability=REGIME_FAVORABILITY,
    default_exclude_earnings_within_days=0,
    enabled_by_default=_backtest_bias_passes() or OPERATOR_TREAT_AS_VALID,
    modifications=MODIFICATIONS,
    rules=rules,
    backtest_summary=_load_backtest_summary(),
    output_contract=OUTPUT_CONTRACT,
)

registry.register(strategy)
