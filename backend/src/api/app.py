from __future__ import annotations

import hmac
import json

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from ..lib import hosting
from . import (
    analyze,
    backtest,
    candidates,
    data,
    events,
    health,
    meta,
    portfolio,
    regime,
    screen,
    shariah,
    sizing,
    strategies,
    verify,
)

LOCAL_CORS_ORIGINS = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:3100",
    "http://localhost:3100",
    "http://192.168.1.138:3000",
]


def _cors_origins() -> list[str]:
    if hosting.hosted_mode():
        origin = hosting.frontend_origin()
        return [origin] if origin else []
    return LOCAL_CORS_ORIGINS


# Liveness/health probes carry no screener data and the platform calls them
# without the owner secret, so they must stay reachable through the gate.
_GATE_EXEMPT_PATHS = {"/health", "/healthz"}


async def owner_secret_gate_middleware(request: Request, call_next):
    if not hosting.hosted_mode():
        return await call_next(request)
    if request.method.upper() == "OPTIONS":
        return await call_next(request)
    if request.url.path in _GATE_EXEMPT_PATHS:
        return await call_next(request)

    expected = hosting.owner_secret()
    if expected is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "Hosted mode is missing owner-secret configuration."},
        )

    supplied = request.headers.get("x-owner-secret", "")
    if not hmac.compare_digest(supplied, expected):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


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


def create_app() -> FastAPI:
    hosting.require_hosted_config()
    app = FastAPI(title="US Stock Screener MVP")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(add_disclaimer_middleware)
    app.middleware("http")(owner_secret_gate_middleware)

    app.include_router(health.router)
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
    app.include_router(verify.router)
    return app


app = create_app()
