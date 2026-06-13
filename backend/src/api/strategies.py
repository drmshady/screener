from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..agent.advisor_prompt import build_screen_advisor_prompt, load_survivorship_status
from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from ..lib.flags import personal_use_directive
from ..models.strategy import (
    ScreenAdvisorPromptResponse,
    ScreenResult,
    ScreenRunRequest,
    Strategy,
)
from ..screening.engine import run_strategy
from ..strategies._registry import registry
from .. import (
    strategies as _strategies,
)  # noqa: F401 - imports register strategy modules

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

    directive = personal_use_directive()
    prompt = build_screen_advisor_prompt(
        screen,
        strat,
        survivorship=load_survivorship_status(),
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
