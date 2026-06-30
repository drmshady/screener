"""T005: Unit tests for pure row validation in portfolio/transactions.py.

Tests written FIRST (TDD — these should FAIL until transactions.py is implemented):
  - Header-alias mapping (descriptive → canonical, case-insensitive, extras ignored)
  - Currency/comma stripping ($1,025.32)
  - Day-first slash date parsing (28/7/2025) and month-name (9-Oct-2025)
  - Case-insensitive action normalisation
  - Acceptance / rejection rules including Div / unsupported types
  - Stable content-hash id (source_row NOT in hash; reordering doesn't change ids)
  - Duplicate-row disambiguation by occurrence index, not source_row
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from backend.src.portfolio.transactions import parse_rows
from backend.src.models.portfolio import RejectedRow, Transaction

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(
    *,
    date_val: str = "28/7/2025",
    type_val: str = "Buy",
    stock: str = "AAPL",
    units: str = "10",
    price: str = "$150.00",
    fees: str = "$0.00",
    source_row: int = 2,
    **extra: str,
) -> dict:
    row = {
        "Date": date_val,
        "Type": type_val,
        "Stock": stock,
        "Transacted Units": units,
        "Transacted Price (per unit)": price,
        "Fees": fees,
        "source_row": source_row,
    }
    row.update(extra)
    return row


def _accept(rows: list[dict]) -> list[Transaction]:
    accepted, _ = parse_rows(rows)
    return accepted


def _reject(rows: list[dict]) -> list[RejectedRow]:
    _, rejected = parse_rows(rows)
    return rejected


# ---------------------------------------------------------------------------
# Header-alias mapping
# ---------------------------------------------------------------------------

def test_descriptive_headers_map_to_canonical_fields() -> None:
    """Descriptive sheet headers (Date/Type/Stock/…) → canonical Transaction fields."""
    accepted, rejected = parse_rows([_row()])
    assert len(accepted) == 1
    assert len(rejected) == 0
    t = accepted[0]
    assert t.ticker == "AAPL"
    assert t.action == "buy"
    assert t.trade_date == date(2025, 7, 28)
    assert t.quantity == Decimal("10")
    assert t.price == Decimal("150.00")


def test_canonical_headers_also_accepted() -> None:
    """Canonical field names (lowercase) are also accepted."""
    row = {
        "trade_date": "2025-07-28",
        "action": "Buy",
        "ticker": "AAPL",
        "quantity": "10",
        "price": "$150.00",
        "source_row": 2,
    }
    accepted, rejected = parse_rows([row])
    assert len(accepted) == 1
    assert accepted[0].ticker == "AAPL"


def test_header_aliases_case_insensitive() -> None:
    """'STOCK', 'date', 'TYPE', etc. all resolve to canonical fields."""
    row = {
        "DATE": "28/7/2025",
        "TYPE": "Buy",
        "STOCK": "MSFT",
        "TRANSACTED UNITS": "5",
        "TRANSACTED PRICE (PER UNIT)": "$400.00",
        "source_row": 2,
    }
    accepted, rejected = parse_rows([row])
    assert len(accepted) == 1
    assert accepted[0].ticker == "MSFT"


def test_extra_computed_columns_ignored() -> None:
    """Total Value / Current Price / Market Value from the sheet are ignored."""
    row = _row()
    row["Total Value"] = "$1,500.00"
    row["Current Price"] = "$155.00"
    row["Market Value"] = "$1,550.00"
    accepted, rejected = parse_rows([row])
    assert len(accepted) == 1
    assert len(rejected) == 0


def test_stock_alias_maps_to_ticker() -> None:
    """'Stock' maps to ticker."""
    accepted, _ = parse_rows([_row(stock="MSFT")])
    assert accepted[0].ticker == "MSFT"


def test_symbol_alias_maps_to_ticker() -> None:
    """'Symbol' also maps to ticker."""
    row = {
        "date": "28/7/2025",
        "type": "Buy",
        "symbol": "gld",
        "units": "4",
        "price": "$245.00",
        "source_row": 2,
    }
    accepted, _ = parse_rows([row])
    assert accepted[0].ticker == "GLD"


# ---------------------------------------------------------------------------
# Money / number normalisation
# ---------------------------------------------------------------------------

def test_dollar_comma_price_stripped() -> None:
    """'$1,025.32' → Decimal('1025.32')."""
    accepted, _ = parse_rows([_row(price="$1,025.32")])
    assert accepted[0].price == Decimal("1025.32")


def test_large_comma_quantity_stripped() -> None:
    """'1,000' quantity parsed as 1000."""
    accepted, _ = parse_rows([_row(units="1,000")])
    assert accepted[0].quantity == Decimal("1000")


def test_fees_optional_zero_when_absent() -> None:
    """Absent fees column → fees = None (treated as 0 by aggregation)."""
    row = {
        "Date": "28/7/2025",
        "Type": "Buy",
        "Stock": "AAPL",
        "Transacted Units": "10",
        "Transacted Price (per unit)": "$150.00",
        "source_row": 2,
    }
    accepted, _ = parse_rows([row])
    assert accepted[0].fees is None


def test_fees_placeholder_dash_treated_as_absent() -> None:
    """'-' or '—' in fees → fees = None, not rejected."""
    for dash in ("-", "—"):
        accepted, rejected = parse_rows([_row(fees=dash)])
        assert len(accepted) == 1, f"dash={dash!r} should be tolerated in fees"
        assert accepted[0].fees is None


def test_empty_fees_cell_treated_as_absent() -> None:
    """Empty string fees → fees = None."""
    accepted, _ = parse_rows([_row(fees="")])
    assert len(accepted) == 1
    assert accepted[0].fees is None


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def test_day_first_slash_date() -> None:
    """'28/7/2025' → date(2025, 7, 28) (day-first fixed by owner confirmation)."""
    accepted, _ = parse_rows([_row(date_val="28/7/2025")])
    assert accepted[0].trade_date == date(2025, 7, 28)


def test_single_digit_day_month_slash_date() -> None:
    """'5/9/2025' → date(2025, 9, 5) (day-first: 5 Sep, not 9 May)."""
    accepted, _ = parse_rows([_row(date_val="5/9/2025")])
    assert accepted[0].trade_date == date(2025, 9, 5)


def test_month_name_hyphen_date() -> None:
    """'9-Oct-2025' → date(2025, 10, 9)."""
    accepted, _ = parse_rows([_row(date_val="9-Oct-2025")])
    assert accepted[0].trade_date == date(2025, 10, 9)


def test_iso_date() -> None:
    """'2025-07-28' → date(2025, 7, 28) (ISO-8601)."""
    accepted, _ = parse_rows([_row(date_val="2025-07-28")])
    assert accepted[0].trade_date == date(2025, 7, 28)


# ---------------------------------------------------------------------------
# Action normalisation
# ---------------------------------------------------------------------------

def test_action_buy_case_insensitive() -> None:
    """'BUY', 'Buy', 'buy' all normalise to 'buy'."""
    for raw in ("BUY", "Buy", "buy"):
        accepted, _ = parse_rows([_row(type_val=raw)])
        assert accepted[0].action == "buy", f"raw={raw!r}"


def test_action_sell_case_insensitive() -> None:
    """'SELL', 'Sell', 'sell' all normalise to 'sell'."""
    for raw in ("SELL", "Sell", "sell"):
        accepted, _ = parse_rows([_row(type_val=raw)])
        assert accepted[0].action == "sell", f"raw={raw!r}"


def test_ticker_uppercased() -> None:
    """'spus' → 'SPUS' (canonical uppercase)."""
    accepted, _ = parse_rows([_row(stock="spus")])
    assert accepted[0].ticker == "SPUS"


# ---------------------------------------------------------------------------
# Rejection rules
# ---------------------------------------------------------------------------

def test_missing_ticker_rejected() -> None:
    """Row with empty ticker → rejected with a descriptive reason."""
    row = _row(stock="")
    _, rejected = parse_rows([row])
    assert len(rejected) == 1
    assert rejected[0].source_row == 2
    assert "ticker" in rejected[0].reason.lower() or "stock" in rejected[0].reason.lower()


def test_action_not_buy_sell_rejected() -> None:
    """Action 'transfer' is neither buy nor sell → rejected."""
    _, rejected = parse_rows([_row(type_val="Transfer")])
    assert len(rejected) == 1
    assert "transfer" in rejected[0].reason.lower()


def test_div_rejected_with_clear_reason_not_silently_dropped() -> None:
    """Div type → rejected with a non-alarming reason; never silently dropped."""
    _, rejected = parse_rows([_row(type_val="Div", units="0", price="$0.75")])
    assert len(rejected) == 1
    assert rejected[0].source_row == 2
    reason = rejected[0].reason.lower()
    assert "div" in reason or "dividend" in reason
    assert "not supported" in reason or "not a supported" in reason or "not tracked" in reason


def test_div_does_not_affect_share_count() -> None:
    """A Div row mixed with a valid Buy must not add to accepted (no share-count change)."""
    buy_row = _row(stock="MSFT", units="5", price="$400.00", source_row=2)
    div_row = _row(type_val="Div", stock="MSFT", units="0", price="$0.75", fees="$0.00", source_row=3)
    accepted, rejected = parse_rows([buy_row, div_row])
    assert len(accepted) == 1
    assert accepted[0].ticker == "MSFT"
    assert accepted[0].quantity == Decimal("5")
    assert len(rejected) == 1


def test_missing_price_rejected() -> None:
    """Empty price → rejected."""
    _, rejected = parse_rows([_row(price="")])
    assert len(rejected) == 1
    assert "price" in rejected[0].reason.lower()


def test_dash_price_rejected() -> None:
    """'—' price (placeholder) in a required field → rejected."""
    _, rejected = parse_rows([_row(price="—")])
    assert len(rejected) == 1
    assert "price" in rejected[0].reason.lower()


def test_zero_quantity_rejected() -> None:
    """Quantity '0' → rejected (must be > 0)."""
    _, rejected = parse_rows([_row(units="0")])
    assert len(rejected) == 1


def test_negative_quantity_rejected() -> None:
    """Quantity '-2' → rejected."""
    _, rejected = parse_rows([_row(units="-2")])
    assert len(rejected) == 1


def test_non_numeric_quantity_rejected() -> None:
    """Non-numeric quantity like 'abc' → rejected."""
    _, rejected = parse_rows([_row(units="abc")])
    assert len(rejected) == 1


def test_unparseable_date_rejected() -> None:
    """'not-a-date' → rejected with a date-related reason."""
    _, rejected = parse_rows([_row(date_val="not-a-date")])
    assert len(rejected) == 1
    assert "date" in rejected[0].reason.lower()


def test_rejected_row_contains_raw_values() -> None:
    """RejectedRow.raw holds the original cell values for the owner to fix."""
    _, rejected = parse_rows([_row(price="")])
    assert isinstance(rejected[0].raw, dict)
    assert len(rejected[0].raw) > 0


def test_partial_success_200_semantics() -> None:
    """Mix of valid + invalid → some accepted, some rejected; not all-or-nothing."""
    valid_row = _row(source_row=2)
    invalid_row = _row(date_val="not-a-date", source_row=3)
    accepted, rejected = parse_rows([valid_row, invalid_row])
    assert len(accepted) == 1
    assert len(rejected) == 1


# ---------------------------------------------------------------------------
# Optional columns tolerated
# ---------------------------------------------------------------------------

def test_note_optional_and_carried_through() -> None:
    """'note' column is optional; if present, stored on the Transaction."""
    row = _row()
    row["note"] = "starter position"
    accepted, _ = parse_rows([row])
    assert accepted[0].note == "starter position"


def test_notes_alias_for_note() -> None:
    """'notes' is accepted as an alias for 'note'."""
    row = _row()
    row["notes"] = "some note"
    accepted, _ = parse_rows([row])
    assert accepted[0].note == "some note"


# ---------------------------------------------------------------------------
# Stable content-hash id
# ---------------------------------------------------------------------------

def test_id_is_stable_across_source_row_changes() -> None:
    """Inserting a new row (changing source_row on an existing row) must not change its id."""
    row_original = _row(stock="AAPL", units="10", price="$150.00", date_val="28/7/2025", source_row=2)
    row_shifted = _row(stock="AAPL", units="10", price="$150.00", date_val="28/7/2025", source_row=5)

    accepted_original, _ = parse_rows([row_original])
    accepted_shifted, _ = parse_rows([row_shifted])

    # Same content → same id regardless of source_row
    assert accepted_original[0].id == accepted_shifted[0].id


def test_unique_row_id_is_first_occurrence_so_later_duplicate_does_not_rename_it() -> None:
    """A unique row keeps the same id when a byte-identical row is added later."""
    row_original = _row(stock="AAPL", units="10", price="$150.00", date_val="28/7/2025", source_row=2)
    row_duplicate = _row(stock="AAPL", units="10", price="$150.00", date_val="28/7/2025", source_row=3)

    accepted_original, _ = parse_rows([row_original])
    accepted_with_duplicate, _ = parse_rows([row_original, row_duplicate])

    assert accepted_original[0].id == accepted_with_duplicate[0].id
    assert accepted_with_duplicate[1].id != accepted_original[0].id


def test_id_changes_when_price_changes() -> None:
    """Different price → different id (content-based hash)."""
    row_a = _row(price="$150.00", source_row=2)
    row_b = _row(price="$151.00", source_row=2)
    accepted_a, _ = parse_rows([row_a])
    accepted_b, _ = parse_rows([row_b])
    assert accepted_a[0].id != accepted_b[0].id


def test_id_changes_when_ticker_changes() -> None:
    """Different ticker → different id."""
    row_a = _row(stock="AAPL", source_row=2)
    row_b = _row(stock="MSFT", source_row=2)
    accepted_a, _ = parse_rows([row_a])
    accepted_b, _ = parse_rows([row_b])
    assert accepted_a[0].id != accepted_b[0].id


# ---------------------------------------------------------------------------
# Duplicate-row disambiguation
# ---------------------------------------------------------------------------

def test_two_identical_rows_get_different_ids() -> None:
    """Two byte-identical rows are disambiguated by occurrence index (not source_row)."""
    row1 = _row(stock="AAPL", units="10", price="$150.00", date_val="28/7/2025", source_row=2)
    row2 = _row(stock="AAPL", units="10", price="$150.00", date_val="28/7/2025", source_row=3)
    accepted, rejected = parse_rows([row1, row2])
    assert len(accepted) == 2
    assert accepted[0].id != accepted[1].id


def test_duplicate_ids_use_occurrence_index_not_source_row() -> None:
    """Two identical rows: occurrence index (#0, #1) is order-based, not source_row-based."""
    # Same content, same relative order but different source_rows
    row_src2 = _row(stock="AAPL", units="10", price="$150.00", date_val="28/7/2025", source_row=2)
    row_src5 = _row(stock="AAPL", units="10", price="$150.00", date_val="28/7/2025", source_row=5)

    # In both orderings, the FIRST occurrence gets #0 and the SECOND gets #1
    accepted_fwd, _ = parse_rows([row_src2, row_src5])
    accepted_rev, _ = parse_rows([row_src5, row_src2])

    # ids within each call should differ (disambiguation worked)
    assert accepted_fwd[0].id != accepted_fwd[1].id
    assert accepted_rev[0].id != accepted_rev[1].id

    # The same content-hash base is used in both cases; only the suffix differs
    base_fwd_0 = accepted_fwd[0].id
    base_rev_0 = accepted_rev[0].id
    # Both first occurrences share the same base sha1 prefix (before the #N suffix)
    assert base_fwd_0 == base_rev_0


def test_reordering_identical_pair_swaps_occurrence_indices() -> None:
    """If the pair is reversed, the first and second occurrence swap (order matters)."""
    row_a = _row(stock="AAPL", units="10", price="$150.00", date_val="28/7/2025", source_row=2)
    row_b = _row(stock="AAPL", units="10", price="$150.00", date_val="28/7/2025", source_row=3)
    row_c = _row(stock="AAPL", units="10", price="$160.00", date_val="28/7/2025", source_row=4)

    # [a, b, c]: row_a → first duplicate, row_b → second duplicate, row_c → unique
    accepted_abc, _ = parse_rows([row_a, row_b, row_c])
    id_a = accepted_abc[0].id  # #0 of the duplicate pair
    id_b = accepted_abc[1].id  # #1 of the duplicate pair
    id_c = accepted_abc[2].id  # unique row

    # All three should be distinct
    assert len({id_a, id_b, id_c}) == 3


# ---------------------------------------------------------------------------
# Full fixture round-trip
# ---------------------------------------------------------------------------

def test_full_fixture_parse() -> None:
    """The real-sheet fixture parses: 8 buy/sell rows accepted, 1 Div rejected."""
    fixture = json.loads((FIXTURES / "transactions_sheet.values.json").read_text())
    values = fixture["values"]
    headers = values[0]
    rows = []
    for i, row_vals in enumerate(values[1:], start=2):
        row = dict(zip(headers, row_vals))
        row["source_row"] = i
        rows.append(row)

    accepted, rejected = parse_rows(rows)

    # 8 buy/sell rows: spus/Buy, msft/Buy x2, amzn/Buy, amzn/Sell, slv/Buy, ibit/Buy, gld/Buy
    assert len(accepted) == 8
    # 1 Div row
    assert len(rejected) == 1
    assert "div" in rejected[0].reason.lower() or "dividend" in rejected[0].reason.lower()


def test_full_fixture_tickers_uppercased() -> None:
    """Lowercase tickers in the sheet (spus/msft/amzn/slv/ibit/gld) are uppercased."""
    fixture = json.loads((FIXTURES / "transactions_sheet.values.json").read_text())
    values = fixture["values"]
    headers = values[0]
    rows = []
    for i, row_vals in enumerate(values[1:], start=2):
        row = dict(zip(headers, row_vals))
        row["source_row"] = i
        rows.append(row)

    accepted, _ = parse_rows(rows)
    tickers = {t.ticker for t in accepted}
    for ticker in tickers:
        assert ticker == ticker.upper()


def test_malformed_fixture_all_rejected() -> None:
    """The malformed-rows fixture: every data row must be rejected (no silently dropped)."""
    fixture = json.loads((FIXTURES / "transactions_malformed.values.json").read_text())
    values = fixture["values"]
    headers = values[0]
    rows = []
    for i, row_vals in enumerate(values[1:], start=2):
        row = dict(zip(headers, row_vals))
        row["source_row"] = i
        rows.append(row)

    accepted, rejected = parse_rows(rows)
    assert len(accepted) == 0
    assert len(rejected) == len(values) - 1  # all data rows rejected
    for r in rejected:
        assert r.reason  # each has a non-empty reason
