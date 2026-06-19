"""Hosted-mode configuration helpers for online deployment."""

import os
from pathlib import Path

_TRUTHY = {"1", "true", "yes", "on"}


def hosted_mode() -> bool:
    """Return whether the app is running in hosted mode."""
    return os.getenv("SCREENER_HOSTED_MODE", "0").strip().lower() in _TRUTHY


def owner_secret() -> str | None:
    """Return the backend owner secret configured for hosted mode."""
    value = os.getenv("SCREENER_OWNER_SECRET")
    if value is None:
        return None
    value = value.strip()
    return value or None


def frontend_origin() -> str | None:
    """Return the hosted frontend origin allowed to call the backend."""
    value = os.getenv("SCREENER_FRONTEND_ORIGIN")
    if value is None:
        return None
    value = value.strip().rstrip("/")
    return value or None


def snapshot_root() -> Path:
    """Return the root of the read-only data snapshot."""
    return Path(__file__).resolve().parents[2] / "data"


def require_hosted_config() -> None:
    """Validate required hosted-mode configuration."""
    if hosted_mode() and owner_secret() is None:
        raise RuntimeError(
            "SCREENER_OWNER_SECRET is required when SCREENER_HOSTED_MODE is enabled."
        )
