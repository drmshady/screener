from __future__ import annotations

import json

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from . import (
    analyze,
    backtest,
    candidates,
    data,
    events,
    meta,
    portfolio,
    regime,
    screen,
    shariah,
    sizing,
    strategies,
)

app = FastAPI(title="US Stock Screener MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:3100",
        "http://localhost:3100",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_disclaimer_middleware(request: Request, call_next):
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type or response.status_code >= 400:
        return response

    body = b""
    async for chunk in response.body_iterator:
        body += chunk

    if not body:
        return response

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    if isinstance(payload, dict):
        payload.setdefault("disclaimer", DISCLAIMER_TEXT)
        payload.setdefault("data_as_of", utc_now_iso())

    headers = dict(response.headers)
    headers.pop("content-length", None)
    return JSONResponse(
        content=payload,
        status_code=response.status_code,
        headers=headers,
    )


app.include_router(meta.router)
app.include_router(analyze.router)
app.include_router(strategies.router)
app.include_router(backtest.router)
app.include_router(candidates.router)
app.include_router(events.router)
app.include_router(regime.router)
app.include_router(shariah.router)
app.include_router(sizing.router)
app.include_router(portfolio.router)
app.include_router(screen.router)
app.include_router(data.router)
