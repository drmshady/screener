from __future__ import annotations

from datetime import date

import pandas as pd
from fastapi import APIRouter, HTTPException

from .. import strategies as _strategies  # noqa: F401 - registers strategies
from ..agent.advisor_prompt import build_advisor_prompt, load_survivorship_status
from ..data.fundamentals import FundamentalsLoader
from ..data.saudi_universe import saudi_universe
from ..lib.disclaimer import DISCLAIMER_TEXT
from ..lib import flags
from ..lib.flags import personal_use_directive
from ..models.strategy import AdvisorPromptResponse, AnalyzeResponse
from ..regime.calculator import current_regime_response
from ..screening.entry_timing import EntryThresholds, classify_entry_timing
from ..screening.engine import (
    _compliant_universe,
    build_single_ticker_snapshot,
    build_universe_snapshot,
    build_universe_snapshot_stooq,
)
from ..shariah.lookup import normalize_shariah_overrides
from ..strategies import midterm_52w_high_momentum as midterm
from ..strategies import midterm_value_composite as value
from ..strategies._registry import registry

router = APIRouter(prefix="/analyze", tags=["analyze"])


def _as_float(value) -> float | None:
    """Coerce a snapshot cell to a plain float, or None when missing/NaN."""
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _material_input_freshness(data_as_of: str, as_of: str | None = None) -> dict[str, str]:
    snapshot_date = data_as_of[:10]
    regime_as_of = as_of or snapshot_date
    return {
        "prices": snapshot_date,
        "fundamentals": snapshot_date,
        "regime": regime_as_of[:10],
    }


_DEFAULT_SHARIAH_SOURCES = [
    "spus_holdings", "spwo_holdings", "spre_holdings", "spte_holdings", "halal_terminal",
]


def _entry_thresholds() -> EntryThresholds:
    return EntryThresholds(
        pivot_max_extension=flags.entry_pivot_max_extension(),
        volume_ratio_min=flags.entry_volume_ratio_min(),
        volume_ratio_preferred=flags.entry_volume_ratio_preferred(),
        flat_min_weeks=flags.entry_flat_base_min_weeks(),
        cup_min_weeks=flags.entry_cup_base_min_weeks(),
        base_depth_max=flags.entry_base_depth_max(),
        sma200_extension_max=flags.entry_sma200_extension_max(),
        climax_advance_min=flags.entry_climax_advance_min(),
        climax_prior_trend_weeks=flags.entry_climax_prior_trend_weeks(),
        huge_gap_threshold=flags.entry_huge_gap_threshold(),
    )


def _market_universe(symbol: str, as_of: str | None) -> pd.DataFrame:
    """The universe whose distribution the percentile gates are scored against —
    the Saudi `.SR` universe for Saudi names, else the compliant US universe."""
    try:
        if symbol.endswith(".SR"):
            df, _ = build_universe_snapshot(saudi_universe(), as_of_date=as_of)
            return df
        overrides = normalize_shariah_overrides(
            {"active_sources": _DEFAULT_SHARIAH_SOURCES}
        )
        df, _ = build_universe_snapshot_stooq(_compliant_universe(overrides), as_of_date=as_of)
        return df
    except Exception:
        return pd.DataFrame()


def _overlay_edgar(snapshot: pd.DataFrame, symbol: str, as_of: str) -> None:
    """Fill point-in-time EDGAR fundamentals (esp. asset_growth, which the yfinance
    profile path doesn't compute) onto the single-ticker row so the quality and
    asset-growth gates have data."""
    loader = FundamentalsLoader()
    try:
        payload = loader.fetch_company_facts(symbol)
        q = loader.quality_metrics_as_of(symbol, date.fromisoformat(as_of[:10]), payload=payload)
    except Exception:
        return
    idx = snapshot.index[0]
    for key in ("asset_growth", "gp_to_assets", "fcf_ttm", "debt_to_equity"):
        cur = snapshot.at[idx, key] if key in snapshot.columns else None
        if (cur is None or pd.isna(cur)) and q.get(key) is not None:
            snapshot.at[idx, key] = q.get(key)
    # Feature 011 (US3): momentum's quality overlay above doesn't compute the
    # value yields the fair-value estimate is derived from; reuse the value
    # overlay so a trusted fair value is available for the reward ceiling (T018)
    # and sizing (T028) here too. Pass the already-fetched payload so this
    # doesn't double the EDGAR fetch/parse cost per request.
    _overlay_edgar_value(snapshot, symbol, as_of, payload=payload)


def _overlay_edgar_value(
    snapshot: pd.DataFrame, symbol: str, as_of: str, payload: dict | None = None
) -> None:
    """Fill point-in-time EDGAR value-composite + Piotroski inputs onto the
    single-ticker row (the yfinance profile path that builds single-ticker
    snapshots doesn't compute them). Only fills missing cells; never clobbers.

    Also recomputes the feature-011 fair-value estimate from the (possibly just
    -filled) yields, since the initial single-ticker snapshot build runs before
    this overlay and would otherwise carry a stale/unavailable estimate."""
    loader = FundamentalsLoader()
    try:
        if payload is None:
            payload = loader.fetch_company_facts(symbol)
        vm = loader.value_metrics_as_of(symbol, date.fromisoformat(as_of[:10]), payload=payload)
    except Exception:
        return
    from ..screening.engine import _fair_value_row_fields, _value_row_fields

    idx = snapshot.index[0]
    close = float(snapshot.at[idx, "close"])
    fields = _value_row_fields({"value_metrics": vm}, close)
    for key, val in fields.items():
        cur = snapshot.at[idx, key] if key in snapshot.columns else None
        if (cur is None or pd.isna(cur)) and val is not None:
            snapshot.at[idx, key] = val

    refreshed = {
        "book_to_market": snapshot.at[idx, "book_to_market"] if "book_to_market" in snapshot.columns else None,
        "earnings_yield": snapshot.at[idx, "earnings_yield"] if "earnings_yield" in snapshot.columns else None,
        "value_metrics_period_end": snapshot.at[idx, "value_metrics_period_end"]
        if "value_metrics_period_end" in snapshot.columns
        else None,
    }
    fair_fields = _fair_value_row_fields(
        refreshed, close, date.fromisoformat(as_of[:10])
    )
    for key, val in fair_fields.items():
        snapshot.at[idx, key] = val


def compute_candidate_result(
    ticker: str,
    strategy: str = "midterm_52w_high_momentum",
    as_of: str | None = None,
    market_universe: pd.DataFrame | None = None,
) -> AnalyzeResponse:
    """Compute the single-ticker strategy result (gate results + levels).

    Shared by GET /analyze/{ticker} and GET /analyze/{ticker}/advisor-prompt so
    both surfaces use one computation path and report identical numbers. Raises
    HTTPException (404/400) on the same conditions as the analyze endpoint.

    ``market_universe`` lets a batch caller (the pipeline board) build the
    percentile-gate universe snapshot **once** and reuse it across every ticker
    instead of rebuilding it per call. When None (the default) the universe is
    built here exactly as before, so the single-call behavior is byte-identical.
    """
    registered = registry.get(strategy)
    if registered is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if strategy not in ("midterm_52w_high_momentum", "midterm_value_composite"):
        raise HTTPException(
            status_code=400,
            detail="Single-ticker analysis is currently available for the mid-term strategies",
        )

    symbol = ticker.strip().upper()
    try:
        snapshot, data_as_of, data_notes = build_single_ticker_snapshot(symbol, as_of=as_of)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if strategy == "midterm_value_composite":
        return _compute_value_candidate_result(
            symbol, snapshot, data_as_of, data_notes, as_of
        )

    _overlay_edgar(snapshot, symbol, data_as_of)
    row = snapshot.iloc[0]
    levels = midterm.derive_levels(row)
    if (
        levels["entry"] is None
        or levels["stop_loss"] is None
        or levels["take_profit"] is None
    ):
        raise HTTPException(
            status_code=404, detail=f"Not enough indicator data to analyze {symbol}"
        )

    # Evaluate the percentile/rank gates against the real universe distribution
    # (so sector-strength / gross-profitability / asset-growth actually run for a
    # single symbol instead of being skipped). Fall back to single-symbol context
    # if the universe snapshot is unavailable.
    universe = market_universe if market_universe is not None else _market_universe(symbol, as_of)
    if not universe.empty:
        others = universe[universe["ticker"].astype(str).str.upper() != symbol]
        combined = pd.concat([others, snapshot], ignore_index=True)
        combined, strong_sectors, gp_applied, ag_applied = midterm.prepare_universe_gates(combined)
        eval_row = combined[combined["ticker"].astype(str).str.upper() == symbol].iloc[0]
        vol_col = (
            "volume_ratio_recent"
            if "volume_ratio_recent" in combined.columns
            else ("volume_ratio_50" if "volume_ratio_50" in combined.columns else None)
        )
        context = midterm.evaluation_context(
            combined,
            strong_sectors=strong_sectors,
            vol_col=vol_col,
            gp_applied=gp_applied,
            ag_applied=ag_applied,
            single_ticker=False,
        )
        gate_results = midterm.evaluate(eval_row, context)
        data_notes.append(
            f"sector-strength, gross-profitability, and asset-growth gates evaluated against "
            f"the {len(combined)}-name {'Saudi' if symbol.endswith('.SR') else 'compliant US'} universe"
        )
    else:
        context = midterm.evaluation_context(snapshot, single_ticker=True)
        gate_results = midterm.evaluate(row, context)
        data_notes.append(
            "sector-strength, gross-profitability, and asset-growth percentile gates need a "
            "full universe context and are skipped (universe snapshot unavailable)"
        )

    would_be_selected = not any(gate["status"] == "fail" for gate in gate_results)
    entry_timing = classify_entry_timing(row.to_dict(), thresholds=_entry_thresholds())

    return AnalyzeResponse(
        ticker=symbol,
        name=str(row.get("name", symbol)),
        sector=str(row.get("sector", "Unclassified")),
        strategy=strategy,
        as_of=data_as_of[:10],
        would_be_selected=would_be_selected,
        current_price=f"{float(row['close']):.2f}",
        entry=f"{float(levels['entry']):.2f}",
        stop_loss=f"{max(float(levels['stop_loss']), 0.01):.2f}",
        tighter_stop_loss=(
            f"{max(float(levels['tighter_stop_loss']), 0.01):.2f}"
            if levels["tighter_stop_loss"] is not None
            else None
        ),
        take_profit=f"{float(levels['take_profit']):.2f}",
        risk_distance=_as_float(levels.get("risk_distance")),
        reward_distance=_as_float(levels.get("reward_distance")),
        reward_ceiling_basis=levels.get("reward_ceiling_basis"),
        bounds_applied=list(levels.get("bounds_applied") or []),
        levels_state=levels.get("levels_state"),
        rationale=levels.get("rationale"),
        return_12_1=_as_float(row.get("return_12_1")),
        vol_scalar=_as_float(row.get("vol_scalar")),
        dist_to_high=_as_float(row.get("dist_to_high")),
        atr=_as_float(row.get("atr")),
        debt_to_equity=_as_float(row.get("debt_to_equity")),
        fcf_ttm=_as_float(row.get("fcf_ttm")),
        gp_to_assets=_as_float(row.get("gp_to_assets")),
        asset_growth=_as_float(row.get("asset_growth")),
        fair_value=_as_float(row.get("fair_value")),
        fair_value_basis=row.get("fair_value_basis"),
        fair_value_trust_flag=row.get("fair_value_trust_flag"),
        fair_value_margin_of_safety=_as_float(row.get("fair_value_margin_of_safety")),
        gate_results=gate_results,
        entry_timing=entry_timing,
        data_notes=data_notes,
        material_input_freshness=_material_input_freshness(data_as_of, as_of),
        data_as_of=data_as_of,
        disclaimer=DISCLAIMER_TEXT,
    )


def _compute_value_candidate_result(
    symbol: str,
    snapshot: pd.DataFrame,
    data_as_of: str,
    data_notes: list[str],
    as_of: str | None,
) -> AnalyzeResponse:
    """Single-ticker path for midterm_value_composite. The value composite and
    F-Score gates are evaluated against the live universe distribution so they are
    not silently skipped for one symbol (FR-009)."""
    _overlay_edgar_value(snapshot, symbol, data_as_of)
    row = snapshot.iloc[0]
    levels = value.derive_levels(row)
    if (
        levels["entry"] is None
        or levels["stop_loss"] is None
        or levels["take_profit"] is None
    ):
        raise HTTPException(
            status_code=404, detail=f"Not enough indicator data to analyze {symbol}"
        )

    universe = _market_universe(symbol, as_of)
    if not universe.empty:
        others = universe[universe["ticker"].astype(str).str.upper() != symbol]
        combined = pd.concat([others, snapshot], ignore_index=True)
        combined, threshold = value.prepare_universe_gates(combined)
        eval_row = combined[combined["ticker"].astype(str).str.upper() == symbol].iloc[0]
        context = value.evaluation_context(combined, composite_threshold=threshold)
        gate_results = value.evaluate(eval_row, context)
        data_notes.append(
            f"value-composite and Piotroski gates evaluated against the {len(combined)}-name"
            f" {'Saudi' if symbol.endswith('.SR') else 'compliant US'} universe"
        )
    else:
        prepared, threshold = value.prepare_universe_gates(snapshot)
        eval_row = prepared.iloc[0]
        context = value.evaluation_context(
            prepared, composite_threshold=threshold, single_ticker=True
        )
        gate_results = value.evaluate(eval_row, context)
        data_notes.append(
            "value-composite percentile gate needs a full universe context and is"
            " skipped (universe snapshot unavailable)"
        )

    would_be_selected = not any(gate["status"] == "fail" for gate in gate_results)
    f_score = eval_row.get("f_score")
    f_eval = eval_row.get("f_score_evaluable")
    return AnalyzeResponse(
        ticker=symbol,
        name=str(row.get("name", symbol)),
        sector=str(row.get("sector", "Unclassified")),
        strategy="midterm_value_composite",
        as_of=data_as_of[:10],
        would_be_selected=would_be_selected,
        current_price=f"{float(row['close']):.2f}",
        entry=f"{float(levels['entry']):.2f}",
        stop_loss=f"{max(float(levels['stop_loss']), 0.01):.2f}",
        tighter_stop_loss=(
            f"{max(float(levels['tighter_stop_loss']), 0.01):.2f}"
            if levels["tighter_stop_loss"] is not None
            else None
        ),
        take_profit=f"{float(levels['take_profit']):.2f}",
        risk_distance=_as_float(levels.get("risk_distance")),
        reward_distance=_as_float(levels.get("reward_distance")),
        reward_ceiling_basis=levels.get("reward_ceiling_basis"),
        bounds_applied=list(levels.get("bounds_applied") or []),
        levels_state=levels.get("levels_state"),
        rationale=levels.get("rationale"),
        atr=_as_float(row.get("atr")),
        debt_to_equity=_as_float(eval_row.get("debt_to_equity")),
        fcf_ttm=_as_float(eval_row.get("fcf_ttm")),
        value_composite=_as_float(eval_row.get("value_composite")),
        book_to_market=_as_float(eval_row.get("book_to_market")),
        earnings_yield=_as_float(eval_row.get("earnings_yield")),
        cashflow_yield=_as_float(eval_row.get("cashflow_yield")),
        sales_yield=_as_float(eval_row.get("sales_yield")),
        f_score=int(f_score) if f_score is not None and not pd.isna(f_score) else None,
        f_score_evaluable=int(f_eval) if f_eval is not None and not pd.isna(f_eval) else None,
        fair_value=_as_float(eval_row.get("fair_value")),
        fair_value_basis=eval_row.get("fair_value_basis"),
        fair_value_trust_flag=eval_row.get("fair_value_trust_flag"),
        fair_value_margin_of_safety=_as_float(eval_row.get("fair_value_margin_of_safety")),
        gate_results=gate_results,
        data_notes=data_notes,
        material_input_freshness=_material_input_freshness(data_as_of, as_of),
        data_as_of=data_as_of,
        disclaimer=DISCLAIMER_TEXT,
    )


@router.get("/{ticker}", response_model=AnalyzeResponse)
def analyze_ticker(
    ticker: str,
    strategy: str = "midterm_52w_high_momentum",
    as_of: str | None = None,
):
    return compute_candidate_result(ticker, strategy=strategy, as_of=as_of)


def _current_regime_name(as_of: str | None) -> str | None:
    """Best-effort current regime name for the prompt; None if unavailable.

    Kept best-effort (never fatal) so the prompt still generates when regime
    inputs are unavailable; the builder notes the absence.
    """
    try:
        return str(current_regime_response(as_of_date=as_of).regime)
    except Exception:
        return None


@router.get("/{ticker}/advisor-prompt", response_model=AdvisorPromptResponse)
def advisor_prompt(
    ticker: str,
    strategy: str = "midterm_52w_high_momentum",
    as_of: str | None = None,
):
    result = compute_candidate_result(ticker, strategy=strategy, as_of=as_of)
    registered = registry.get(strategy)
    directive = personal_use_directive()
    prompt = build_advisor_prompt(
        result,
        registered,
        survivorship=load_survivorship_status(slug=strategy),
        regime=_current_regime_name(as_of),
        directive=directive,
    )
    return AdvisorPromptResponse(
        ticker=result.ticker,
        strategy=strategy,
        personal_use_directive=directive,
        prompt=prompt,
        data_as_of=result.data_as_of,
        disclaimer=DISCLAIMER_TEXT,
    )
