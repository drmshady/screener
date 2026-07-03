"""T029: Golden-fixture tests for pure realized/unrealized P&L (portfolio/pnl.py).

Tests written FIRST (TDD): these should FAIL until pnl.py is implemented.

Covers (per contracts/portfolio-pnl.md):
  1. FIFO multi-lot + partial sell matches the oldest lots first; realized_pnl,
     outcome, and win_rate equal hand-computed golden numbers.
  2. Fees are subtracted (buy + sell) on the matched shares.
  3. win/loss/flat classification is correct at, above, and below break-even.
  4. Buy-only ⇒ realized_pnl None + zeroed counts (byte-identical totals).
  5. Missing-quote unrealized degradation is flagged, others unaffected.
  6. Informational isolation: pure + deterministic, input never mutated.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.src.models.portfolio import PortfolioHolding, Transaction
from backend.src.portfolio.pnl import compute_realized_pnl, compute_unrealized_pnl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _txn(
    *,
    ticker: str = "AAPL",
    action: str = "buy",
    quantity: str = "10",
    price: str = "100.00",
    trade_date: str = "2025-01-01",
    fees: str | None = None,
    source_row: int = 2,
) -> Transaction:
    return Transaction(
        id=f"fake_{ticker}_{action}_{trade_date}_{source_row}",
        ticker=ticker,
        action=action,
        quantity=Decimal(quantity),
        price=Decimal(price),
        trade_date=date.fromisoformat(trade_date),
        fees=Decimal(fees) if fees is not None else None,
        source_row=source_row,
    )


def _open_holding(
    ticker: str, *, unrealized_pl: str | None, status: str = "open"
) -> PortfolioHolding:
    return PortfolioHolding(
        ticker=ticker,
        net_quantity=Decimal("10"),
        avg_cost=Decimal("100.00"),
        cost_basis=Decimal("1000.00"),
        earliest_buy_date=date(2025, 1, 1),
        most_recent_buy_date=date(2025, 1, 1),
        realized_pl=Decimal("0.00"),
        status=status,  # type: ignore[arg-type]
        priceable=unrealized_pl is not None,
        unrealized_pl=Decimal(unrealized_pl) if unrealized_pl is not None else None,
    )


# ---------------------------------------------------------------------------
# 1. FIFO multi-lot + partial sell
# ---------------------------------------------------------------------------

def test_fifo_partial_sell_matches_oldest_lots_first() -> None:
    txns = [
        _txn(quantity="10", price="100.00", trade_date="2025-01-01", source_row=2),
        _txn(quantity="10", price="120.00", trade_date="2025-02-01", source_row=3),
        _txn(action="sell", quantity="15", price="150.00", trade_date="2025-03-01", source_row=4),
    ]
    result = compute_realized_pnl(txns)

    # A 15-share sell spanning two lots -> two FIFO round-trips.
    assert len(result.trades) == 2

    first, second = result.trades
    # Oldest lot (10 @ 100) fully consumed first.
    assert first.shares == Decimal("10")
    assert first.buy_date == date(2025, 1, 1)
    assert first.proceeds == Decimal("1500.00")  # 10 * 150
    assert first.cost_basis == Decimal("1000.00")  # 10 * 100
    assert first.realized_pnl == Decimal("500.00")
    assert first.outcome == "win"
    assert first.holding_days == (date(2025, 3, 1) - date(2025, 1, 1)).days

    # Second lot (5 of the 10 @ 120) matched next.
    assert second.shares == Decimal("5")
    assert second.buy_date == date(2025, 2, 1)
    assert second.proceeds == Decimal("750.00")  # 5 * 150
    assert second.cost_basis == Decimal("600.00")  # 5 * 120
    assert second.realized_pnl == Decimal("150.00")
    assert second.outcome == "win"

    assert result.realized_pnl == Decimal("650.00")
    assert result.closed_trade_count == 2
    assert result.winning_trade_count == 2
    assert result.win_rate == 1.0


def test_win_rate_mixes_wins_and_losses() -> None:
    txns = [
        _txn(quantity="10", price="100.00", trade_date="2025-01-01", source_row=2),
        _txn(action="sell", quantity="10", price="90.00", trade_date="2025-02-01", source_row=3),
        _txn(quantity="5", price="50.00", trade_date="2025-03-01", source_row=4),
        _txn(action="sell", quantity="5", price="70.00", trade_date="2025-04-01", source_row=5),
    ]
    result = compute_realized_pnl(txns)
    assert result.closed_trade_count == 2
    assert result.winning_trade_count == 1
    assert result.win_rate == 0.5
    outcomes = {t.outcome for t in result.trades}
    assert outcomes == {"win", "loss"}
    assert result.realized_pnl == Decimal("0.00")  # -100 + 100


# ---------------------------------------------------------------------------
# 2. Fees
# ---------------------------------------------------------------------------

def test_fees_subtracted_on_matched_shares() -> None:
    txns = [
        _txn(quantity="10", price="100.00", fees="5.00", trade_date="2025-01-01", source_row=2),
        _txn(action="sell", quantity="10", price="120.00", fees="3.00", trade_date="2025-02-01", source_row=3),
    ]
    result = compute_realized_pnl(txns)
    assert len(result.trades) == 1
    trade = result.trades[0]
    # proceeds 1200 - cost 1000 - fees (5 + 3) = 192
    assert trade.fees == Decimal("8.00")
    assert trade.realized_pnl == Decimal("192.00")
    assert trade.outcome == "win"


def test_partial_sell_allocates_buy_fees_proportionally() -> None:
    txns = [
        _txn(quantity="10", price="100.00", fees="10.00", trade_date="2025-01-01", source_row=2),
        _txn(action="sell", quantity="4", price="110.00", fees="2.00", trade_date="2025-02-01", source_row=3),
    ]
    result = compute_realized_pnl(txns)
    trade = result.trades[0]
    # matched 4/10 of a $10 buy fee -> 4.00; sell fee 2.00 -> fees 6.00
    # proceeds 440 - cost 400 - 6 = 34
    assert trade.fees == Decimal("6.00")
    assert trade.realized_pnl == Decimal("34.00")


# ---------------------------------------------------------------------------
# 3. Win / loss / flat classification
# ---------------------------------------------------------------------------

def test_outcome_flat_at_break_even() -> None:
    txns = [
        _txn(quantity="10", price="100.00", trade_date="2025-01-01", source_row=2),
        _txn(action="sell", quantity="10", price="100.00", trade_date="2025-02-01", source_row=3),
    ]
    result = compute_realized_pnl(txns)
    assert result.trades[0].outcome == "flat"
    assert result.trades[0].realized_pnl == Decimal("0.00")
    assert result.winning_trade_count == 0
    assert result.win_rate == 0.0


def test_outcome_loss_below_break_even() -> None:
    txns = [
        _txn(quantity="10", price="100.00", trade_date="2025-01-01", source_row=2),
        _txn(action="sell", quantity="10", price="80.00", trade_date="2025-02-01", source_row=3),
    ]
    result = compute_realized_pnl(txns)
    assert result.trades[0].outcome == "loss"
    assert result.trades[0].realized_pnl == Decimal("-200.00")


# ---------------------------------------------------------------------------
# 4. Buy-only ⇒ byte-identical (no realized figures)
# ---------------------------------------------------------------------------

def test_buy_only_has_no_realized_pnl() -> None:
    txns = [
        _txn(quantity="10", price="100.00", trade_date="2025-01-01", source_row=2),
        _txn(quantity="5", price="120.00", trade_date="2025-02-01", source_row=3),
    ]
    result = compute_realized_pnl(txns)
    assert result.trades == []
    assert result.realized_pnl is None
    assert result.closed_trade_count == 0
    assert result.winning_trade_count == 0
    assert result.win_rate is None


def test_empty_transactions_has_no_realized_pnl() -> None:
    result = compute_realized_pnl([])
    assert result.trades == []
    assert result.realized_pnl is None
    assert result.win_rate is None


# ---------------------------------------------------------------------------
# 5. Unrealized mark-to-market + missing-quote degradation
# ---------------------------------------------------------------------------

def test_unrealized_sums_priceable_open_holdings() -> None:
    holdings = [
        _open_holding("AAA", unrealized_pl="150.00"),
        _open_holding("BBB", unrealized_pl="-40.00"),
    ]
    total, notes = compute_unrealized_pnl(holdings)
    assert total == Decimal("110.00")
    assert notes == []


def test_unrealized_flags_missing_quote_without_blocking_others() -> None:
    holdings = [
        _open_holding("AAA", unrealized_pl="150.00"),
        _open_holding("BBB", unrealized_pl=None),  # unpriceable
    ]
    total, notes = compute_unrealized_pnl(holdings)
    assert total == Decimal("150.00")  # AAA still counted
    assert len(notes) == 1
    assert "BBB" in notes[0]


def test_unrealized_none_when_nothing_priceable() -> None:
    holdings = [_open_holding("AAA", unrealized_pl=None)]
    total, notes = compute_unrealized_pnl(holdings)
    assert total is None
    assert len(notes) == 1


def test_unrealized_ignores_closed_holdings() -> None:
    holdings = [
        _open_holding("AAA", unrealized_pl="150.00"),
        _open_holding("BBB", unrealized_pl=None, status="closed"),
    ]
    total, notes = compute_unrealized_pnl(holdings)
    assert total == Decimal("150.00")
    assert notes == []  # closed holding is not flagged


# ---------------------------------------------------------------------------
# 6. Informational isolation: pure, deterministic, non-mutating
# ---------------------------------------------------------------------------

def test_determinism_and_input_not_mutated() -> None:
    txns = [
        _txn(quantity="10", price="100.00", trade_date="2025-01-01", source_row=2),
        _txn(action="sell", quantity="4", price="150.00", trade_date="2025-03-01", source_row=3),
    ]
    before = [t.model_dump() for t in txns]
    result_1 = compute_realized_pnl(txns)
    result_2 = compute_realized_pnl(txns)
    assert result_1.model_dump() == result_2.model_dump()
    # Input list/objects unchanged.
    assert [t.model_dump() for t in txns] == before
