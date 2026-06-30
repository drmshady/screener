# Feature Specification: Portfolio Import, Purchase-Anchored Levels & Risk-Aware Sizing

**Feature Branch**: `013-portfolio-import-sizing`  
**Created**: 2026-06-30  
**Status**: Draft  
**Input**: User description: "1. i want to import stocks from google sheets directly from portfolio i add transaction 2. i want stocks in portfolio to show stop loss and profit take based on date of purchase 3. sizing should take in consideration risk management"

## Overview

Today the owner tracks screened candidates and a browser-local portfolio/watchlist, with
stop-loss / take-profit levels and position sizing computed for *hypothetical* new entries
at the latest price. This feature turns the portfolio into a record of **what the owner
actually bought**: the owner maintains a Google Sheet of buy/sell transactions, imports it
into the screener, and for each resulting holding sees stop-loss and take-profit levels
**anchored to the real purchase price and date**, plus a risk-management view of how each
position is sized relative to the owner's capital and per-trade risk budget.

This is a **personal-use, single-owner** feature consistent with the existing screener
(no advice/directive language, every data-bearing response carries `data_as_of` +
`disclaimer`, deterministic for a given snapshot). It adds portfolio bookkeeping and
presentation on top of the already-existing risk-sizing and level-derivation logic — it
does **not** change any strategy rule, default, citation, indicator, or backtest baseline.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import transactions from a Google Sheet (Priority: P1)

The owner keeps a Google Sheet where each row is a transaction (ticker, action buy/sell,
quantity, price per share, trade date, optional fees/notes). From the screener's portfolio
screen, the owner connects/points to that sheet and imports it. The screener reads the
transaction rows, validates them, aggregates them into current holdings (net quantity and
average cost per ticker/lot), and displays the resulting portfolio. Re-importing after the
owner adds new transactions updates the portfolio without creating duplicates.

**Why this priority**: Nothing else in the feature can happen until the owner's real
positions — with their true purchase prices and dates — are in the system. It is the
foundation and is independently valuable on its own (a correct, low-effort portfolio
ledger replacing manual entry).

**Independent Test**: Provide a sample sheet of transactions, run the import, and confirm
the portfolio shows the correct per-ticker net quantity, average cost, and earliest/most-
recent purchase dates, with malformed rows reported rather than silently dropped.

**Acceptance Scenarios**:

1. **Given** a Google Sheet with valid buy transactions for 5 tickers, **When** the owner
   imports it, **Then** the portfolio shows 5 holdings each with the summed quantity and
   share-weighted average cost from the sheet.
2. **Given** a sheet containing both buys and a later partial sell of one ticker, **When**
   imported, **Then** that holding's net quantity reflects buys minus sells and the cost
   basis is computed consistently (documented method), and a fully-sold ticker shows zero/closed.
3. **Given** a sheet row with a missing price or unparseable date, **When** imported,
   **Then** the row is flagged in an import summary (row reference + reason) and the rest of
   the import still succeeds.
4. **Given** a prior import, **When** the owner adds new rows to the sheet and re-imports,
   **Then** previously imported transactions are not double-counted and only the net change
   is reflected.
5. **Given** a successful import, **When** the portfolio is shown, **Then** the response
   carries `data_as_of` and `disclaimer` and contains zero directive trading language.

---

### User Story 2 - Purchase-anchored stop-loss & take-profit per holding (Priority: P2)

For every open holding, the owner sees a stop-loss level and a take-profit level computed
from the **actual purchase price and purchase date** of that position (not a hypothetical
fresh entry at today's price). Each holding also shows current price, distance to each
level, and unrealized P/L, so the owner can see at a glance which positions are near a stop
or target and how the original plan has aged.

**Why this priority**: This is the core "what do I do with what I already own" value, but it
depends on US1 having established real holdings with purchase prices and dates.

**Independent Test**: With imported holdings present, verify each holding displays a
stop-loss and take-profit derived from its recorded purchase price/date, that the levels are
deterministic for a given snapshot, and that current-price distance and unrealized P/L are
correct.

**Acceptance Scenarios**:

1. **Given** a holding bought at a known price on a known date, **When** the portfolio is
   shown, **Then** it displays both the original-plan stop-loss/take-profit (fixed from the
   purchase price/date) and the current-condition stop-loss/take-profit (recomputed on the
   latest snapshot), each labeled, using the existing bounded (volatility-/horizon-aware)
   level logic, with a plain-language rationale and no directive language.
2. **Given** a holding whose current price has fallen below its stop-loss level, **When**
   shown, **Then** it is clearly flagged as breached (informational, not an instruction).
3. **Given** a holding with insufficient price history to derive volatility-based levels,
   **When** shown, **Then** a documented fallback level and a neutral "insufficient data"
   rationale are shown instead of an error.
4. **Given** the same portfolio and the same data snapshot, **When** the levels are computed
   twice, **Then** the results are byte-identical (determinism preserved).

---

### User Story 3 - Risk-management-aware sizing view for holdings (Priority: P3)

For each holding and for the portfolio as a whole, the owner sees a risk-management view: a
recommended position size derived from the owner's capital and per-trade risk budget (the
existing risk-per-trade backbone, sized to that holding's stop-loss), compared against the
**actual** size held, plus the dollar/percentage of capital currently at risk to the stop.
Over-sized positions (actual risk exceeding the per-trade budget or position caps) and total
portfolio risk are flagged so the owner can judge concentration and risk exposure.

**Why this priority**: It refines decision support on top of real holdings and their stops;
valuable but the portfolio and its stops (US1/US2) must exist first.

**Independent Test**: With holdings and stops present and a configured capital base, verify
each holding shows recommended vs actual size and capital-at-risk, and that positions
exceeding the per-trade risk budget or caps are flagged, using the existing sizing rules.

**Acceptance Scenarios**:

1. **Given** a configured capital base and per-trade risk fraction, **When** the portfolio is
   shown, **Then** each holding shows a recommended size (risk-per-trade sized to its stop,
   bounded by the existing caps) alongside the actual quantity held.
2. **Given** a holding whose actual capital-at-risk exceeds the per-trade risk budget, **When**
   shown, **Then** it is flagged as over-risk with the binding constraint named.
3. **Given** missing modulator input (e.g., insufficient data for a conviction signal),
   **When** sizing is shown, **Then** sizing fails open to the bounded baseline rather than
   erroring, consistent with the existing sizing behavior.
4. **Given** all holdings, **When** the portfolio is shown, **Then** total capital-at-risk and
   total invested are summarized for the whole portfolio.

---

### User Story 4 - Watch a screener candidate until it is entry-ready (Priority: P4)

From a screen result, the owner saves a candidate to the watchlist. The watchlist then actively
re-checks each saved ticker's **live entry-timing state** against the latest snapshot, so the
owner can watch a name that is not yet entry-ready until it becomes entry-ready — shown as
informational status, never an instruction. This reuses the existing watchlist and the
feature-012 entry-timing classifier; it adds no strategy logic.

**Why this priority**: It is a convenience/monitoring layer that is independent of the
import/holdings work (US1–US3) and reuses existing pieces, so it is valuable but lowest-risk to
defer or slot in opportunistically.

**Independent Test**: Save a candidate currently classified `not_entry_ready`; open the
watchlist; refresh; confirm it shows a "watching — not yet ready" state with the top failing
reasons; when the snapshot makes it entry-ready, the watchlist highlights it as entry-ready
(descriptive). Re-checking twice on the same snapshot is byte-identical.

**Acceptance Scenarios**:

1. **Given** a saved candidate that is not entry-ready, **When** the owner opens the watchlist
   and refreshes, **Then** each open entry shows its current entry-timing state (entry-ready /
   watching — not yet ready / undetermined) with the top failing reasons and the snapshot's
   `data_as_of`, using only descriptive language.
2. **Given** a watched ticker whose latest snapshot makes it entry-ready, **When** the watchlist
   is refreshed, **Then** it is highlighted as entry-ready (informational status, not an
   instruction) and surfaced ahead of not-ready entries.
3. **Given** the same snapshot, **When** entry-readiness is re-checked twice, **Then** the
   results are byte-identical (determinism preserved).

---

### Edge Cases

- **Duplicate / re-imported transactions**: identical rows on re-import must not double-count;
  the system needs a stable way to recognize already-seen transactions.
- **Sells exceeding holdings / short positions**: a net-negative quantity (more sold than
  bought in the sheet) is surfaced as a data warning rather than producing a nonsensical holding.
- **Ticker not recognized** by the screener's universe (delisted, non-US, typo, **or an ETF
  such as SPUS/SLV/IBIT/GLD** outside the US-common-equity universe): the holding is shown but
  clearly marked as not priceable / out of coverage, without breaking the import. For this
  owner ETFs are common, so the out-of-coverage path is a normal case, not a rare edge.
- **Non-buy/sell rows** (e.g. `Div` cash dividends; the owner's sheet contains Buy/Sell/Div
  only): recognized but **rejected as unsupported** in the import summary with a reason — never
  silently dropped, never added to share count; cash dividends are not tracked in v1.
- **Descriptive headers & formatting**: the sheet uses headers like `Date`, `Type`, `Stock`,
  `Transacted Units`, `Transacted Price (per unit)`; money cells carry `$` and thousands
  commas; slash dates are **day-first** (`28/7/2025`). The importer maps headers via aliases,
  strips currency/commas, and parses dates day-first deterministically.
- **Multiple lots of the same ticker** bought on different dates: define whether levels/P-L are
  shown per-lot or per aggregated holding (and which purchase date anchors the levels).
- **Currency / non-USD prices** in the sheet: out of scope for v1 (assume USD); flag obviously
  inconsistent values.
- **Empty sheet, wrong columns, or no access** to the sheet: a clear, non-crashing error that
  tells the owner what to fix.
- **Stale current price** for a held ticker: distance-to-level and P/L reflect the snapshot's
  `data_as_of`, surfaced honestly.

## Requirements *(mandatory)*

### Functional Requirements

#### Import (US1)

- **FR-001**: System MUST let the owner import a portfolio of transactions by reading the
  owner's Google Sheet directly via the owner's authorized Google account (Sheets read
  access), addressing the sheet by its identifier and re-reading it live on each import.
  Owner authorization/credentials are runtime-only and MUST never be written to any artifact
  file (consistent with the app's API-key handling).
- **FR-002**: System MUST accept transaction rows with at least: ticker, action (buy/sell),
  quantity, price per share, and trade date; and MUST tolerate optional columns (fees, notes)
  without failing.
- **FR-003**: System MUST validate each row and produce an import summary listing accepted
  rows and rejected rows (with a row reference and human-readable reason), never silently
  dropping data.
- **FR-004**: System MUST aggregate transactions into current holdings per ticker (net
  quantity and a documented cost-basis method), incorporating buys and sells.
- **FR-005**: System MUST make re-import idempotent: re-importing a sheet that contains
  previously imported transactions plus new ones MUST NOT double-count the previously imported
  transactions.
- **FR-006**: System MUST record, for each holding, the purchase price(s) and purchase date(s)
  needed to anchor levels in US2.
- **FR-007**: System MUST persist the owner's portfolio between sessions (single owner) and
  allow clearing/replacing it.

#### Purchase-anchored levels (US2)

- **FR-008**: System MUST compute, for each open holding, a stop-loss and a take-profit level
  anchored to that holding's actual purchase price and purchase date, reusing the existing
  bounded (volatility-/horizon-aware) level-derivation logic.
- **FR-009**: System MUST show, per holding, BOTH level bases side by side: (a) the
  **original-plan** stop-loss/take-profit computed once from the purchase price and the
  volatility as of the purchase date and held static, and (b) the **current-condition**
  stop-loss/take-profit anchored to the purchase price/date but recomputed on the latest
  snapshot and elapsed holding period. Each is clearly labeled.
- **FR-010**: System MUST display, per holding, current price, distance to stop-loss, distance
  to take-profit, and unrealized P/L (absolute and percent).
- **FR-011**: System MUST flag holdings whose current price has breached the stop-loss or
  reached the take-profit, as informational status only (no directive language).
- **FR-012**: System MUST provide a documented fallback level and neutral rationale when price
  history is insufficient to derive volatility-based levels, instead of erroring.
- **FR-013**: Level computation MUST be deterministic for a given data snapshot and portfolio.

#### Risk-aware sizing (US3)

- **FR-014**: System MUST show, per holding, a recommended position size derived from the
  owner's capital base and per-trade risk budget sized to that holding's stop-loss, reusing the
  existing risk-per-trade sizing backbone and its caps.
- **FR-015**: System MUST show, per holding, the actual quantity/value held and the
  dollar and percent of capital currently at risk to the stop-loss.
- **FR-016**: System MUST flag holdings whose actual capital-at-risk exceeds the per-trade risk
  budget or position caps, naming the binding constraint.
- **FR-017**: System MUST summarize portfolio-level totals: total invested and total
  capital-at-risk.
- **FR-018**: Sizing MUST fail open to the bounded baseline when a conviction/modulator input
  is missing, consistent with existing sizing behavior.

#### Watch until entry-ready (US4)

- **FR-024**: System MUST let the owner save a screen candidate to the watchlist (existing
  capability) and, on the watchlist, re-check each saved ticker's **live entry-timing state**
  against the latest snapshot, reusing the existing feature-012 entry-timing classifier — adding
  no new strategy logic.
- **FR-025**: System MUST present each watched ticker's entry-timing state (entry-ready /
  not-yet-ready / undetermined) with the top failing reasons and the snapshot's `data_as_of`, as
  informational status only (no directive language), and surface entry-ready names ahead of
  not-ready ones.
- **FR-026**: Entry-readiness re-checks MUST be deterministic for a given snapshot and MUST NOT
  change any strategy rule, default, citation, indicator, or backtest baseline.

#### Cross-cutting (constitution)

- **FR-019**: Every portfolio response that exposes user-visible data MUST carry `data_as_of`
  and `disclaimer`.
- **FR-020**: All portfolio surfaces MUST contain zero directive trading language ("Buy",
  "Sell", "Recommended", "Strong buy"); status and sizing are descriptive/informational only.
- **FR-021**: The feature MUST NOT change any strategy rule, default, citation, indicator, or
  backtest baseline; it reuses existing level and sizing logic.
- **FR-022**: When the screener runs in hosted mode, the personal-use directive MUST remain
  forced OFF and non-waivable, unchanged by this feature.
- **FR-023**: Tickers not in the screener's coverage MUST be shown as out-of-coverage / not
  priceable rather than breaking the portfolio view.

### Key Entities *(include if feature involves data)*

- **Transaction**: one buy or sell as recorded in the owner's sheet — ticker, action,
  quantity, price per share, trade date, optional fees/notes, and a stable identity for
  idempotent re-import.
- **Holding (Position)**: the owner's current net position in one ticker — net quantity,
  cost basis / average cost, anchoring purchase date(s), derived stop-loss & take-profit,
  current price, unrealized P/L, and recommended-vs-actual size with capital-at-risk.
- **Portfolio**: the collection of holdings for the single owner, plus the capital base and
  per-trade risk configuration used for sizing, and portfolio-level risk/invested totals.
- **Import Result**: the outcome of one import run — accepted transactions, rejected rows with
  reasons, and a summary the owner can act on.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The owner can import a sheet of transactions and see the resulting portfolio in
  under 2 minutes, without manually re-typing any position.
- **SC-002**: 100% of rejected/malformed transaction rows are reported with a row reference and
  reason; 0% are silently dropped.
- **SC-003**: Re-importing a sheet after adding N new transactions changes the portfolio by
  exactly those N transactions (0 double-counting).
- **SC-004**: For every open holding, both the original-plan and current-condition stop-loss /
  take-profit (each anchored to its real purchase price/date) are shown, with current-price
  distance and unrealized P/L correct against the snapshot.
- **SC-005**: Every holding shows recommended vs actual size and capital-at-risk, and 100% of
  positions exceeding the per-trade risk budget or caps are flagged.
- **SC-006**: Identical snapshot + identical portfolio produce byte-identical levels and sizing
  outputs across repeated runs (determinism).
- **SC-007**: 100% of portfolio responses include `data_as_of` + `disclaimer`, and automated
  copy linting finds zero directive trading terms on portfolio surfaces.
- **SC-008**: A saved watchlist candidate shows its live entry-timing state on demand; when the
  snapshot makes it entry-ready it is highlighted as such, and re-checks on the same snapshot are
  byte-identical (determinism), with zero directive language on the watchlist surface.

## Assumptions

- **Single owner, personal use**: the portfolio is for one owner on the existing single-user
  app; no multi-user sharing, no redistribution.
- **USD only for v1**: transaction prices and portfolio values are assumed USD; non-USD rows
  are out of scope and flagged if obviously inconsistent.
- **Reuse, not redesign**: stop-loss/take-profit derivation reuses feature 011 US2 bounded
  level logic and sizing reuses feature 011 US3 risk-per-trade backbone; this feature adds
  portfolio bookkeeping, purchase-date anchoring, and presentation only.
- **Capital base & per-trade risk** come from the existing capital-aware sizing configuration;
  if unset, sizing shows recommendations once the owner sets a capital base.
- **Coverage limited to the screener's existing universe/snapshot** for current prices and
  volatility; out-of-coverage tickers are shown but not priceable.
- **Cost-basis method**: average-cost per ticker is assumed as the default aggregation for net
  holdings unless a per-lot view is chosen during planning.
- **Sheet schema**: the owner's sheet uses recognizable column headers for the required fields;
  a documented expected column layout is provided.
- **Determinism & honesty obligations** (data_as_of/disclaimer, no directive language, hosted
  directive-OFF, unchanged backtest baseline) carry over unchanged from the existing app.
