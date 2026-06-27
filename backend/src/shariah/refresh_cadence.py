from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class RefreshDecision:
    action: str
    elapsed_days: float | None
    reason: str


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def should_refresh(
    now: datetime,
    last_success_at: datetime | None,
    *,
    interval_days: int = 90,
    force: bool = False,
    key_present: bool = True,
) -> RefreshDecision:
    """Return the deterministic Halal Terminal refresh cadence decision."""
    interval = max(int(interval_days), 1)
    now_utc = _utc(now)
    elapsed_days: float | None = None
    if last_success_at is not None:
        elapsed_days = max(
            0.0, (now_utc - _utc(last_success_at)).total_seconds() / 86400.0
        )

    if force:
        if key_present:
            return RefreshDecision(
                "refresh",
                elapsed_days,
                "force refresh requested - refreshing",
            )
        return RefreshDecision(
            "stale",
            elapsed_days,
            "compliance data stale - force refresh requested but API key is unavailable",
        )

    if last_success_at is None:
        if key_present:
            return RefreshDecision(
                "refresh",
                None,
                "missing last successful refresh timestamp - refreshing",
            )
        return RefreshDecision(
            "stale",
            None,
            "compliance data stale - missing last successful refresh timestamp and API key is unavailable",
        )

    if elapsed_days is not None and elapsed_days < interval:
        return RefreshDecision(
            "skip",
            elapsed_days,
            f"within {interval}-day window - reusing cache",
        )

    if key_present:
        return RefreshDecision(
            "refresh",
            elapsed_days,
            f"{interval} days elapsed - refreshing",
        )

    return RefreshDecision(
        "stale",
        elapsed_days,
        f"compliance data stale - {interval} days elapsed and API key is unavailable",
    )
