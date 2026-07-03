# Feature Specification: Momentum Cockpit — Candidate Lifecycle Pipeline + Portfolio-Aware Fit

**Feature Branch**: `016-momentum-cockpit`
**Created**: 2026-07-03
**Status**: Draft
**Input**: User description: "Momentum Cockpit — a candidate lifecycle pipeline plus a portfolio- and regime-aware fit layer that becomes the new home page. Momentum-only. Add an available-cash, cash-first capital model where cash is a real sizing constraint."

## Overview

The app already ranks momentum candidates, tells the owner whether a candidate is *ready to
buy now* (entry-timing), sizes positions against a portfolio-heat ceiling and sector caps,
tracks holdings with plan/current/trailing risk levels, and reports the market regime.
Today the owner mentally stitches these across five separate screens to answer one recurring
question: *"of everything I'm watching, which is ready AND actually fits my portfolio right
now — and which of my holdings needs attention?"*

This feature adds the connective layer: a candidate **lifecycle pipeline**
(watch → ready → staged → owned → managing → exited) and a **fit/suitability** view that
re-ranks watched candidates by whether a real, heat-capped, sector-capped, cash-limited
position would fit the current portfolio — surfaced as a **momentum-only cockpit that
replaces the static home page**. The app becomes momentum-only in the UI: value and
short-term strategies are removed from every user-facing surface (their code and tests stay
in place, so the change is reversible). It also introduces a **cash-first capital model** (the
owner enters available cash, total capital is derived, and cash becomes a real position-sizing
limit), **in-app buy/sell transaction recording** (the Google Sheet import stays as a secondary
bulk path), and **portfolio win/loss tracking** (realized + unrealized). No screening rule,
gate threshold, indicator definition, citation, or backtest baseline changes — this is
synthesis and presentation of numbers the app already produces, plus one additive sizing
constraint and informational P&L.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See what is ready AND fits my portfolio right now (Priority: P1)

The owner opens the app and, on the home screen, immediately sees a single ranked list of the
momentum candidates they are watching that are both *ready to enter* and would *fit* the
current portfolio (survive heat, sector, concentration, cash, and regime constraints), with
each item showing its suggested position size, the binding constraint, and how much portfolio
heat remains. A running "cumulative heat" line marks the point in the list past which entering
further candidates would breach the heat ceiling.

**Why this priority**: This is the core synthesis the feature exists to deliver — it collapses
five screens of manual cross-referencing into one answer and is independently valuable even
without stage tracking or alerts.

**Independent Test**: With a few momentum tickers watched, holdings imported, and capital set,
open the home page and confirm the ready-and-fit list is present, correctly ordered by fit,
shows per-item sizing + binding constraint, and marks where cumulative heat would bind — all
without navigating elsewhere.

**Acceptance Scenarios**:

1. **Given** the owner watches several momentum candidates and has holdings and capital set,
   **When** they open the home page, **Then** a ready-and-fit list appears ranked by fit, each
   row showing suggested shares, the binding constraint, and resulting heat headroom.
2. **Given** three watched candidates each individually fit but collectively exceed the heat
   ceiling, **When** the owner views the list, **Then** a cumulative-heat marker shows how many
   from the top can be entered together before the ceiling would bind.
3. **Given** several ready-and-fit candidates share one sector, **When** the owner views the
   list, **Then** a sector-clustering note indicates the combined sector exposure that entering
   them all would create.
4. **Given** the market regime does not favor new entries, **When** the owner views the list,
   **Then** every candidate's fit reflects the regime constraint and the reason is shown.

### User Story 2 - Enter available cash and have sizing respect it (Priority: P1)

The owner enters the **available cash** figure their broker shows. Total capital is then
derived automatically as available cash plus the current market value of holdings, so the owner
never re-syncs a "total capital" number as the market moves. Position sizing then treats cash
as a hard limit: a suggested position can never require more dollars than the owner has, and
when cash is the limiting factor the app says so.

**Why this priority**: Cash is the owner's real-world constraint; without it, suggested sizes
can exceed what is actually investable, undermining trust in every downstream fit judgment.
It is independently valuable on the portfolio page even before the cockpit exists.

**Independent Test**: On the portfolio page, enter available cash and confirm total capital
derives as cash + holdings market value; set cash low and confirm a candidate's suggested size
is capped by cash and labeled as cash-limited.

**Acceptance Scenarios**:

1. **Given** the owner has holdings, **When** they enter available cash, **Then** total capital
   is shown as a derived value equal to available cash plus holdings market value.
2. **Given** available cash is set below the cost of a full suggested position, **When** sizing
   runs for that candidate, **Then** the suggested share count is reduced so its cost does not
   exceed available cash, and the binding constraint is reported as available cash.
3. **Given** available cash is set to zero, **When** sizing runs, **Then** the suggested size is
   zero and the reason is reported as available cash (an honest "nothing fits").
4. **Given** the owner has never set available cash, **When** they use the app, **Then**
   behavior is exactly as before this feature (manual total capital, derived cash) with no
   forced change.

### User Story 3 - Know which candidates just became ready and which holdings need attention (Priority: P2)

The owner can tell at a glance which watched candidates *newly* became ready since they last
looked (a "newly ready" badge and a "ready for N days" counter), and which existing holdings
need attention (a level status has changed or open risk exceeds its limit). Each ticker shows a
lifecycle stage badge wherever it appears (screen results, candidate detail, watchlist,
holdings), so the owner always knows where a ticker sits in the pipeline.

**Why this priority**: Alerts and stage visibility turn the cockpit from a snapshot into a
daily driver, but the ready-and-fit synthesis (US1) is usable without them.

**Independent Test**: Watch a candidate, cause its readiness to change, reopen the cockpit, and
confirm the "newly ready" badge and day counter appear and clear once acknowledged; hold a
position whose level status changes and confirm it appears in a "needs attention" list.

**Acceptance Scenarios**:

1. **Given** a watched candidate transitions to ready, **When** the owner opens the cockpit,
   **Then** it shows a "newly ready" badge that clears after the owner has seen it.
2. **Given** a candidate has been ready for several days, **When** the owner views it, **Then** a
   "ready for N days" counter is shown.
3. **Given** an open holding's level status is no longer a plain "holding" or its open risk
   exceeds the limit, **When** the owner opens the cockpit, **Then** that holding appears in a
   "needs attention" list linking to the portfolio.
4. **Given** any ticker in the pipeline, **When** it appears on any screen, **Then** a stage
   badge shows its current lifecycle stage.

### User Story 4 - Record buy/sell transactions in-app and see win/loss (Priority: P2)

The owner records the trades they actually made directly in the app — each buy and sell, with
shares, price, date, and any fees — instead of only importing a spreadsheet (which stays
available for bulk entry). From that history the app shows realized win/loss on closed trades
(with a win rate) and unrealized win/loss on open holdings, per holding and in total.

**Why this priority**: Direct entry removes the spreadsheet round-trip for everyday use, and
win/loss tracking answers "how am I actually doing" — both high-value, but the cockpit's
ready-and-fit synthesis and cash model come first.

**Independent Test**: Record a buy then a partial sell in-app, confirm holdings aggregate the
same as an equivalent import, and confirm the realized P&L (with win/loss) and unrealized P&L
figures appear and are correct.

**Acceptance Scenarios**:

1. **Given** the owner records a buy transaction in-app, **When** they view the portfolio,
   **Then** the holding reflects it identically to an equivalent imported row.
2. **Given** the owner records a sell that closes part of a position, **When** they view
   win/loss, **Then** realized P&L for the closed portion (proceeds − cost basis − fees) and a
   win/loss outcome are shown, and the remaining open shares still show unrealized P&L.
3. **Given** open holdings with current quotes, **When** the owner views the portfolio, **Then**
   unrealized P&L (market value − cost basis) and a portfolio total P&L and win rate are shown.
4. **Given** a quote is unavailable for a holding, **When** unrealized P&L is computed, **Then**
   that holding degrades gracefully (cost basis shown, flagged) without blocking the rest.
5. **Given** the owner prefers bulk entry, **When** they choose "import from Sheet", **Then** the
   existing import path still works as a secondary option.

---

### User Story 5 - Optional decision framing for personal use (Priority: P3)

When the owner has enabled personal-use directive framing (and the app is not in hosted mode),
the fit view may additionally show a concise decision-oriented label per candidate. In the
default and hosted configurations, only neutral suitability language is ever shown.

**Why this priority**: A convenience for the single owner's private use; must never leak into
the neutral or hosted experience, so it is lowest priority and strictly gated.

**Independent Test**: Toggle personal-use directive framing on and off and confirm the optional
label appears only when on and never in hosted mode.

**Acceptance Scenarios**:

1. **Given** personal-use directive framing is off, **When** the owner views fit results,
   **Then** only neutral band + reason language appears (no directive verbs anywhere).
2. **Given** personal-use directive framing is on and the app is not hosted, **When** the owner
   views fit results, **Then** an optional decision label may appear alongside the neutral band.
3. **Given** the app is in hosted mode, **When** any user views fit results, **Then** the
   directive label is never present regardless of the flag.

### Edge Cases

- **Backend pipeline capability disabled**: the home page falls back to today's panels and
  links; nothing breaks and no error is shown.
- **No holdings / no capital / empty watchlist**: empty sections become onboarding prompts (set
  capital, save candidates to watch) rather than blank panels.
- **Unknown or un-priceable ticker in the batch**: that one ticker is skipped with a reason;
  the rest of the board still renders (no whole-board failure).
- **Non-momentum strategy requested for the board**: rejected with a clear message — the
  pipeline is momentum-only because readiness is only defined for momentum.
- **Locally edited but not-yet-synced portfolio**: the board reflects the last synced/persisted
  portfolio, which may lag unsynced local edits; this is disclosed.
- **Stage disagreement (e.g., ready vs. owned)**: stages derived from actual holdings always
  take precedence over readiness- or manually-set stages.
- **Available cash set but stale holdings market value**: total capital derivation uses the
  latest available quotes; if quotes are unavailable, the derivation degrades gracefully rather
  than blocking sizing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a momentum-only candidate lifecycle with stages
  watch → ready → staged → owned → managing → exited, where owned/managing are derived from
  actual holdings, ready is derived from entry-timing, watching is the default for a saved
  candidate, and staged/exited are optional manual overrides that derived stages always outrank.
- **FR-002**: The system MUST compute a fit/suitability result per watched momentum candidate
  from existing outputs — entry-readiness, risk-aware position sizing, portfolio exposure/heat,
  sector caps, concentration, regime favorability, reward-to-risk, and cash sufficiency — and
  express it as a suitability band plus the specific facts that failed.
- **FR-003**: The system MUST rank the ready-and-fit list by fit and MUST show, per item, the
  suggested position size, the binding constraint, and the resulting heat headroom without
  requiring navigation to another screen.
- **FR-004**: The system MUST present a cumulative-heat preview down the ranked list, marking the
  point beyond which entering further candidates would breach the aggregate heat ceiling.
- **FR-005**: The system MUST flag sector clustering when multiple ready-and-fit candidates share
  a sector, indicating the combined sector exposure that entering them all would create.
- **FR-006**: The system MUST let the owner enter **available cash** and MUST derive total capital
  as available cash plus the current market value of holdings; until available cash is set,
  behavior MUST remain identical to today (manual total capital, derived cash).
- **FR-007**: Position sizing MUST treat available cash as a hard limit so that a suggested
  position's cost never exceeds available cash; when cash is the limiting factor, the binding
  constraint MUST be reported as available cash. Available cash of zero MUST yield a zero
  suggested size with available cash as the stated reason.
- **FR-008**: When available cash is not provided, sizing output MUST be identical to today's
  output (the new constraint is additive and inert when unset).
- **FR-009**: The system MUST surface, per watched candidate, when it *newly* became ready since
  the owner last acknowledged it, and MUST show how long it has been ready.
- **FR-010**: The system MUST list open holdings needing attention (a level status other than a
  plain "holding", or open risk exceeding its limit) with a link into the portfolio.
- **FR-011**: The system MUST show a lifecycle stage indicator for a ticker wherever it appears
  (screen results, candidate detail, watchlist, holdings).
- **FR-012**: The cockpit MUST replace the current static home page as the default landing
  surface, retaining the existing regime, data-freshness, and market-events panels, and MUST
  remove every in-app entry point (home cards, navigation, screen/compare links) to non-momentum
  strategies so the product is momentum-only. This removal is user-facing only: the value and
  short-term strategy code, registry entries, and tests MUST remain in place and passing (the
  change is reversible; nothing is deleted from the backend).
- **FR-022**: Users MUST be able to record individual buy and sell transactions directly in the
  app (ticker, side, shares, price, date, optional fees), which MUST feed the same validation and
  average-cost aggregation as the existing bulk import. The existing Google Sheet import MUST
  remain available as a secondary bulk/backup path. Users MUST be able to correct a recorded
  transaction.
- **FR-023**: The system MUST report portfolio win/loss: realized profit-and-loss from
  closed/sold lots (matched by a documented, consistent cost-basis method over the transaction
  history, including a win/loss outcome and win rate), and unrealized profit-and-loss on open
  holdings marked to current market value, with per-holding and portfolio totals. When a quote is
  unavailable, the unrealized figure MUST degrade gracefully rather than block. P&L is
  informational only and MUST NOT change any gate, rank, level, sizing, or backtest result.
- **FR-013**: The system MUST degrade gracefully: when the pipeline capability is disabled or its
  data is unavailable, the home page MUST render today's panels and links without error.
- **FR-014**: Empty or incomplete-setup states (no capital, empty watchlist) MUST render as
  onboarding prompts rather than blank sections.
- **FR-015**: The pipeline/fit board MUST serve the primary momentum strategy only and MUST
  reject requests for other strategies with a clear message; value and short-term strategies
  remain available and their existing behavior and tests are unchanged.
- **FR-016**: All new pipeline/fit behavior MUST be capability-gated and default to today's
  output, such that with the capability off the app is byte-for-byte unchanged.
- **FR-017**: In the default and hosted configurations, all fit/suitability language MUST be
  neutral (no directive trading verbs). An optional decision-oriented label MAY appear only when
  personal-use directive framing is enabled AND the app is not hosted; it MUST never be present
  in hosted mode.
- **FR-018**: Every response that exposes user-visible data for this feature MUST carry the
  standard as-of date and disclaimer, consistent with the rest of the app.
- **FR-019**: Fit, sizing, exposure, and readiness outputs MUST be deterministic: the same data
  snapshot plus the same portfolio MUST produce identical board output.
- **FR-020**: Pipeline lifecycle state (manual stages, ready acknowledgements) MUST be owner
  state that persists across sessions and devices via the existing owner-state sync, and MUST
  remain opaque to the backend (the backend does not interpret it).
- **FR-021**: A per-ticker failure while building the board MUST NOT fail the whole board; the
  affected ticker MUST be skipped with a reason.

### Key Entities *(include if feature involves data)*

- **Pipeline stage**: the lifecycle position of a momentum ticker (watch, ready, staged, owned,
  managing, exited); derived where possible, with staged/exited as optional manual overrides.
- **Fit result**: a per-candidate suitability judgment — a band, the set of pass/fail facts it is
  built from (entry-ready, meaningful size survives, heat headroom, sector room, not
  over-concentrated, regime allows entries, reward-to-risk sufficient, cash sufficient), and an
  optional gated decision label.
- **Board**: the batch view for a set of watched momentum tickers plus portfolio- and
  regime-level context (regime, heat ceiling and headroom, available cash, as-of/disclaimer).
- **Available cash**: the owner-entered investable cash figure; the anchor for the cash-first
  capital model and a hard sizing limit.
- **Derived total capital**: available cash plus current market value of holdings, used wherever
  total capital is consumed once available cash is set.
- **Ready acknowledgement**: owner-state marking that a candidate's "newly ready" transition has
  been seen, and the timestamp since which it has been ready.
- **Transaction**: an owner-recorded buy or sell (ticker, side, shares, price, date, optional
  fees); the retained history from which holdings and realized P&L are computed.
- **P&L result**: realized profit/loss on closed lots (with win/loss outcome and win rate) and
  unrealized profit/loss on open holdings, per holding and in total; informational only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From the home page alone, the owner can identify which watched momentum candidates
  are ready and fit the portfolio, and their suggested sizes, without navigating to any other
  screen.
- **SC-002**: When individually-fitting candidates would collectively breach the heat ceiling,
  the owner can see from the cumulative-heat marker exactly how many of the top-ranked candidates
  can be entered together.
- **SC-003**: After entering available cash, the owner sees total capital equal to available cash
  plus holdings market value, and suggested position costs never exceed available cash in any
  view.
- **SC-004**: Setting available cash to zero results in every candidate showing a zero suggested
  size attributed to available cash, with no misleading non-zero suggestions.
- **SC-005**: With the pipeline capability disabled, the home page and every existing response are
  identical to before this feature (verified byte-for-byte on existing outputs).
- **SC-006**: In default and hosted configurations, no directive trading language appears anywhere
  in the new surfaces (verified by the existing page-wide language lint).
- **SC-007**: The same data snapshot and portfolio produce identical board output across repeated
  runs (determinism).
- **SC-008**: A single unknown or un-priceable watched ticker never prevents the rest of the board
  from rendering.
- **SC-009**: Existing value and short-term strategy behavior and their test suites remain green
  and unchanged, even though those strategies no longer appear anywhere in the UI.
- **SC-010**: A transaction recorded in-app produces the same resulting holding as the equivalent
  imported row, and the Google Sheet import still works as a secondary path.
- **SC-011**: For a recorded buy-then-partial-sell, the owner sees a correct realized P&L and
  win/loss outcome on the closed portion and correct unrealized P&L on the remaining open shares,
  with a portfolio total and win rate.

## Assumptions

- The pipeline and cockpit target the primary momentum strategy (`midterm_52w_high_momentum`)
  exclusively, because entry-timing readiness is only defined for momentum. Value and short-term
  strategies are removed from the UI entirely (not merely demoted), but their code, registry
  entries, and tests remain in place and passing so the removal is reversible.
- Manual transaction recording reuses the existing import validation and average-cost
  aggregation; raw transactions are retained (not just the aggregated snapshot) so realized P&L
  is recomputable from history. Cost basis for realized P&L uses a single documented method
  (FIFO) and is informational only.
- "Buy" / "Sell" as transaction sides describe past owner actions being recorded, not trading
  advice, consistent with the existing import; they are not directive language.
- The owner is the single user; portfolio holdings are derived from the owner's persisted
  transactions, and the board reflects that persisted/synced state rather than unsynced local
  edits.
- Scanning is on-demand (opening the cockpit and a manual refresh); there is no scheduled/cron
  scanning in this feature.
- Reusing the existing personal-use directive framing flag is acceptable for the optional decision
  label; no new directive capability is introduced, and hosted mode continues to force that
  framing off.
- Fit fact weights are fixed, documented constants; per-user configurable weights are out of scope
  for a single-owner tool.
- The cockpit becomes the home page in place; there is no separate cockpit route, and the home
  page must not depend on build-time environment configuration (graceful runtime degradation
  instead).
- The available-cash sizing constraint is additive and optional; when unset, all existing sizing
  and capital behavior is preserved with no migration forced on the owner.
