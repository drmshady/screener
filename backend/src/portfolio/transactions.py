"""Pure row validation: map, normalise, validate, and hash-id sheet rows.

Called by POST /portfolio/import. No I/O; deterministic.

Input: list of raw dicts keyed by either descriptive sheet-header names
(Date / Type / Stock / Transacted Units / Transacted Price (per unit) / Fees)
or canonical field names (trade_date / action / ticker / quantity / price / fees).
Values are raw strings as returned by the Google Sheets API. Each row must
include 'source_row' (int, 1-based).

Output: (accepted: list[Transaction], rejected: list[RejectedRow])
Every non-accepted row becomes a RejectedRow — nothing is silently dropped.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha1
from typing import Any

from ..models.portfolio import RejectedRow, Transaction, money

# ---------------------------------------------------------------------------
# Header-alias table (case-insensitive, whitespace-trimmed)
# ---------------------------------------------------------------------------

_ALIASES: dict[str, list[str]] = {
    "trade_date": ["trade_date", "date"],
    "action": ["action", "type"],
    "ticker": ["ticker", "stock", "symbol"],
    "quantity": ["quantity", "transacted units", "units"],
    "price": ["price", "transacted price (per unit)", "price (per unit)"],
    "fees": ["fees", "fee"],
    "note": ["note", "notes"],
}

_ALIAS_MAP: dict[str, str] = {
    alias.lower(): canonical
    for canonical, aliases in _ALIASES.items()
    for alias in aliases
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _map_headers(raw: dict[str, Any]) -> dict[str, Any]:
    """Translate descriptive header names → canonical field names.

    Unknown keys (computed columns, etc.) are silently dropped.
    'source_row' is always carried through unchanged.
    """
    out: dict[str, Any] = {}
    for key, val in raw.items():
        if key == "source_row":
            out["source_row"] = val
            continue
        canonical = _ALIAS_MAP.get(key.strip().lower())
        if canonical is not None:
            out[canonical] = val
    return out


_MONTH_NAMES: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date(raw: str) -> date | None:
    """Try three formats; return None on failure.

    1. Day-first slash: D/M/YYYY  (e.g. '28/7/2025', '5/9/2025')
    2. Month-name hyphen: D-Mon-YYYY  (e.g. '9-Oct-2025')
    3. ISO: YYYY-MM-DD
    """
    s = raw.strip()
    if not s:
        return None

    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            return None

    m = re.fullmatch(r"(\d{1,2})-([A-Za-z]+)-(\d{4})", s)
    if m:
        day = int(m.group(1))
        month = _MONTH_NAMES.get(m.group(2).lower()[:3])
        year = int(m.group(3))
        if month is None:
            return None
        try:
            return date(year, month, day)
        except ValueError:
            return None

    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    return None


_PLACEHOLDER = re.compile(r"^[-—]$")


def _parse_money(raw: str) -> Decimal | None:
    """Strip '$', thousands ',', whitespace; parse Decimal. None for placeholder/empty."""
    s = str(raw).strip()
    if not s or _PLACEHOLDER.match(s):
        return None
    s = s.replace("$", "").replace(",", "").strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


_UNSUPPORTED_ACTIONS = {"div", "dividend", "transfer", "split", "spinoff", "merger"}


def _content_hash(
    ticker: str, action: str, quantity: Decimal, price: Decimal, trade_date: date
) -> str:
    """Stable sha1 over normalised fields. source_row intentionally excluded."""
    key = f"{ticker}|{action}|{quantity}|{price}|{trade_date.isoformat()}"
    return sha1(key.encode()).hexdigest()  # noqa: S324 — not a security use


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_rows(
    raw_rows: list[dict[str, Any]],
) -> tuple[list[Transaction], list[RejectedRow]]:
    """Parse and validate raw sheet rows.

    Returns (accepted, rejected). Every non-accepted row appears in rejected
    with a human-readable reason — nothing is silently dropped.
    """
    accepted_pairs: list[tuple[str, Transaction]] = []  # (base_hash, txn)
    rejected: list[RejectedRow] = []

    for raw in raw_rows:
        source_row: int = int(raw.get("source_row", 0))
        raw_display = {k: v for k, v in raw.items() if k != "source_row"}
        mapped = _map_headers(raw)

        def _reject(reason: str) -> None:
            rejected.append(RejectedRow(source_row=source_row, raw=raw_display, reason=reason))

        # --- ticker ---
        ticker = str(mapped.get("ticker", "")).strip().upper()
        if not ticker:
            _reject("ticker (stock symbol) is required but was empty")
            continue

        # --- action ---
        action_raw = str(mapped.get("action", "")).strip().lower()
        if action_raw in _UNSUPPORTED_ACTIONS:
            _reject(
                f"type '{action_raw}' is not a supported buy/sell transaction; "
                "only buy and sell are tracked in v1"
            )
            continue
        if action_raw not in {"buy", "sell"}:
            _reject(f"action '{action_raw}' is not recognised; expected 'buy' or 'sell'")
            continue

        # --- quantity ---
        qty_raw = str(mapped.get("quantity", "")).strip()
        qty = _parse_money(qty_raw)
        if qty is None:
            _reject(f"quantity '{qty_raw}' is not a positive number")
            continue
        if qty <= 0:
            _reject(f"quantity '{qty_raw}' must be greater than zero (got {qty})")
            continue

        # --- price ---
        price_raw = str(mapped.get("price", "")).strip()
        price = _parse_money(price_raw)
        if price is None:
            _reject(f"price '{price_raw}' is not a positive number")
            continue
        if price <= 0:
            _reject(f"price '{price_raw}' must be greater than zero (got {price})")
            continue

        # --- trade_date ---
        date_raw = str(mapped.get("trade_date", "")).strip()
        trade_date = _parse_date(date_raw)
        if trade_date is None:
            _reject(
                f"date '{date_raw}' could not be parsed; "
                "expected DD/MM/YYYY, D-Mon-YYYY, or YYYY-MM-DD"
            )
            continue

        # --- fees (optional) ---
        fees_raw = str(mapped.get("fees", "")).strip()
        fees: Decimal | None = None
        if fees_raw and not _PLACEHOLDER.match(fees_raw):
            fees = _parse_money(fees_raw)  # failure → treat as absent

        # --- note (optional) ---
        note_val = mapped.get("note")
        note: str | None = str(note_val).strip() or None if note_val is not None else None

        base_hash = _content_hash(ticker, action_raw, qty, money(price), trade_date)
        txn = Transaction(
            id=base_hash,  # will be updated in second pass
            ticker=ticker,
            action=action_raw,  # type: ignore[arg-type]
            quantity=qty,
            price=money(price),
            trade_date=trade_date,
            fees=money(fees) if fees is not None else None,
            note=note,
            source_row=source_row,
        )
        accepted_pairs.append((base_hash, txn))

    # Second pass: always assign an occurrence-index suffix. This keeps the
    # first copy's id stable if a byte-identical row is added in a later import:
    # one row -> hash#0, two rows -> hash#0/hash#1.
    # Occurrence is determined by input order (not source_row).
    occurrence: Counter[str] = Counter()

    final_accepted: list[Transaction] = []
    for base_hash, txn in accepted_pairs:
        idx = occurrence[base_hash]
        occurrence[base_hash] += 1
        final_accepted.append(txn.model_copy(update={"id": f"{base_hash}#{idx}"}))

    return final_accepted, rejected
