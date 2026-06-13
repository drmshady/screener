from __future__ import annotations

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..models.portfolio import SizingRequest, SizingResponse
from ..portfolio.sizing import size_position

router = APIRouter(tags=["sizing"])


@router.post(
    "/sizing",
    response_model=SizingResponse,
    responses={422: {"model": SizingResponse}},
)
def sizing_endpoint(request: SizingRequest):
    response = size_position(request)
    if not response.caps_respected:
        return JSONResponse(status_code=422, content=jsonable_encoder(response))
    return response
