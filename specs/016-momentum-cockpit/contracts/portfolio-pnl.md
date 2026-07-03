# Contract: portfolio win/loss (realized + unrealized P&L)

New pure module `backend/src/portfolio/pnl.py`; additive/optional response fields on the
holdings/totals payload. Informational only — never changes any gate, rank, level, sizing, or
backtest result. Neutral labels only (no directive verbs).

## Realized P&L — `compute_realized_pnl(transactions) -> RealizedPnl`

- **FIFO** matching of sells against prior buys, per ticker.
- Per round-trip `RealizedTrade`: `ticker`, `shares`, `buy_date`, `sell_date`, `proceeds`,
  `cost_basis`, `fees`, `realized_pnl = proceeds − cost_basis − fees`,
  `outcome ∈ {win, loss, flat}`, `holding_days`.
- Aggregates: per-ticker + portfolio `realized_pnl`, `closed_trade_count`,
  `winning_trade_count`, `win_rate`.
- Pure + deterministic; golden-fixture tested.

## Unrealized P&L (mark-to-market)

- Per open holding: `unrealized_pnl = market_value − cost_basis` using the quotes already
  fetched on the portfolio page (`PortfolioHolding.unrealized_pl` already exists).
- Missing quote ⇒ degrade gracefully: show cost basis, flag "quote unavailable" in
  `data_notes`, never block the rest.

## Surfaced fields (additive on `PortfolioTotals`)

`realized_pnl`, `unrealized_pnl`, `total_pnl`, `win_rate`, `closed_trade_count`,
`winning_trade_count` — all `None`/`0` when there are no closed lots ⇒ **byte-identical** to
today.

## Invariants (tests — `backend/tests/portfolio/test_pnl.py`)

1. **FIFO golden fixtures** — multi-lot buys with a partial sell match the oldest lots first;
   realized P&L, `outcome`, and `win_rate` equal hand-computed golden numbers.
2. **Fees** — realized P&L subtracts buy+sell fees on the matched shares.
3. **Win/loss/flat** — outcome classification is correct at, above, and below break-even.
4. **No closed lots ⇒ byte-identical** — a buy-only portfolio yields `realized_pnl = None`/`0`
   and an unchanged totals payload.
5. **Missing-quote degradation** — an unpriceable open holding contributes no unrealized figure
   and is flagged, without blocking others.
6. **Informational isolation** — P&L computation does not alter any sizing/level/board output
   (determinism + no-baseline-change assertion).
