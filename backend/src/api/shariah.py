from __future__ import annotations

from fastapi import APIRouter, Query

from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from ..models.shariah import ShariahStatusResponse
from ..shariah.lookup import ShariahLookup

router = APIRouter(prefix="/shariah", tags=["shariah"])


@router.get("/status/{ticker}", response_model=ShariahStatusResponse)
def get_shariah_status(
    ticker: str,
    sources: str | None = Query(default=None),
    include: str | None = Query(default=None),
    exclude: str | None = Query(default=None),
):
    lookup = ShariahLookup(
        {
            "active_sources": sources,
            "include": include,
            "exclude": exclude,
        }
    )
    status = lookup.status(ticker)
    return ShariahStatusResponse(
        **status.model_dump(),
        data_as_of=utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )
