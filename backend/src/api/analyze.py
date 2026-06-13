from __future__ import annotations

from datetime import date

import pandas as pd
from fastapi import APIRouter, HTTPException

from .. import strategies as _strategies  # noqa: F401 - registers strategies
from ..agent.advisor_prompt import build_advisor_prompt, load_survivorship_status
from ..data.fundamentals import FundamentalsLoader
from ..data.saudi_universe import saudi_universe
from ..lib.disclaimer import DISCLAIMER_TEXT
from ..lib.flags import personal_use_directive
from ..models.strategy import AdvisorPromptResponse, AnalyzeResponse
from ..regime.calculator import current_regime_response
from ..screening.engine import (
    _compliant_universe,
    build_single_ticker_snapshot,
    build_universe_snapshot,
    build_universe_snapshot_stooq,
)
from ..shariah.lookup import normalize_shariah_overrides
from ..strategies import midterm_52w_high_momentum as midterm
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

_DEFAULT_SHARIAH_SOURCES = [
    "spus_holdings", "spwo_holdings", "spre_holdings", "spte_holdings", "halal_terminal",
]


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
    try:
        q = FundamentalsLoader().quality_metrics_as_of(
            symbol, date.fromisoformat(as_of[:10])
        )
    except Exception:
        return
    idx = snapshot.index[0]
    for key in ("asset_growth", "gp_to_assets", "fcf_ttm", "debt_to_equity"):
        cur = snapshot.at[idx, key] if key in snapshot.columns else None
        if (cur is None or pd.isna(cur)) and q.get(key) is not None:
            snapshot.at[idx, key] = q.get(key)


def compute_candidate_result(
    ticker: str,
    strategy: str = "midterm_52w_high_momentum",
    as_of: str | None = None,
) -> AnalyzeResponse:
    """Compute the single-ticker strategy result (gate results + levels).

    Shared by GET /analyze/{ticker} and GET /analyze/{ticker}/advisor-prompt so
    both surfaces use one computation path and report identical numbers. Raises
    HTTPException (404/400) on the same conditions as the analyze endpoint.
    """
    registered = registry.get(strategy)
    if registered is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if strategy != "midterm_52w_high_momentum":
        raise HTTPException(
            status_code=400,
            detail="Single-ticker analysis is currently available for the midterm 52-week-high strategy",
        )

    symbol = ticker.strip().upper()
    try:
        snapshot, data_as_of, data_notes = build_single_ticker_snapshot(symbol, as_of=as_of)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

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
    universe = _market_universe(symbol, as_of)
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
        return_12_1=_as_float(row.get("return_12_1")),
        vol_scalar=_as_float(row.get("vol_scalar")),
        dist_to_high=_as_float(row.get("dist_to_high")),
        atr=_as_float(row.get("atr")),
        debt_to_equity=_as_float(row.get("debt_to_equity")),
        fcf_ttm=_as_float(row.get("fcf_ttm")),
        gp_to_assets=_as_float(row.get("gp_to_assets")),
        asset_growth=_as_float(row.get("asset_growth")),
        gate_results=gate_results,
        data_notes=data_notes,
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
        survivorship=load_survivorship_status(),
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
