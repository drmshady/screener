from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..agent.advisor_prompt import (
    build_midterm_matrix_advisor_prompt,
    build_screen_advisor_prompt,
    load_survivorship_status,
)
from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from ..lib.flags import personal_use_directive
from ..models.strategy import (
    MidtermComparePromptResponse,
    MidtermComparisonResponse,
    ScreenAdvisorPromptResponse,
    ScreenResult,
    ScreenRunRequest,
    Strategy,
)
from ..screening.engine import run_strategy
from ..screening.midterm_matrix import run_midterm_matrix
from ..strategies._registry import registry
from .. import strategies as _strategies  # noqa: F401 - registers strategy modules

router = APIRouter(prefix="/strategies", tags=["strategies"])


class StrategiesResponse(BaseModel):
    strategies: list[Strategy]
    data_as_of: str
    disclaimer: str


@router.get("", response_model=StrategiesResponse)
def list_strategies(timeframe: str | None = None, enabled_only: bool = False):
    strategies = registry.list_all()
    if timeframe:
        strategies = [
            strategy for strategy in strategies if strategy.timeframe == timeframe
        ]
    if enabled_only:
        strategies = [
            strategy for strategy in strategies if strategy.enabled_by_default
        ]
    return StrategiesResponse(
        strategies=strategies,
        data_as_of=utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )


# NOTE: the mid-term compare routes are declared BEFORE the dynamic `/{slug}`
# routes so `/strategies/midterm-compare/...` is not captured as `slug="midterm-
# compare"` by `/{slug}/advisor-prompt`.


@router.post("/midterm-compare", response_model=MidtermComparisonResponse)
def midterm_compare(request: ScreenRunRequest):
    """Run the fixed four-variant mid-term matrix over ONE shared snapshot and
    return all four variant screens + the shared regime/data_as_of (feature 006).
    The two A/B params are owned by the matrix; caller values for them are
    ignored (contracts/compare-api.md)."""
    run = run_midterm_matrix(
        as_of_date=request.as_of_date,
        filters=request.filters,
        shariah_overrides=request.shariah_overrides,
        parameters=request.parameters,
    )
    return MidtermComparisonResponse(
        variants=run.variants,
        regime=run.regime,
        data_as_of=run.data_as_of,
        disclaimer=DISCLAIMER_TEXT,
    )


@router.post(
    "/midterm-compare/advisor-prompt", response_model=MidtermComparePromptResponse
)
def midterm_compare_advisor_prompt(request: ScreenRunRequest):
    """Run the matrix and return ONE combined four-variant advisor prompt
    (declaration + gates + levels + shared regime + per-strategy bias-check).
    Directive framing is gated on the personal-use flag (FR-014)."""
    run = run_midterm_matrix(
        as_of_date=request.as_of_date,
        filters=request.filters,
        shariah_overrides=request.shariah_overrides,
        parameters=request.parameters,
    )
    directive = personal_use_directive()
    prompt = build_midterm_matrix_advisor_prompt(
        run.variants, regime=run.regime, directive=directive
    )
    return MidtermComparePromptResponse(
        prompt=prompt,
        variant_count=len(run.variants),
        personal_use_directive=directive,
        data_as_of=run.data_as_of,
        disclaimer=DISCLAIMER_TEXT,
    )


@router.get("/{slug}", response_model=Strategy)
def get_strategy(slug: str):
    strat = registry.get(slug)
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strat


@router.post("/{slug}/run", response_model=ScreenResult)
def run_strategy_endpoint(slug: str, request: ScreenRunRequest):
    # Market handling (Saudi `.SR` universe + SAR thresholds) is centralized in
    # run_strategy via parameters.market, so callers just pass it through.
    try:
        return run_strategy(
            slug,
            parameters=request.parameters,
            filters=request.filters,
            shariah_overrides=request.shariah_overrides,
            as_of_date=request.as_of_date,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Strategy not found") from None
    except ValueError as exc:
        # e.g. explicit `tickers` that resolve to no OHLCV data — fail gracefully
        # like the analyze/candidate paths rather than crashing with a 500.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{slug}/advisor-prompt", response_model=ScreenAdvisorPromptResponse)
def screen_advisor_prompt(slug: str, request: ScreenRunRequest):
    """Run the screen and return ONE combined advisor prompt covering every
    candidate. Reuses run_strategy so the prompt's numbers match the screen, and
    build_screen_advisor_prompt so the strategy context + honesty block are the
    same single source of truth as the per-candidate prompt."""
    strat = registry.get(slug)
    if strat is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    try:
        screen = run_strategy(
            slug,
            parameters=request.parameters,
            filters=request.filters,
            shariah_overrides=request.shariah_overrides,
            as_of_date=request.as_of_date,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Strategy not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    directive = personal_use_directive()
    prompt = build_screen_advisor_prompt(
        screen,
        strat,
        survivorship=load_survivorship_status(slug=slug),
        directive=directive,
    )
    return ScreenAdvisorPromptResponse(
        strategy=slug,
        candidate_count=screen.candidate_count,
        personal_use_directive=directive,
        prompt=prompt,
        data_as_of=screen.data_as_of,
        disclaimer=DISCLAIMER_TEXT,
    )
