from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..data.snapshot import check_snapshot_integrity

router = APIRouter()


@router.get("/health")
def health() -> JSONResponse:
    """Snapshot-integrity health probe used by the deployment platform.

    Returns 200 only when the read-only snapshot is complete (manifest parses +
    key stores present), so a partial/corrupt freshly published image never
    receives traffic — the atomic swap keeps the last good image serving and a
    genuinely absent snapshot surfaces as an explicit maintenance state. Exposes
    no screener data, so it is exempt from the owner-secret gate (the platform
    probe carries no secret).
    """
    integrity = check_snapshot_integrity()
    status_code = 200 if integrity.ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if integrity.ok else "maintenance",
            "snapshot_ok": integrity.ok,
            "manifest_ok": integrity.manifest_ok,
            "stores": integrity.present,
            "missing": list(integrity.missing),
        },
    )
