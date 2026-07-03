"""Pure portfolio win/loss: FIFO realized P&L + unrealized mark-to-market.

No I/O. Deterministic: identical inputs -> identical output (SC-006). Informational
only — this module never changes any gate, rank, level, sizing, or backtest result
(Feature 016 US4, contracts/portfolio-pnl.md).

Realized P&L uses FIFO matching per ticker: each sell is matched against the oldest
open buy lots, producing one `RealizedTrade` round-trip per (buy-lot, sell) match so
each round-trip carries a single `buy_date`. Buy fees are allocated to the matched
shares proportionally; the sell fee is allocated across the shares it covers.
Over-sells beyond the available buy lots are ignored (never treated as a short),
mirroring the aggregation module's `anomalous` handling.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from ..models.portfolio import RealizedPnl, RealizedTrade, Transaction, money

if TYPE_CHECKING:
    from ..models.portfolio import PortfolioHolding


def _outcome(realized: Decimal) -> Literal["win", "loss", "flat"]:
    if realized > 0:
        return "win"
    if realized < 0:
        return "loss"
    return "flat"


class _Lot:
    """A mutable open buy lot consumed FIFO by later sells."""

    __slots__ = ("shares", "price", "fee_per_share", "buy_date")

    def __init__(self, txn: Transaction) -> None:
        self.shares: Decimal = txn.quantity
        self.price: Decimal = txn.price
        fee = txn.fees or Decimal("0")
        self.fee_per_share: Decimal = fee / txn.quantity if txn.quantity > 0 else Decimal("0")
        self.buy_date = txn.trade_date


def compute_realized_pnl(transactions: list[Transaction]) -> RealizedPnl:
    """Match sells against prior buys FIFO per ticker and summarise win/loss.

    Returns an all-empty `RealizedPnl` (realized_pnl None, counts 0, win_rate None)
    when there are no closed round-trips ⇒ byte-identical to today's buy-only
    portfolios.
    """
    by_ticker: dict[str, list[Transaction]] = {}
    for txn in transactions:
        by_ticker.setdefault(txn.ticker, []).append(txn)

    trades: list[RealizedTrade] = []
    for ticker, txns in by_ticker.items():
        txns_sorted = sorted(txns, key=lambda t: (t.trade_date, t.source_row))
        lots: list[_Lot] = []
        for txn in txns_sorted:
            if txn.action == "buy":
                lots.append(_Lot(txn))
                continue

            # Sell: consume the oldest lots first.
            remaining = txn.quantity
            sell_fee_per_share = (
                (txn.fees or Decimal("0")) / txn.quantity if txn.quantity > 0 else Decimal("0")
            )
            while remaining > 0 and lots:
                lot = lots[0]
                matched = min(lot.shares, remaining)
                proceeds = money(matched * txn.price)
                cost_basis = money(matched * lot.price)
                fees = money(matched * (lot.fee_per_share + sell_fee_per_share))
                realized = money(proceeds - cost_basis - fees)
                trades.append(
                    RealizedTrade(
                        ticker=ticker,
                        shares=matched,
                        buy_date=lot.buy_date,
                        sell_date=txn.trade_date,
                        proceeds=proceeds,
                        cost_basis=cost_basis,
                        fees=fees,
                        realized_pnl=realized,
                        outcome=_outcome(realized),
                        holding_days=(txn.trade_date - lot.buy_date).days,
                    )
                )
                lot.shares -= matched
                remaining -= matched
                if lot.shares <= 0:
                    lots.pop(0)
            # An over-sell with no remaining lots is dropped (never a short).

    if not trades:
        return RealizedPnl()

    total = money(sum((t.realized_pnl for t in trades), Decimal("0")))
    winning = sum(1 for t in trades if t.outcome == "win")
    closed = len(trades)
    return RealizedPnl(
        trades=trades,
        realized_pnl=total,
        closed_trade_count=closed,
        winning_trade_count=winning,
        win_rate=winning / closed if closed else None,
    )


def compute_unrealized_pnl(
    holdings: list[PortfolioHolding],
) -> tuple[Decimal | None, list[str]]:
    """Sum `unrealized_pl` across open holdings, flagging unpriceable ones.

    Uses the per-holding mark-to-market already computed on the portfolio page.
    Returns (None, notes) when no open holding is priceable; a missing quote on
    one holding never blocks the others (graceful degradation).
    """
    total = Decimal("0")
    notes: list[str] = []
    any_priced = False
    for holding in holdings:
        if holding.status != "open":
            continue
        if holding.unrealized_pl is not None:
            total += holding.unrealized_pl
            any_priced = True
        else:
            notes.append(f"{holding.ticker}: quote unavailable; unrealized P&L excluded")
    return (money(total) if any_priced else None), notes
