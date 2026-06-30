"""Server-side persistence for the single-user portfolio/watchlist/settings blob.

The browser already keeps this in localStorage, but that is per-browser and
per-origin, so the app appears to "start from the beginning" on a different
browser/URL or after clearing site data. For the personal deployment we persist
the same blob server-side as one JSON file (single user, no auth, no concurrency)
so it survives restarts, browsers, and origins. The blob is opaque on the server
— the frontend store owns its shape — which keeps the two loosely coupled.

Feature 013 adds three server-owned keys within `state`: `transactions`,
`sheet_id`, and `sheet_range`. The `load_transactions` / `save_transactions` /
`clear_transactions` helpers read and write only those keys, leaving the rest of
the opaque blob intact.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models.portfolio import Transaction

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


# ---------------------------------------------------------------------------
# Feature 013: transactions-aware helpers
# ---------------------------------------------------------------------------

def load_transactions() -> tuple[list[Transaction], str | None, str | None]:
    """Return (transactions, sheet_id, sheet_range) from the persisted blob.

    Returns ([], None, None) when the blob is missing or has no transactions.
    Validates each stored row against the Transaction model so corrupted rows
    raise immediately rather than silently producing bad data.
    """
    from ..models.portfolio import Transaction  # local to avoid circular import at module load

    envelope = load_portfolio_state()
    if not envelope:
        return [], None, None
    state: dict[str, Any] = envelope.get("state") or {}
    raw_txns = state.get("transactions") or []
    transactions = [Transaction.model_validate(t) for t in raw_txns]
    return transactions, state.get("sheet_id"), state.get("sheet_range")


def save_transactions(
    transactions: list[Transaction],
    sheet_id: str | None,
    sheet_range: str | None,
) -> str:
    """Atomically persist transactions + sheet metadata, preserving the rest of the blob.

    Uses model_dump(mode="json") so Decimal and date values are serialized as
    strings, which json.dumps can handle without a custom encoder.
    Returns the updated_at timestamp.
    """
    envelope = load_portfolio_state()
    state: dict[str, Any] = (envelope.get("state") or {}) if envelope else {}
    state["transactions"] = [t.model_dump(mode="json") for t in transactions]
    state["sheet_id"] = sheet_id
    state["sheet_range"] = sheet_range
    return save_portfolio_state(state)


def clear_transactions() -> str:
    """Remove all transactions and sheet metadata (FR-007 clear/replace path).

    Preserves all other keys in the blob (watchlist, settings, etc.).
    Returns the updated_at timestamp.
    """
    envelope = load_portfolio_state()
    state: dict[str, Any] = (envelope.get("state") or {}) if envelope else {}
    state["transactions"] = []
    state.pop("sheet_id", None)
    state.pop("sheet_range", None)
    return save_portfolio_state(state)
