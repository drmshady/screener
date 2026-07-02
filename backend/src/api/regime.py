from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Query

from ..models.regime import RegimeResponse, StrategyFavorability
from ..regime.calculator import current_regime_response
from ..strategies._registry import registry
from .. import strategies as _strategies  # noqa: F401 - register strategies

router = APIRouter(tags=["regime"])
REGIME_CACHE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "regime"
    / "regime_response_cache.json"
)


def _cached_regime() -> RegimeResponse | None:
    if not REGIME_CACHE.exists():
        return None
    try:
        payload = json.loads(REGIME_CACHE.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(
            str(payload["cached_at"]).replace("Z", "+00:00")
        )
        if datetime.now(timezone.utc) - cached_at > timedelta(days=1):
            return None
        response = RegimeResponse.model_validate(payload["response"])
        if response.inputs.spy_sma200 is None or response.inputs.spy_above_sma200 is None:
            return None
        return response
    except Exception:
        return None


def _save_regime_cache(response: RegimeResponse) -> None:
    REGIME_CACHE.parent.mkdir(parents=True, exist_ok=True)
    REGIME_CACHE.write_text(
        json.dumps(
            {
                "cached_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "response": response.model_dump(mode="json"),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


@router.get("/regime", response_model=RegimeResponse)
def get_regime(as_of_date: str | None = Query(default=None)):
    response = _cached_regime() if as_of_date is None else None
    if response is None:
        response = current_regime_response(as_of_date=as_of_date)
    response.per_strategy_favorability = [
        StrategyFavorability(
            slug=strategy.slug,
            name=strategy.name,
            favorability=strategy.regime_favorability.get(response.regime, "Neutral"),
            explanation=(
                f"{strategy.name} is "
                f"{strategy.regime_favorability.get(response.regime, 'Neutral').lower()} "
                f"when the market regime is {response.regime}."
            ),
        )
        for strategy in registry.list_all()
    ]
    if as_of_date is None:
        if response.inputs.spy_sma200 is not None and response.inputs.spy_above_sma200 is not None:
            _save_regime_cache(response)
    return response
