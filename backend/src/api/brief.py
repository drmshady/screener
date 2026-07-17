"""Daily portfolio brief API router (feature 018).

`POST /brief/run` assembles + (unless dry-run) sends one deterministic email per
completed trading session; `GET /brief/status` reports whether/what was last sent.

This Phase-2 skeleton establishes the gating, idempotency, non-trading-day skip,
status, and dry-run edges with **stubbed** assemble/render/send. User Story 1
(T017–T021) replaces `_assemble_brief` / `_render_brief` with the real portfolio
status + attention synthesis and wires the SMTP send; US2/US3 extend them further.

Both routes ride the existing owner-secret gate middleware + CORS pin — no new auth
surface. `brief_enabled()` defaults OFF ⇒ `POST /brief/run` 404s and no email is
ever sent (byte-identical to feature 017 until the owner opts in).
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..data import brief_store
from ..data.freshness import compute_data_freshness
from ..data.market_calendar import is_trading_day, latest_completed_trading_day
from ..lib.disclaimer import DISCLAIMER_TEXT, utc_now_iso
from ..lib.flags import brief_enabled
from ..models.brief import (
    BriefDeliveryRecord,
    BriefModel,
    BriefRunResponse,
    BriefStatusResponse,
    DeliveryStatus,
)
from ..brief import assemble as brief_assemble
from ..brief import email as brief_email
from ..brief import render as brief_render

router = APIRouter(prefix="/brief", tags=["brief"])


class BriefRunRequest(BaseModel):
    dry_run: bool = False


def _target_session() -> date:
    """The completed session the brief reports on = the snapshot's newest as-of.

    Falls back to the latest completed US trading day when no manifest source
    date is available (e.g. a fresh local checkout).
    """
    try:
        snapshot = compute_data_freshness()
        source_dates = [
            record.data_as_of for record in snapshot.sources if record.data_as_of
        ]
        if source_dates:
            return max(source_dates)
        return snapshot.latest_session
    except Exception:
        return latest_completed_trading_day()


def _assemble_brief(target_session: date, *, include_news: bool = True) -> BriefModel:
    """Assemble the full deterministic brief for the target session.

    Delegates to `brief/assemble.py` — the real portfolio-status + attention
    synthesis (US1), the news + market-context sections (US2), and the five ranked
    recommendations (US3). Kept deterministic (no `generated_at` in the hash).
    """
    return brief_assemble.assemble_brief(
        target_session.isoformat(), include_news=include_news
    )


def _render_brief(brief: BriefModel) -> tuple[str, str, str]:
    """Deterministic (subject, text, html) render via `brief/render.py`."""
    return brief_render.render_brief(brief)


@router.get("/status", response_model=BriefStatusResponse)
def brief_status() -> BriefStatusResponse:
    enabled = brief_enabled()
    last_run = brief_store.load_last_run() if enabled else None
    return BriefStatusResponse(
        enabled=enabled,
        last_run=last_run,
        data_as_of=utc_now_iso(),
        disclaimer=DISCLAIMER_TEXT,
    )


@router.post("/run", response_model=BriefRunResponse)
def brief_run(request: BriefRunRequest | None = None) -> BriefRunResponse:
    if not brief_enabled():
        raise HTTPException(status_code=404, detail="Daily brief is not enabled")

    req = request or BriefRunRequest()
    target = _target_session()
    session_iso = target.isoformat()
    brief = _assemble_brief(target)

    # Dry run: assemble + return content without sending or writing a record.
    if req.dry_run:
        return BriefRunResponse(
            status="dry_run",
            target_session=session_iso,
            record=None,
            brief=brief,
            data_as_of=session_iso,
            disclaimer=DISCLAIMER_TEXT,
        )

    # Idempotency (FR-010): at most one delivered brief per target session.
    existing = brief_store.load_last_delivered(session_iso)
    if existing is not None:
        return BriefRunResponse(
            status="delivered",
            target_session=session_iso,
            record=existing,
            data_as_of=session_iso,
            disclaimer=DISCLAIMER_TEXT,
        )

    recipient = brief_email.flags.brief_recipient() or ""

    # Non-trading-day skip (FR-011): never a misleading "today" brief.
    if not is_trading_day(target, "US"):
        record = BriefDeliveryRecord(
            target_session=session_iso,
            status=DeliveryStatus.SKIPPED,
            recipient=recipient,
            reason="Target session is not a completed trading day.",
            attempts=0,
            directive=brief.directive,
            content_hash=brief.content_hash(),
        )
        brief_store.record_run(record)
        return BriefRunResponse(
            status="skipped",
            target_session=session_iso,
            record=record,
            data_as_of=session_iso,
            disclaimer=DISCLAIMER_TEXT,
        )

    subject, text_body, html_body = _render_brief(brief)
    try:
        attempts = brief_email.send_brief(subject, text_body, html_body)
    except brief_email.BriefSendError as exc:
        record = BriefDeliveryRecord(
            target_session=session_iso,
            status=DeliveryStatus.FAILED,
            recipient=recipient,
            reason=str(exc),  # redacted by construction — never the password
            attempts=brief_email.MAX_ATTEMPTS,
            directive=brief.directive,
            content_hash=brief.content_hash(),
        )
        brief_store.record_run(record)
        raise HTTPException(status_code=502, detail=str(exc))

    record = BriefDeliveryRecord(
        target_session=session_iso,
        status=DeliveryStatus.DELIVERED,
        recipient=recipient,
        reason=None,
        attempts=attempts,
        directive=brief.directive,
        content_hash=brief.content_hash(),
    )
    brief_store.record_run(record)
    return BriefRunResponse(
        status="delivered",
        target_session=session_iso,
        record=record,
        data_as_of=session_iso,
        disclaimer=DISCLAIMER_TEXT,
    )
