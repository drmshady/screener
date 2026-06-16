"""On-demand independent verification endpoint (feature 008).

``GET /candidate/{ticker}/verify`` cross-checks one candidate's screener price /
52-week-high against a free-tier third-party vendor (Finnhub primary, Alpha
Vantage fallback; ``data/independent_quote``). It is **explicitly user-triggered**
— the deterministic, network-free live screen (FR-002/FR-024) never calls it. The
API key is read process-locally from ``SCREENER_INDEPENDENT_QUOTE_API_KEY`` and is
never written to a file (FR-009). A missing key / network error yields verdict
``UNVERIFIED`` and never raises.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, HTTPException

from .. import strategies as _strategies  # noqa: F401 - registers strategies
from ..data.independent_quote import (
    INDEPENDENT_QUOTE_KEY_ENV,
    build_default_independent_provider,
)
from ..lib.disclaimer import DISCLAIMER_TEXT
from ..models.strategy import IndependentVerifyResponse
from ..screening.engine import build_single_ticker_snapshot
from ..screening.integrity.engine import evaluate_contract
from ..screening.integrity.harness import classify_verdict, compute_divergence
from ..strategies.midterm_52w_high_momentum import OUTPUT_CONTRACT

router = APIRouter(prefix="/candidate", tags=["verify"])


def _f(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@router.get("/{ticker}/verify", response_model=IndependentVerifyResponse)
def verify_candidate(ticker: str, as_of: str | None = None) -> IndependentVerifyResponse:
    symbol = ticker.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Ticker is required")
    try:
        snapshot, data_as_of, _notes = build_single_ticker_snapshot(symbol, as_of=as_of)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Run the same output contract the live screen uses so the verdict's
    # "screener already flagged this" input matches what a screen would show.
    annotated = evaluate_contract(snapshot, OUTPUT_CONTRACT)
    row = annotated.iloc[0]
    screener_price = _f(row.get("close"))
    screener_high = _f(row.get("52w_high"))
    screener_flagged = bool(row.get("data_suspect", False))

    key_configured = bool(os.getenv(INDEPENDENT_QUOTE_KEY_ENV))
    quote = build_default_independent_provider().quote(symbol)
    fetched_at = datetime.now(timezone.utc).isoformat()

    independent_price = quote.price if quote.available else None
    independent_high = quote.high_52w if quote.available else None
    divergence = compute_divergence(screener_price, independent_price)
    verdict = classify_verdict(
        screener_price=screener_price,
        independent_price=independent_price,
        has_warning=screener_flagged,
        stale=False,
    )

    return IndependentVerifyResponse(
        ticker=symbol,
        screener_price=screener_price,
        screener_52w_high=screener_high,
        independent_price=independent_price,
        independent_52w_high=independent_high,
        independent_source=quote.source,
        divergence_pct=divergence,
        verdict=verdict,
        screener_flagged=screener_flagged,
        key_configured=key_configured,
        fetched_at=fetched_at,
        data_as_of=data_as_of,
        disclaimer=DISCLAIMER_TEXT,
    )
