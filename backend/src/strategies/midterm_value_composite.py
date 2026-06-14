"""Mid-Term Value Composite strategy.

Selection thesis is *cheapness*: rank the liquid universe by a multi-metric value
composite (book/market, earnings, cash-flow, sales yields), keep only financially
*improving* firms via a Piotroski (2000) F-Score gate (the canonical value-trap
filter), apply a loose leverage sanity ceiling, and rank the composite WITHIN
sector so structurally cheap/expensive sectors (financials, REITs) compete with
their own peers. Holding band and level/stop machinery match the mid-term
momentum strategy, so the comparison (003) and advisor-export (004) surfaces apply
unchanged.

Citations: Fama & French (1992); Lakonishok, Shleifer & Vishny (1994) (value/
contrarian premium); Piotroski (2000) (financial-health F-Score).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from ..models.strategy import BacktestSummary, Modification, Strategy, StrategyParameter
from ._helpers.reference_thresholds import load_reference_thresholds
from ._helpers.sector_rank import rank_within_sector
from ._helpers.value_composite import compute_value_composite
from ._registry import registry

# Operator override (mirrors midterm_52w_high_momentum): the backtest's
# survivorship check still FAILS on the free Stooq bundle (no delisted tickers),
# so strict constitutional gating would keep this disabled. The single operator of
# this personal-use tool has chosen to treat it as enabled-by-default with eyes
# open; this does NOT alter the backtest artifact or its honest bias_check (which
# continue to report survivorship as FAILED and stay visible in the UI) — it only
# flips the enable flag. Set SCREENER_VALUE_TREAT_AS_VALID=0 to restore strict
# gating (disabled until survivorship passes on a delisted-inclusive archive).
OPERATOR_TREAT_AS_VALID = os.getenv("SCREENER_VALUE_TREAT_AS_VALID", "1") != "0"

NAME = "Mid-Term Value Composite"
CITATION = "Fama & French (1992); Lakonishok, Shleifer & Vishny (1994)"
TIMEFRAME = "Mid-term"
DESCRIPTION = (
    "Ranks liquid stocks by a multi-metric value composite (book/market, earnings,"
    " cash-flow, sales yields), gated by the Piotroski F-Score and ranked within"
    " sector."
)

HOLDING_PERIOD = {"min": 60, "max": 180}

PARAMETERS = {
    "min_f_score": StrategyParameter(
        default=6,
        min=0,
        max=9,
        type="int",
        description="Piotroski F-Score floor (value-trap gate); 6 is the lower bound of Piotroski's high-score band.",
    ),
    "composite_top_percentile": StrategyParameter(
        default=0.5,
        min=0.05,
        max=1.0,
        type="float",
        description="Keep names in the cheapest top fraction of the value composite (1.0 disables the hard cut; ranking still orders by composite).",
    ),
    "within_sector_ranking": StrategyParameter(
        default=True,
        type="bool",
        description="Rank the value composite within sector so financials/REITs compete with peers (FR-014 distorted-sector handling).",
    ),
    "min_momentum_12_1": StrategyParameter(
        default=-1.0,
        min=-1.0,
        max=1.0,
        type="float",
        description=(
            "Optional falling-knife guard: exclude names whose 12-1 month price"
            " momentum is below this floor (e.g. -0.20 drops names down >20%)."
            " Default -1.0 disables it (pure value — Piotroski sees financial health,"
            " not price trend). Override with SCREENER_VALUE_MIN_MOMENTUM. Names with"
            " unknown momentum pass through (fail-open)."
        ),
    ),
    "max_per_sector": StrategyParameter(
        default=5, type="int", description="Max candidates per sector"
    ),
    "max_debt_equity": StrategyParameter(
        default=2.0,
        min=0.0,
        max=5.0,
        type="float",
        description="Leverage sanity ceiling (looser than momentum; value names can carry more debt). Missing D/E passes through.",
    ),
    "take_profit_r_multiple": StrategyParameter(
        default=4.0,
        min=1.0,
        max=10.0,
        type="float",
        description="Take-profit target as a multiple of risk; more patient than momentum (mean-reversion thesis).",
    ),
    "trend_sma_length": StrategyParameter(
        default=200,
        min=50,
        max=300,
        type="int",
        description="SMA length used only for the trailing-stop level (NOT an entry gate — value enters weakness).",
    ),
    "structure_stop_buffer_atr": StrategyParameter(
        default=0.25,
        min=0.0,
        max=2.0,
        type="float",
        description="ATR buffer below the 20-day swing low for the tighter structure stop.",
    ),
}

# Value/contrarian premium does part of its work entering weakness, so downtrends
# are Neutral (NOT Unfavorable) — marking them Unfavorable would make the Faber
# regime master-switch suppress exactly the contrarian entries the thesis targets.
REGIME_FAVORABILITY = {
    "Trending up": "Neutral",
    "Range-bound": "Favorable",
    "Trending down": "Neutral",
}

MODIFICATIONS = [
    Modification(
        name="Value composite",
        description="Equal-weight blend of cross-sectional percentile ranks on book/market, earnings, cash-flow and sales yields.",
        citation="Fama & French (1992), The Cross-Section of Expected Stock Returns; Lakonishok, Shleifer & Vishny (1994), Contrarian Investment, Extrapolation, and Risk",
    ),
    Modification(
        name="Piotroski F-Score health gate",
        description="Keeps only financially improving cheap firms (F-Score >= floor), filtering likely value traps.",
        citation="Piotroski (2000), Value Investing: The Use of Historical Financial Statement Information",
    ),
    Modification(
        name="Within-sector ranking",
        description="Ranks the value composite among sector peers so financials/REITs are not spuriously ranked cheap or expensive.",
        citation="Asness, Frazzini & Pedersen (2013), Value and Momentum Everywhere",
    ),
    Modification(
        name="Sector concentration cap",
        description="Caps the result list at a maximum number of names per sector.",
        citation="Documented risk-control overlay for sector concentration",
    ),
]


def _backtest_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "backtests"
        / "midterm_value_composite.json"
    )


def _load_backtest_summary() -> BacktestSummary | None:
    path = _backtest_path()
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
    path = _backtest_path()
    if not path.exists():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    bias_check = payload.get("bias_check", {})
    return bool(bias_check) and all(
        item.get("passed") is True for item in bias_check.values()
    )


def _gate_mode() -> str:
    """hard (default) filters every gate; tiered warns + ranks. Shared switch with
    the momentum strategy (SCREENER_GATE_MODE)."""
    mode = os.getenv("SCREENER_GATE_MODE", "hard").strip().lower()
    return mode if mode in {"tiered", "hard"} else "hard"


def _active_min_momentum(override=None) -> float:
    """Resolve the optional 12-1 momentum floor. Precedence: a per-run override
    (UI toggle, threaded via the universe frame's attrs) wins, then the
    SCREENER_VALUE_MIN_MOMENTUM env, then the declared default. Values <= -1.0
    mean the guard is disabled (pure value)."""
    if override is not None:
        try:
            return float(override)
        except (TypeError, ValueError):
            pass
    raw = os.getenv("SCREENER_VALUE_MIN_MOMENTUM")
    if raw is not None:
        try:
            return float(raw)
        except ValueError:
            pass
    return float(PARAMETERS["min_momentum_12_1"].default)


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


def _composite_threshold(df: pd.DataFrame) -> float | None:
    """Cheapness cut: prefer the cached reference-universe value-composite cut
    (stable across screen/analyze/detail); else this universe's own quantile."""
    top = float(PARAMETERS["composite_top_percentile"].default)
    if not (0.0 < top < 1.0):
        return None
    ref = load_reference_thresholds()
    if ref and ref.get("value_composite_threshold") is not None:
        return float(ref["value_composite_threshold"])
    valid = pd.to_numeric(df.get("value_composite"), errors="coerce").dropna()
    if valid.empty:
        return None
    return float(valid.quantile(1.0 - top))


def evaluation_context(
    universe_df: pd.DataFrame,
    *,
    composite_threshold: float | None = None,
    single_ticker: bool = False,
    min_momentum_override=None,
) -> dict:
    return {
        "min_f_score": int(PARAMETERS["min_f_score"].default),
        "max_debt_equity": float(PARAMETERS["max_debt_equity"].default),
        "composite_threshold": composite_threshold,
        "min_momentum_12_1": _active_min_momentum(min_momentum_override),
        "single_ticker": single_ticker,
    }


def evaluate(row, context: dict | None = None) -> list[dict]:
    """Per-name gate-by-gate breakdown (no filtering)."""
    if context is None:
        prepared = prepare_universe_gates(pd.DataFrame([dict(row)]))
        df = prepared[0]
        row = df.iloc[0]
        context = evaluation_context(
            df, composite_threshold=prepared[1], single_ticker=True
        )
    out: list[dict] = []

    # Value composite
    composite = _as_float(row.get("value_composite"))
    count = int(row.get("value_metrics_count", 0) or 0)
    threshold = context.get("composite_threshold")
    if composite is None or count == 0:
        out.append(
            {
                "gate": "Value composite",
                "status": "skipped",
                "detail": "no value yields available to compute cheapness",
            }
        )
    elif threshold is None:
        out.append(
            {
                "gate": "Value composite",
                "status": "pass",
                "detail": f"composite {composite:.2f} (from {count}/4 yields); cheapness cut disabled",
            }
        )
    else:
        passed = composite >= threshold
        out.append(
            {
                "gate": "Value composite",
                "status": _status(passed),
                "detail": (
                    f"composite {composite:.2f} (from {count}/4 yields) "
                    f"{'>=' if passed else '<'} cut {threshold:.2f}"
                ),
            }
        )

    # Piotroski F-Score
    f_score = row.get("f_score")
    f_eval = int(row.get("f_score_evaluable", 0) or 0)
    min_f = int(context.get("min_f_score", 6))
    if f_score is None or f_eval == 0:
        out.append(
            {
                "gate": "Piotroski F-Score",
                "status": "skipped",
                "detail": "no point-in-time financial-statement inputs to score health",
            }
        )
    else:
        passed = int(f_score) >= min_f
        partial = "" if f_eval == 9 else f" ({f_eval}/9 signals evaluable)"
        out.append(
            {
                "gate": "Piotroski F-Score",
                "status": _status(passed),
                "detail": f"F-Score {int(f_score)}/9{partial} {'>=' if passed else '<'} floor {min_f}",
            }
        )

    # Leverage sanity
    de = _as_float(row.get("debt_to_equity"))
    max_de = float(context.get("max_debt_equity", 2.0))
    if de is None:
        out.append(
            {
                "gate": "Leverage sanity",
                "status": "skipped",
                "detail": "debt/equity unavailable (passed through)",
            }
        )
    else:
        passed = de <= max_de
        out.append(
            {
                "gate": "Leverage sanity",
                "status": _status(passed),
                "detail": f"debt/equity {de:.2f} {'<=' if passed else '>'} {max_de:g}",
            }
        )

    # Optional momentum floor (only reported when enabled)
    mom_floor = float(context.get("min_momentum_12_1", -1.0))
    if mom_floor > -1.0:
        mom = _as_float(row.get("return_12_1"))
        if mom is None:
            out.append(
                {
                    "gate": "Momentum floor",
                    "status": "skipped",
                    "detail": "12-1 momentum unavailable (passed through)",
                }
            )
        else:
            passed = mom >= mom_floor
            out.append(
                {
                    "gate": "Momentum floor",
                    "status": _status(passed),
                    "detail": f"12-1 momentum {mom * 100:.0f}% {'>=' if passed else '<'} floor {mom_floor * 100:.0f}% (falling-knife guard)",
                }
            )

    # Sector concentration (informational for a single ticker)
    if context.get("single_ticker"):
        out.append(
            {
                "gate": "Sector concentration",
                "status": "skipped",
                "detail": "needs the screened universe to rank within sector",
            }
        )
    else:
        out.append(
            {
                "gate": "Sector concentration",
                "status": "pass",
                "detail": f"within the top {PARAMETERS['max_per_sector'].default} of its sector by value composite",
            }
        )

    if _gate_mode() == "tiered":
        for gate in out:
            if gate["gate"] != "Value composite" and gate["status"] == "fail":
                gate["status"] = "warn"
    return out


def prepare_universe_gates(df: pd.DataFrame) -> tuple[pd.DataFrame, float | None]:
    """Compute the cross-sectional value composite + the cheapness threshold over a
    universe frame. Shared by the screen (`rules`) and single-ticker analysis so the
    percentile composite is evaluated against the SAME universe distribution rather
    than skipped for one symbol."""
    df = compute_value_composite(
        df, within_sector=bool(PARAMETERS["within_sector_ranking"].default)
    )
    return df, _composite_threshold(df)


def derive_levels(row) -> dict[str, float | None]:
    close = _as_float(row.get("close"))
    atr = _as_float(row.get("atr"))
    if close is None or atr is None:
        return {"entry": close, "stop_loss": None, "tighter_stop_loss": None, "take_profit": None}
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
    stop_loss = trend_stop
    take_profit = entry + PARAMETERS["take_profit_r_multiple"].default * (entry - stop_loss)
    return {
        "entry": entry,
        "stop_loss": stop_loss,
        "tighter_stop_loss": structure_stop,
        "take_profit": take_profit,
    }


def rules(universe_df: pd.DataFrame) -> pd.DataFrame:
    """Evaluate the value strategy over a universe snapshot.

    Required columns: ticker, sector, close, atr, debt_to_equity and the value
    yields (book_to_market, earnings_yield, cashflow_yield, sales_yield) +
    f_score / f_score_evaluable. Optional sma_200 / contraction_low_20 enable the
    stop levels. Deterministic on a fixed frame.
    """
    if universe_df.empty:
        return pd.DataFrame()

    # Per-run momentum-floor override (UI toggle) is carried on the frame's attrs;
    # capture it before pandas operations drop attrs further down.
    mom_override = universe_df.attrs.get("min_momentum_12_1")

    gates_applied: list[str] = []
    gates_skipped: list[str] = []

    def _with_notes(frame: pd.DataFrame) -> pd.DataFrame:
        frame.attrs["gates_applied"] = list(gates_applied)
        frame.attrs["gates_skipped"] = list(gates_skipped)
        return frame

    df, composite_threshold = prepare_universe_gates(universe_df)
    hard_mode = _gate_mode() == "hard"
    min_f = int(PARAMETERS["min_f_score"].default)
    max_de = float(PARAMETERS["max_debt_equity"].default)

    matched = df.copy()

    # HARD gate (always filters): the value composite IS the strategy. Names with
    # no evaluable yields cannot be ranked for cheapness and are dropped.
    gates_applied.append("value composite (cheapness ranking)")
    has_composite = pd.to_numeric(matched["value_composite"], errors="coerce").notna()
    no_composite = int((~has_composite).sum())
    if no_composite:
        gates_skipped.append(
            f"value composite unavailable for {no_composite} name(s) lacking any"
            " value yield (excluded — cannot rank cheapness)"
        )
    matched = matched[has_composite]
    if matched.empty:
        return _with_notes(matched)

    # Cheapness cut (soft in tiered mode).
    if composite_threshold is not None:
        gates_applied.append("cheapest top fraction")
        if hard_mode:
            matched = matched[matched["value_composite"] >= composite_threshold]
            if matched.empty:
                return _with_notes(matched)
    else:
        gates_skipped.append("cheapness cut disabled (composite_top_percentile=1.0)")

    # Piotroski F-Score gate. Missing health inputs -> cannot confirm not-a-trap;
    # excluded in hard mode and recorded as skipped.
    gates_applied.append("Piotroski F-Score health")
    f_eval = pd.to_numeric(matched.get("f_score_evaluable"), errors="coerce").fillna(0)
    f_val = pd.to_numeric(matched.get("f_score"), errors="coerce")
    n_unscored = int((f_eval == 0).sum())
    if n_unscored:
        gates_skipped.append(
            f"Piotroski F-Score unavailable for {n_unscored} name(s) with no"
            " point-in-time financials (excluded in hard mode)"
        )
    if hard_mode:
        matched = matched[(f_eval > 0) & (f_val >= min_f)]
        if matched.empty:
            return _with_notes(matched)

    # Leverage sanity (soft). Missing D/E passes through.
    gates_applied.append("leverage sanity")
    de = pd.to_numeric(matched.get("debt_to_equity"), errors="coerce")
    n_missing_de = int(de.isna().sum())
    if n_missing_de:
        gates_skipped.append(
            f"leverage sanity passed-through for {n_missing_de} name(s) missing debt/equity"
        )
    if hard_mode:
        matched = matched[de.isna() | (de <= max_de)]
        if matched.empty:
            return _with_notes(matched)

    # Optional falling-knife guard (soft): exclude names in steep price downtrends
    # so the strategy doesn't buy cheapness that is cheap *because* it's collapsing.
    # Disabled by default (pure value); fail-open on unknown momentum.
    mom_floor = _active_min_momentum(mom_override)
    if mom_floor > -1.0 and "return_12_1" in matched.columns:
        gates_applied.append(f"12-1 momentum >= {mom_floor:.0%} (not a falling knife)")
        mom = pd.to_numeric(matched["return_12_1"], errors="coerce")
        n_missing_mom = int(mom.isna().sum())
        if n_missing_mom:
            gates_skipped.append(
                f"momentum floor passed-through for {n_missing_mom} name(s) with unknown 12-1 momentum"
            )
        if hard_mode:
            matched = matched[mom.isna() | (mom >= mom_floor)]
            if matched.empty:
                return _with_notes(matched)
    elif mom_floor <= -1.0:
        gates_skipped.append("momentum floor disabled (pure value; min_momentum_12_1=-1.0)")

    # Score = value composite (higher = cheaper = better). The engine sorts by it.
    matched["score"] = pd.to_numeric(matched["value_composite"], errors="coerce")

    # Within-sector concentration cap.
    matched = rank_within_sector(
        matched, score_column="score", max_per_sector=PARAMETERS["max_per_sector"].default
    )

    # Levels.
    matched["entry"] = matched["close"]
    atr_stop = matched["entry"] - (3 * matched["atr"])
    if "sma_200" in matched.columns:
        sma_valid = (
            matched["sma_200"].notna()
            & (matched["sma_200"] > 0)
            & (matched["sma_200"] < matched["entry"])
        )
        trend_stop = matched["sma_200"].where(sma_valid, atr_stop)
    else:
        trend_stop = atr_stop
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
    matched["stop_loss"] = trend_stop
    matched["tighter_stop_loss"] = structure_stop
    matched["take_profit"] = matched["entry"] + PARAMETERS[
        "take_profit_r_multiple"
    ].default * (matched["entry"] - matched["stop_loss"])

    # Per-candidate gate breakdown + warnings.
    context = evaluation_context(
        matched, composite_threshold=composite_threshold, min_momentum_override=mom_override
    )
    matched["gate_results"] = [evaluate(r, context) for _, r in matched.iterrows()]
    matched["warnings"] = matched["gate_results"].apply(
        lambda gr: [g["gate"] for g in gr if g["status"] == "warn"]
    )
    matched["warning_count"] = matched["warnings"].apply(len)

    if hard_mode:
        matched["reason"] = f"{', '.join(gates_applied).capitalize()}; trailing 200-day SMA stop"
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
            parts.append("trailing 200-day SMA stop")
            return "; ".join(parts)

        matched["reason"] = matched.apply(_row_reason, axis=1)

    if not hard_mode and len(matched) > 1:
        matched = matched.sort_values(
            ["warning_count", "score"], ascending=[True, False]
        ).reset_index(drop=True)

    return _with_notes(matched)


strategy = Strategy(
    slug="midterm_value_composite",
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
