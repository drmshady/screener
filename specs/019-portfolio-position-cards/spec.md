# Feature Specification: Portfolio Position Cards & Transaction Separation

**Feature Branch**: `019-portfolio-position-cards`
**Created**: 2026-07-17
**Status**: Draft
**Input**: User description: "i want to seperate transections from protoiflio to be in seperate pages closed transectin after seeling all atocks will have 0 stocks it shouldnt appear in protofolio i want summary of realized winng and losing stocks in portofloio iwant each position has card with info about stocks and current status and stoploss and target posytion news and event affect it and direct instuction of hold or trin or sell the app for personal use so direct instuction is not problem"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Position card with status, levels, news, and a call (Priority: P1)

The owner opens the Portfolio page and, for every stock they currently hold, sees one card that
tells them everything they need without leaving the page: what the stock is doing, its
stop-loss and target, any recent news or events affecting it, and a direct call — Hold, Trim, or
Sell.

**Why this priority**: This is the core value of the request — turning a spreadsheet-style
holdings table into an at-a-glance decision surface. Everything else in this feature exists to
support this view.

**Independent Test**: With at least one open holding, load the Portfolio page and verify a card
renders for that ticker showing status, stop-loss, target, recent news/events (or an explicit
"nothing new" statement), and one of Hold/Trim/Sell. Testable on its own, without the
transactions-page split or the realized summary.

**Acceptance Scenarios**:

1. **Given** an open holding with a computed stop-loss and target, **When** the owner views the
   Portfolio page, **Then** its card shows both levels alongside the current market price and
   unrealized P&L.
2. **Given** a holding whose stop-loss has been breached, **When** the owner views its card,
   **Then** the card's status reflects the breach and its instruction reads "Sell".
3. **Given** a holding approaching its stop or showing a deteriorating risk signal (per existing
   risk/heat data), **When** the owner views its card, **Then** the instruction reads "Trim".
4. **Given** a healthy holding tracking toward its target with no breach, **When** the owner
   views its card, **Then** the instruction reads "Hold".
5. **Given** a holding with no notable recent news or events, **When** the owner views its card,
   **Then** the card plainly states there is nothing new to report — never a blank or missing
   section.

---

### User Story 2 - Transactions on their own page (Priority: P1)

The owner moves all buy/sell recording, import, and the transaction ledger off the Portfolio
page onto a dedicated Transactions page, so the Portfolio page is reserved for reviewing current
positions.

**Why this priority**: This is the structural change the rest of the feature depends on — the
Portfolio page can only become a clean card view once transaction bookkeeping is moved out of
it.

**Independent Test**: Navigate to the new Transactions page and confirm it shows the complete
buy/sell ledger with existing add/import/delete controls; confirm the Portfolio page no longer
contains any transaction-entry UI. Testable independently of the card redesign.

**Acceptance Scenarios**:

1. **Given** the owner is on the Portfolio page, **When** they look for transaction entry or
   ledger controls, **Then** none are present — only a link to the Transactions page.
2. **Given** the owner navigates to the Transactions page, **When** it loads, **Then** it shows
   the full chronological transaction ledger (including transactions for now-closed positions)
   with the existing add, Sheet-import, and delete controls.
3. **Given** the owner adds or deletes a transaction on the Transactions page, **When** they
   return to the Portfolio page, **Then** holdings and cards reflect the change immediately.

---

### User Story 3 - Closed positions leave the Portfolio page (Priority: P2)

Once the owner sells all shares of a holding, it drops off the Portfolio page entirely — it no
longer clutters the view of current, actionable positions — while its transaction history stays
fully visible on the Transactions page.

**Why this priority**: Directly requested and depends on User Story 2's page split, but is a
smaller, independently verifiable behavior on top of it.

**Independent Test**: Sell 100% of a holding's shares and confirm its card disappears from the
Portfolio page, while its buy/sell rows remain on the Transactions page and it's reflected in the
realized summary (User Story 4).

**Acceptance Scenarios**:

1. **Given** a holding reaches zero net shares, **When** the owner views the Portfolio page,
   **Then** no card is shown for that ticker.
2. **Given** that same holding, **When** the owner views the Transactions page, **Then** its
   buy/sell rows remain fully visible and auditable.
3. **Given** the owner later repurchases a previously fully-closed ticker, **When** they view
   the Portfolio page, **Then** a new open-position card appears for it.

---

### User Story 4 - Realized win/loss summary (Priority: P2)

The owner sees, on the Portfolio page, a scoreboard of closed positions — how many were winners
versus losers, the win rate, and total realized profit/loss — without having to reconstruct it
from the raw transaction ledger.

**Why this priority**: Explicitly requested; gives the owner a running scorecard, but is
additive to (not a prerequisite for) the position cards and page split.

**Independent Test**: With at least one fully closed position, view the summary and verify
winner/loser counts, win rate, and total realized P&L are shown, and are mathematically
consistent with the underlying closed trades.

**Acceptance Scenarios**:

1. **Given** closed positions with mixed outcomes, **When** the owner views the Portfolio page,
   **Then** the summary shows count won, count lost, win rate %, and total realized P&L.
2. **Given** zero closed positions so far, **When** the owner views the summary, **Then** it
   plainly states there is no realized history yet — not an error or a blank section.

---

### Edge Cases

- A holding with insufficient price history to compute a stop-loss/target must still get a card;
  the card states the levels are unavailable rather than hiding the position or failing to load.
- A partial sell that reduces quantity but doesn't reach zero keeps the position — and its card —
  on the Portfolio page.
- Multiple buy lots of the same ticker across different dates are represented by a single,
  consolidated card (existing average-cost aggregation), not one card per lot.
- If fetching news/events for a ticker fails or returns nothing, the card degrades gracefully
  with an explicit "no data" message rather than a bare/blank/"Unknown" state.
- If the shared AI sentiment/narrative spend cap is already reached when the Portfolio page
  loads, cards still show the deterministic source-only template narrative (per feature 014's
  existing degrade behavior) rather than an error or a missing section.
- A ticker sold completely and repurchased later (or same day) is governed by existing
  aggregation rules; the card reflects the final net position.
- On a hosted deployment where the single-owner directive carve-out is not satisfied, cards fall
  back to neutral, non-directive status language instead of a Hold/Trim/Sell verb (see FR-008).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a Transactions page, separate from the Portfolio page, that
  lists the complete chronological buy/sell transaction ledger and hosts all transaction entry,
  Sheet-import, and delete controls currently on the Portfolio page.
- **FR-002**: The Portfolio page MUST NOT contain transaction-entry/ledger UI once the
  Transactions page ships; it MUST link to the Transactions page.
- **FR-003**: The Portfolio page MUST show one card per ticker with a non-zero net open
  position. Holdings with zero net shares MUST NOT appear as cards on the Portfolio page.
- **FR-004**: Each position card MUST show, at minimum: ticker/company, quantity and cost basis,
  current price and unrealized P&L, a status/stage indicator, the current stop-loss level, and
  the current target (take-profit) level.
- **FR-005**: Each position card MUST show recent news/events relevant to that ticker, each with
  a source and as-of date; if none exist, the card MUST state that plainly rather than leaving
  the section blank.
- **FR-006**: Each card MUST automatically fetch and display the AI sentiment/narrative report
  (feature 014's existing pipeline) for its ticker on Portfolio page load, for every open
  position — not gated behind a per-card click. This reuses feature 014's existing ~$5/month
  spend cap and its deterministic-template degrade behavior once that cap is reached, so a
  portfolio with many holdings degrades to source-only template narratives rather than exceeding
  budget or failing.
- **FR-007**: The hold/trim/sell instruction on each card MUST be derived deterministically,
  purely from existing rule-based signals — stop-loss/target status, portfolio heat, and
  lifecycle stage — with the same same-inputs-same-output determinism guarantee as the rest of
  the app. It MUST NOT factor in the AI sentiment/narrative score; that score is shown
  separately on the card (FR-006) as supporting context, not as an input to the instruction.
- **FR-008**: When the single-owner directive carve-out (the same mechanism already established
  for the daily brief feature — personal-use flag on, owner secret set, not multi-user) is not
  satisfied, the card instruction MUST fall back to neutral, non-directive status language
  instead of Hold/Trim/Sell — consistent with the constitution's hosted-mode-forced-off default.
- **FR-009**: The Portfolio page MUST show a realized win/loss summary: count and percentage of
  winning vs. losing closed positions and total realized P&L, computed from the app's existing
  realized-P&L logic. It MUST state plainly when there is no closed-position history yet.
- **FR-010**: All transaction records — including for fully closed positions — MUST remain
  permanently visible and auditable on the Transactions page regardless of a position's card
  visibility on the Portfolio page.
- **FR-011**: A ticker with zero net shares that is subsequently repurchased MUST reappear as a
  new open-position card on the Portfolio page.
- **FR-012**: Every position card and the realized summary MUST carry the app's existing
  `data_as_of`/staleness and disclaimer treatment, consistent with the rest of the app.
- **FR-013**: This feature MUST NOT introduce or alter any screening rule, gate threshold,
  indicator, sizing model, or backtest baseline — it is presentation/synthesis over existing
  outputs only.

### Key Entities

- **Position Card**: A synthesized, per-ticker view combining an open holding's status, price
  levels, recent news/events, and instruction. Not a new stored entity — assembled from existing
  holdings, levels, and news/sentiment data.
- **Transaction Ledger**: The existing append-only buy/sell record set, relocated to its own
  page; unchanged in structure.
- **Realized Trade Summary**: Aggregated win/loss counts, win rate, and realized P&L across
  closed positions — derived from existing realized-P&L computation, not newly stored.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The owner can decide whether to hold, trim, or sell every open position without
  leaving the Portfolio page or consulting an external tool.
- **SC-002**: The Portfolio page shows zero cards for positions with zero net shares in 100% of
  cases immediately after a full-sell transaction is recorded.
- **SC-003**: The owner can reach the full transaction history (including closed positions)
  within one navigation step from the Portfolio page.
- **SC-004**: Realized win/loss summary figures match a manual reconciliation of the transaction
  ledger for the same account state, every time.
- **SC-005**: For a portfolio of a typical size the owner actually holds, the Portfolio page
  shell (cards, levels, status, instruction) loads and is usable without waiting on
  sentiment/narrative fetches to complete — those load per-card in the background so a slow or
  budget-capped narrative never blocks the rest of the page.

## Assumptions

- The realized win/loss summary lives on the Portfolio page (as the request states), even though
  the raw transaction ledger moves to its own page — the summary is a synthesis view, not raw
  transaction data.
- "Current status" on a card reuses the app's existing lifecycle/stage indicator (the
  watch → ready → staged → owned → managing → exited badge introduced for the pipeline cockpit)
  plus its existing risk/breach status, rather than inventing a new status taxonomy.
- Position cards cover every open holding regardless of origin — Sheet-imported or recorded
  in-app — since both already flow through the same holdings aggregation today.
- "Sell" is used as the exit-side instruction verb shown to the owner (matching the user's own
  wording), even though some existing internal/export copy uses "Exit" for the same concept;
  both refer to the same closing action.
- The Transactions page reuses the existing transaction-ledger UI/controls (add, Sheet-import,
  delete) essentially as-is, relocated rather than redesigned; this feature does not change how
  transactions are entered or validated.
- No new backend data is introduced for "closed position tracking" beyond what
  `compute_realized_pnl` already produces — the summary and the disappearance of closed cards
  are both presentation-layer consequences of existing net-quantity and realized-P&L logic.
