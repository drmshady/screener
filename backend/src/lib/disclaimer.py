from __future__ import annotations

from datetime import datetime, timezone

DISCLAIMER_TEXT = (
    "This product is for informational purposes only and does not constitute financial advice. "
    "It does not place trades."
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
