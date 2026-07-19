# Contract: Portfolio / Transactions page + PositionCard (frontend)

## Routes

| Route | Purpose | Contains |
|-------|---------|----------|
| `/portfolio` (restructured) | Review current positions | One `PositionCard` per open holding; `RealizedSummary`; link to `/transactions`. **No** transaction-entry/ledger UI (FR-002). |
| `/transactions` (new) | Record & audit | `ImportTransactions`, "Record a Transaction" form, full chronological ledger (incl. closed positions), realized-trades detail, per-holding Remove (FR-001, FR-010). |

Nav: add a **Transactions** link in `AppShell` between Portfolio and Settings.

## PositionCard (one per holding with `net_quantity > 0`)

Required sections (FR-004/005/006/007/008); every section degrades to an explicit statement, never
a blank/"Unknown":

1. **Header** — ticker + company, quantity + cost basis, status/stage badge (`PipelineStageBadge` +
   level status label).
2. **Price & P&L** — current price, unrealized P&L ($ and %).
3. **Levels** — current stop-loss + target (`current_condition`) and the trailing protective level;
   `"Levels unavailable"` when `insufficient_data`.
4. **News/events** — recent items via `EventsBadge`/`/events`, each with source + as-of; explicit
   "nothing new to report" when empty (FR-005).
5. **AI sentiment/narrative** — auto-loaded per card on page load (origin `"holding"`), lazy/background
   so it never blocks the shell (SC-005); shows the feature-014 template narrative when the spend cap
   is reached (FR-006). Shown as context; **not** an input to the instruction.
6. **Instruction** — `directive` verb (Hold/Trim/Sell) + rationale when `directive_enabled`; otherwise
   the neutral `status_label` (FR-008).

## RealizedSummary (on `/portfolio`)

From `totals` / `realized_trades`: count won, count lost, win rate %, total realized P&L. Empty state:
"No realized history yet" (FR-009). No raw ledger here (that lives on `/transactions`).

## Behavior

- Full-sell ⇒ card disappears immediately; ledger row persists on `/transactions` (US2/US3, SC-002/003).
- Repurchase of a fully-closed ticker ⇒ new card (FR-011).
- Every card + the summary carry `data_as_of`/staleness + disclaimer (FR-012) via the existing shell.

## Tests

- **Vitest**: card renders levels/status/instruction with a stub `/holdings`; each section's degrade
  path (no levels, no news, capped sentiment) renders its explicit statement, not a blank.
- **Playwright**:
  - `/transactions` shows the record/import/ledger/delete controls; `/portfolio` shows none of them.
  - Zero cards for a zero-net holding; card reappears after a repurchase.
  - **No-directive lint**: with `directive_enabled=false`, no "Buy/Sell/Hold/Trim/Recommended" verbs
    appear on `/portfolio`; with the carve-out on, Hold/Trim/Sell may appear on cards (and only there).
  - `data_as_of` + disclaimer present on `/portfolio`.
