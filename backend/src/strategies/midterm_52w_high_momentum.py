import json
import os
from pathlib import Path

import pandas as pd

from ..models.strategy import BacktestSummary, Modification, Strategy, StrategyParameter
from ._helpers.quality import gross_profitability_mask, passes_quality_screen
from ._helpers.sector_rank import rank_within_sector
from ._helpers.vol_scaling import calculate_volatility_scalar
from ._registry import registry

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


def derive_levels(row) -> dict[str, float | None]:
    close = _as_float(row.get("close"))
    atr = _as_float(row.get("atr"))
    if close is None or atr is None:
        return {
            "entry": close,
            "stop_loss": None,
            "tighter_stop_loss": None,
            "take_profit": None,
        }
    entry = close
    atr_stop = entry - (3 * atr)
    sma_200 = _as_float(row.get("sma_200"))
    trend_stop = sma_200 if sma_200 is not None and 0 < sma_200 < entry else atr_stop
    contraction_low_20 = _as_float(row.get("contraction_low_20"))
    if contraction_low_20 is not None:
        structure_stop = contraction_low_20 - (
            PARAMETERS["structure_stop_buffer_atr"].default * atr
        )
        if structure_stop <= 0 or structure_stop >= entry:
            structure_stop = atr_stop
    else:
        structure_stop = atr_stop
    stop_loss = structure_stop if _active_stop_mode() == "structure" else trend_stop
    take_profit = entry + PARAMETERS["take_profit_r_multiple"].default * (
        entry - stop_loss
    )
    return {
        "entry": entry,
        "stop_loss": stop_loss,
        "tighter_stop_loss": structure_stop,
        "take_profit": take_profit,
    }


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

    gp_applied = "gp_to_assets" in df.columns and df["gp_to_assets"].notna().any()
    if gp_applied:
        df["_gp_pass"] = gross_profitability_mask(
            df["gp_to_assets"], PARAMETERS["min_gp_assets_percentile"].default
        )
    else:
        df["_gp_pass"] = True

    ag_top = PARAMETERS["max_asset_growth_percentile"].default
    ag_applied = (
        ag_top < 1.0
        and "asset_growth" in df.columns
        and df["asset_growth"].notna().any()
    )
    if ag_applied:
        ag_threshold = df["asset_growth"].dropna().quantile(ag_top)
        df["_ag_pass"] = df["asset_growth"].isna() | (df["asset_growth"] <= ag_threshold)
    else:
        df["_ag_pass"] = True

    if "52w_high" in df.columns and "close" in df.columns:
        df["dist_to_high"] = (df["52w_high"] - df["close"]) / df["close"]

    strong_sectors = _strong_sectors_by_breadth(
        df, PARAMETERS["sector_strength_top_fraction"].default
    )

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

    # Cross-sectional gross-profitability gate is computed over the full universe
    # so "top half" means top half of the screened universe, not of the survivors.
    if "gp_to_assets" in df.columns and df["gp_to_assets"].notna().any():
        df["_gp_pass"] = gross_profitability_mask(
            df["gp_to_assets"], PARAMETERS["min_gp_assets_percentile"].default
        )
        gates_applied.append("top-half gross profitability")
    else:
        df["_gp_pass"] = True
        gates_skipped.append(
            "gross-profitability gate skipped: gp_to_assets unavailable for this universe"
        )

    # Cross-sectional LOW asset-growth gate (George-Hwang-Li q-theory): keep only
    # the bottom fraction of the universe by YoY asset growth. Fails OPEN per name
    # (missing asset_growth still passes) since point-in-time asset growth is sparse.
    ag_top = PARAMETERS["max_asset_growth_percentile"].default
    if (
        ag_top < 1.0
        and "asset_growth" in df.columns
        and df["asset_growth"].notna().any()
    ):
        ag_valid = df["asset_growth"].dropna()
        ag_threshold = ag_valid.quantile(ag_top)
        df["_ag_pass"] = df["asset_growth"].isna() | (
            df["asset_growth"] <= ag_threshold
        )
        gates_applied.append("low asset growth")
        n_missing_ag = int(df["asset_growth"].isna().sum())
        if n_missing_ag:
            gates_skipped.append(
                f"asset-growth gate passed-through for {n_missing_ag} name(s) missing"
                " point-in-time asset growth (fails open)"
            )
    else:
        df["_ag_pass"] = True
        gates_skipped.append(
            "asset-growth gate skipped: asset_growth unavailable for this universe"
            if ag_top < 1.0
            else "asset-growth gate disabled (max_asset_growth_percentile=1.0)"
        )

    # 1. 52-week high proximity
    df["dist_to_high"] = (df["52w_high"] - df["close"]) / df["close"]

    # Sector strength via BREADTH (industry momentum): keep names only in sectors
    # where a high fraction of members are in an uptrend (above their 200-day SMA).
    # Replaces the old median-distance-to-high metric, which was dominated by each
    # sector's far-from-high majority and excluded near-high names in broadly-weak
    # sectors. Skipped (fail-open) when sector coverage is too thin or disabled.
    strong_sectors = _strong_sectors_by_breadth(
        df, PARAMETERS["sector_strength_top_fraction"].default
    )
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

    # 7. Entry / Stop Loss / Take Profit derivation. BOTH stops are always
    # computed so the UI can show them side by side; the active mode selects which
    # one is "primary" (drives the take-profit). Default primary = trend stop.
    matched["entry"] = matched["close"]
    # 3-ATR disaster stop is the universal fallback when a method's preferred
    # level is unavailable or sits at/above entry.
    atr_stop = matched["entry"] - (3 * matched["atr"])

    # (a) Trend stop: per-stock 200-day SMA when below entry (Faber), else 3-ATR.
    if "sma_200" in matched.columns:
        sma_valid = (
            matched["sma_200"].notna()
            & (matched["sma_200"] > 0)
            & (matched["sma_200"] < matched["entry"])
        )
        trend_stop = matched["sma_200"].where(sma_valid, atr_stop)
    else:
        trend_stop = atr_stop

    # (b) Structure stop: just below the 20-day consolidation low (− ATR buffer).
    # Usually tighter than the 200-SMA for a name near its high (better reward:risk).
    if "contraction_low_20" in matched.columns:
        buffer = PARAMETERS["structure_stop_buffer_atr"].default * matched["atr"]
        structure_stop = matched["contraction_low_20"] - buffer
        struct_valid = (
            matched["contraction_low_20"].notna()
            & (structure_stop > 0)
            & (structure_stop < matched["entry"])
        )
        structure_stop = structure_stop.where(struct_valid, atr_stop)
    else:
        structure_stop = atr_stop

    if _active_stop_mode() == "structure":
        matched["stop_loss"] = structure_stop
        stop_label = "hard stop below 20-day consolidation low"
    else:
        matched["stop_loss"] = trend_stop
        stop_label = "trailing 200-day SMA stop"
    # Always expose the structure (swing-low) stop as the tighter alternative.
    matched["tighter_stop_loss"] = structure_stop

    # Take-profit target as an R-multiple of the (entry - stop) risk.
    matched["take_profit"] = matched["entry"] + PARAMETERS[
        "take_profit_r_multiple"
    ].default * (matched["entry"] - matched["stop_loss"])
    # Per-candidate gate-by-gate breakdown (pass / warn / skipped, with values).
    gate_context = evaluation_context(
        matched,
        strong_sectors=strong_sectors,
        vol_col=vol_col,
        gp_applied="top-half gross profitability" in gates_applied,
        ag_applied="low asset growth" in gates_applied,
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
)

registry.register(strategy)
