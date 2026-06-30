"""T006: Unit tests for pure aggregation (portfolio/aggregation.py).

Tests written FIRST (TDD): these should FAIL until aggregation.py is implemented.

Covers:
  - Net quantity = Σ(buy qty) − Σ(sell qty)
  - Share-weighted average cost of buys (sells don't move the avg)
  - Realized P/L from sells (incl. fees)
  - status: open / closed / anomalous
  - earliest_buy_date and most_recent_buy_date
  - Determinism: identical inputs → identical output
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.src.portfolio.aggregation import aggregate
from backend.src.models.portfolio import Transaction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _txn(
    *,
    ticker: str = "AAPL",
    action: str = "buy",
    quantity: str = "10",
    price: str = "150.00",
    trade_date: str = "2025-07-28",
    fees: str | None = None,
    source_row: int = 2,
    id_: str | None = None,
) -> Transaction:
    return Transaction(
        id=id_ or f"fake_{ticker}_{action}_{source_row}",
        ticker=ticker,
        action=action,
        quantity=Decimal(quantity),
        price=Decimal(price),
        trade_date=date.fromisoformat(trade_date),
        fees=Decimal(fees) if fees is not None else None,
        source_row=source_row,
    )


# ---------------------------------------------------------------------------
# Net quantity
# ---------------------------------------------------------------------------

def test_single_buy_net_quantity() -> None:
    txns = [_txn(quantity="10")]
    holdings = aggregate(txns)
    assert len(holdings) == 1
    assert holdings[0].ticker == "AAPL"
    assert holdings[0].net_quantity == Decimal("10")


def test_buy_and_sell_net_quantity() -> None:
    txns = [
        _txn(quantity="10", trade_date="2025-07-28", source_row=2),
        _txn(action="sell", quantity="3", price="160.00", trade_date="2025-08-01", source_row=3),
    ]
    holdings = aggregate(txns)
    assert holdings[0].net_quantity == Decimal("7")


def test_full_sell_net_quantity_zero() -> None:
    txns = [
        _txn(quantity="10", trade_date="2025-07-28", source_row=2),
        _txn(action="sell", quantity="10", price="160.00", trade_date="2025-08-01", source_row=3),
    ]
    holdings = aggregate(txns)
    assert holdings[0].net_quantity == Decimal("0")
    assert holdings[0].status == "closed"


def test_multiple_buys_net_quantity() -> None:
    txns = [
        _txn(quantity="5", trade_date="2025-07-28", source_row=2),
        _txn(quantity="8", trade_date="2025-08-15", source_row=3),
    ]
    holdings = aggregate(txns)
    assert holdings[0].net_quantity == Decimal("13")


# ---------------------------------------------------------------------------
# Average cost (share-weighted, buys only)
# ---------------------------------------------------------------------------

def test_single_buy_avg_cost() -> None:
    txns = [_txn(quantity="10", price="150.00")]
    holdings = aggregate(txns)
    assert holdings[0].avg_cost == Decimal("150.00")


def test_two_buys_weighted_avg_cost() -> None:
    """Σ(qty × price) / Σ(qty), buys only."""
    txns = [
        # 5 @ $400 + 5 @ $415.20 → avg = (2000 + 2076) / 10 = 407.60
        _txn(quantity="5", price="400.00", trade_date="2025-08-15", source_row=2),
        _txn(quantity="5", price="415.20", trade_date="2025-10-09", source_row=3),
    ]
    holdings = aggregate(txns)
    expected = Decimal("2000.00") + Decimal("2076.00")  # 4076
    expected_avg = (expected / Decimal("10")).quantize(Decimal("0.01"))
    assert holdings[0].avg_cost == expected_avg


def test_sells_do_not_move_avg_cost() -> None:
    """Selling shares does not change the average cost of remaining shares."""
    txns = [
        _txn(quantity="10", price="150.00", trade_date="2025-07-28", source_row=2),
        _txn(action="sell", quantity="3", price="160.00", trade_date="2025-08-01", source_row=3),
    ]
    holdings = aggregate(txns)
    assert holdings[0].avg_cost == Decimal("150.00")


def test_avg_cost_stable_across_multiple_sells() -> None:
    """Multiple sells still leave avg cost at the buy price."""
    txns = [
        _txn(quantity="8", price="1025.32", trade_date="2025-09-20", source_row=2),
        _txn(action="sell", quantity="3", price="1100.00", trade_date="2025-10-05", source_row=3),
        _txn(action="sell", quantity="2", price="1050.00", trade_date="2025-10-10", source_row=4),
    ]
    holdings = aggregate(txns)
    assert holdings[0].avg_cost == Decimal("1025.32")


# ---------------------------------------------------------------------------
# Cost basis
# ---------------------------------------------------------------------------

def test_cost_basis_is_avg_cost_times_net_qty() -> None:
    txns = [
        _txn(quantity="10", price="150.00", trade_date="2025-07-28", source_row=2),
        _txn(action="sell", quantity="3", price="160.00", trade_date="2025-08-01", source_row=3),
    ]
    holdings = aggregate(txns)
    # net_qty=7, avg_cost=150.00 → cost_basis = 1050.00
    assert holdings[0].cost_basis == Decimal("1050.00")


# ---------------------------------------------------------------------------
# Realized P/L
# ---------------------------------------------------------------------------

def test_realized_pl_from_sell() -> None:
    """realized_pl = (sell_price - avg_cost) × qty − fees."""
    txns = [
        _txn(quantity="10", price="150.00", trade_date="2025-07-28", source_row=2),
        # sell 3 @ $160 with no fee → (160-150)*3 = +30
        _txn(action="sell", quantity="3", price="160.00", trade_date="2025-08-01", source_row=3),
    ]
    holdings = aggregate(txns)
    assert holdings[0].realized_pl == Decimal("30.00")


def test_realized_pl_deducts_fees() -> None:
    """Fees reduce realized P/L."""
    txns = [
        _txn(quantity="10", price="150.00", trade_date="2025-07-28", source_row=2),
        # sell 3 @ $160, fee $2.50 → (160-150)*3 - 2.50 = 27.50
        _txn(
            action="sell", quantity="3", price="160.00", fees="2.50",
            trade_date="2025-08-01", source_row=3,
        ),
    ]
    holdings = aggregate(txns)
    assert holdings[0].realized_pl == Decimal("27.50")


def test_realized_pl_is_zero_with_no_sells() -> None:
    txns = [_txn(quantity="10", price="150.00")]
    holdings = aggregate(txns)
    assert holdings[0].realized_pl == Decimal("0.00")


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def test_status_open_when_net_qty_positive() -> None:
    txns = [_txn(quantity="10")]
    assert aggregate(txns)[0].status == "open"


def test_status_closed_when_net_qty_zero() -> None:
    txns = [
        _txn(quantity="10", trade_date="2025-07-28", source_row=2),
        _txn(action="sell", quantity="10", price="160.00", trade_date="2025-08-01", source_row=3),
    ]
    assert aggregate(txns)[0].status == "closed"


def test_status_anomalous_when_oversold() -> None:
    """net_qty < 0 (sell > buy) → 'anomalous'; never treated as a short."""
    txns = [
        _txn(quantity="5", trade_date="2025-07-28", source_row=2),
        _txn(action="sell", quantity="8", price="160.00", trade_date="2025-08-01", source_row=3),
    ]
    holding = aggregate(txns)[0]
    assert holding.status == "anomalous"
    assert holding.net_quantity == Decimal("-3")


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

def test_earliest_buy_date() -> None:
    txns = [
        _txn(quantity="5", trade_date="2025-08-15", source_row=2),
        _txn(quantity="5", trade_date="2025-10-09", source_row=3),
    ]
    holding = aggregate(txns)[0]
    assert holding.earliest_buy_date == date(2025, 8, 15)


def test_most_recent_buy_date() -> None:
    txns = [
        _txn(quantity="5", trade_date="2025-08-15", source_row=2),
        _txn(quantity="5", trade_date="2025-10-09", source_row=3),
    ]
    holding = aggregate(txns)[0]
    assert holding.most_recent_buy_date == date(2025, 10, 9)


def test_dates_ignore_sell_dates() -> None:
    """earliest/most_recent are BUY dates only, not sell dates."""
    txns = [
        _txn(quantity="10", trade_date="2025-07-28", source_row=2),
        _txn(action="sell", quantity="3", price="160.00", trade_date="2025-01-01", source_row=3),
    ]
    holding = aggregate(txns)[0]
    assert holding.earliest_buy_date == date(2025, 7, 28)
    assert holding.most_recent_buy_date == date(2025, 7, 28)


# ---------------------------------------------------------------------------
# Multiple tickers
# ---------------------------------------------------------------------------

def test_multiple_tickers_each_aggregated_separately() -> None:
    txns = [
        _txn(ticker="AAPL", quantity="10", trade_date="2025-07-28", source_row=2),
        _txn(ticker="MSFT", quantity="5", price="400.00", trade_date="2025-08-15", source_row=3),
    ]
    holdings = aggregate(txns)
    assert len(holdings) == 2
    tickers = {h.ticker for h in holdings}
    assert tickers == {"AAPL", "MSFT"}


def test_tickers_isolated_sells_dont_cross() -> None:
    """Sell on AMZN does not reduce MSFT quantity."""
    txns = [
        _txn(ticker="MSFT", quantity="5", trade_date="2025-08-15", source_row=2),
        _txn(ticker="AMZN", quantity="8", price="1025.32", trade_date="2025-09-20", source_row=3),
        _txn(
            ticker="AMZN", action="sell", quantity="3", price="1100.00",
            trade_date="2025-10-05", source_row=4,
        ),
    ]
    holdings = aggregate(txns)
    h_msft = next(h for h in holdings if h.ticker == "MSFT")
    h_amzn = next(h for h in holdings if h.ticker == "AMZN")
    assert h_msft.net_quantity == Decimal("5")
    assert h_amzn.net_quantity == Decimal("5")


# ---------------------------------------------------------------------------
# Ordering: trades sorted by trade_date then source_row
# ---------------------------------------------------------------------------

def test_aggregation_order_by_date_then_source_row() -> None:
    """Rows are aggregated in trade_date ASC, source_row ASC order regardless
    of list input order."""
    txns = [
        _txn(quantity="5", price="415.20", trade_date="2025-10-09", source_row=3),  # later
        _txn(quantity="5", price="400.00", trade_date="2025-08-15", source_row=2),  # earlier
    ]
    holdings_1 = aggregate(txns)

    txns_reversed = list(reversed(txns))
    holdings_2 = aggregate(txns_reversed)

    assert holdings_1[0].avg_cost == holdings_2[0].avg_cost


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_determinism_same_input_same_output() -> None:
    txns = [
        _txn(quantity="10", price="150.00", trade_date="2025-07-28", source_row=2),
        _txn(action="sell", quantity="3", price="160.00", trade_date="2025-08-01", source_row=3),
    ]
    result_1 = aggregate(txns)
    result_2 = aggregate(txns)
    assert result_1[0].model_dump() == result_2[0].model_dump()


def test_empty_transactions_returns_empty_list() -> None:
    assert aggregate([]) == []
