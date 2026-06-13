from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..models.strategy import ScreenResult
from ..screening.engine import run_strategy

router = APIRouter(prefix="/api/v1/screen", tags=["screen"])


class ScreenRequest(BaseModel):
    strategy_slug: str
    settings: dict[str, Any] = Field(default_factory=dict)


@router.post("", response_model=ScreenResult)
def run_screen(req: ScreenRequest):
    try:
        return run_strategy(
            req.strategy_slug,
            parameters=req.settings,
            filters={
                "shariah_only": bool(req.settings.get("shariah_filter_on", False))
            },
            shariah_overrides={
                "active_sources": req.settings.get(
                    "shariah_external_sources", ["spus_holdings"]
                ),
                "inclusion": req.settings.get("shariah_user_inclusion", []),
                "exclusion": req.settings.get("shariah_user_exclusion", []),
            },
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Strategy not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
