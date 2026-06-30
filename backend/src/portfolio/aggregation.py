"""Pure aggregation: transactions → average-cost holdings.

No I/O. Deterministic: identical inputs → identical output (SC-006).

Aggregation rules (data-model.md):
  - Group accepted transactions by ticker; order by trade_date then source_row.
  - avg_cost = Σ(buy qty × buy price) / Σ(buy qty)  (unaffected by sells).
  - realized_pl = Σ over sells of (sell_price − avg_cost_at_sale) × sell_qty − fees.
  - status: open (net_qty > 0) | closed (net_qty = 0) | anomalous (net_qty < 0).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from ..models.portfolio import Holding, Transaction, money


def aggregate(transactions: list[Transaction]) -> list[Holding]:
    """Aggregate accepted transactions into one Holding per ticker.

    Input order does not matter: rows are sorted by (trade_date, source_row)
    before aggregation.
    """
    if not transactions:
        return []

    # Group by ticker (preserving order for the sort below)
    by_ticker: dict[str, list[Transaction]] = {}
    for txn in transactions:
        by_ticker.setdefault(txn.ticker, []).append(txn)

    holdings: list[Holding] = []
    for ticker, txns in by_ticker.items():
        txns_sorted = sorted(txns, key=lambda t: (t.trade_date, t.source_row))

        total_buy_qty = Decimal("0")
        total_buy_cost = Decimal("0")  # Σ(qty × price) for buys
        total_sell_qty = Decimal("0")
        realized_pl = Decimal("0")
        buy_dates: list = []

        for txn in txns_sorted:
            if txn.action == "buy":
                total_buy_qty += txn.quantity
                total_buy_cost += txn.quantity * txn.price
                buy_dates.append(txn.trade_date)
            else:  # sell
                # Compute avg_cost at the time of this sell (running avg so far)
                avg_at_sale = (
                    total_buy_cost / total_buy_qty if total_buy_qty > 0 else Decimal("0")
                )
                fees = txn.fees or Decimal("0")
                realized_pl += (txn.price - avg_at_sale) * txn.quantity - fees
                total_sell_qty += txn.quantity

        avg_cost = money(total_buy_cost / total_buy_qty) if total_buy_qty > 0 else Decimal("0")
        net_quantity = total_buy_qty - total_sell_qty
        cost_basis = money(avg_cost * net_quantity)
        realized_pl = money(realized_pl)

        if net_quantity > 0:
            status: Literal["open", "closed", "anomalous"] = "open"
        elif net_quantity == 0:
            status = "closed"
        else:
            status = "anomalous"

        earliest_buy = min(buy_dates) if buy_dates else txns_sorted[0].trade_date
        most_recent_buy = max(buy_dates) if buy_dates else txns_sorted[-1].trade_date

        holdings.append(
            Holding(
                ticker=ticker,
                net_quantity=net_quantity,
                avg_cost=avg_cost,
                cost_basis=cost_basis,
                earliest_buy_date=earliest_buy,
                most_recent_buy_date=most_recent_buy,
                realized_pl=realized_pl,
                status=status,
            )
        )

    return holdings
