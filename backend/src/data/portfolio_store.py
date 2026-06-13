"""Server-side persistence for the single-user portfolio/watchlist/settings blob.

The browser already keeps this in localStorage, but that is per-browser and
per-origin, so the app appears to "start from the beginning" on a different
browser/URL or after clearing site data. For the personal deployment we persist
the same blob server-side as one JSON file (single user, no auth, no concurrency)
so it survives restarts, browsers, and origins. The blob is opaque on the server
— the frontend store owns its shape — which keeps the two loosely coupled.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def _state_path() -> Path:
    base = os.getenv("SCREENER_DATA_DIR")
    data_dir = Path(base) if base else (ROOT / "backend" / "data")
    return data_dir / "portfolio_state.json"


def load_portfolio_state() -> dict[str, Any] | None:
    """Return the stored {state, updated_at} envelope, or None if never saved."""
    path = _state_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_portfolio_state(state: dict[str, Any]) -> str:
    """Persist the opaque state blob; returns the updated_at timestamp."""
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    envelope = {"state": state, "updated_at": updated_at}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    tmp.replace(path)  # atomic-ish swap
    return updated_at
