from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class RefreshDecision:
    action: str
    elapsed_days: float | None
    reason: str


@dataclass(frozen=True)
class FreshnessStatus:
    status: str  # "fresh" | "due_soon" | "stale"
    elapsed_days: float | None
    days_remaining: float | None
    reason: str


def freshness_status(
    now: datetime,
    source_as_of: datetime | None,
    *,
    interval_days: int = 90,
    warn_within_days: int = 14,
) -> FreshnessStatus:
    """Classify a source's age against its refresh deadline (no side effects).

    Unlike ``should_refresh`` (which decides whether to *act*), this is a pure
    reporting helper so the publish chain can warn the owner *before* a source
    crosses its deadline and bakes stale on the host. ``stale`` once the interval
    has elapsed, ``due_soon`` within ``warn_within_days`` of it, else ``fresh``.
    """
    interval = max(int(interval_days), 1)
    if source_as_of is None:
        return FreshnessStatus(
            "stale", None, None, "no successful refresh timestamp recorded"
        )
    elapsed = max(0.0, (_utc(now) - _utc(source_as_of)).total_seconds() / 86400.0)
    remaining = interval - elapsed
    if remaining <= 0:
        return FreshnessStatus(
            "stale",
            elapsed,
            remaining,
            f"{elapsed:.0f} days since last refresh (>= {interval}-day deadline)",
        )
    if remaining <= max(int(warn_within_days), 0):
        return FreshnessStatus(
            "due_soon",
            elapsed,
            remaining,
            f"{remaining:.0f} days until the {interval}-day refresh deadline",
        )
    return FreshnessStatus(
        "fresh",
        elapsed,
        remaining,
        f"{remaining:.0f} days until the {interval}-day refresh deadline",
    )


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
