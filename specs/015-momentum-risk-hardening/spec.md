# Feature Specification: Momentum Risk & Validation Hardening

**Feature Branch**: `015-momentum-risk-hardening`
**Created**: 2026-07-02
**Status**: Draft
**Input**: User description: "apply recommendation" — apply the honest-review findings on the mid-term 52-week-high momentum strategy (`midterm_52w_high_momentum`), its risk management, entry/stop-loss/take-profit levels, and position sizing.

## Context & Motivation *(informative)*

An honest review of the primary strategy found that the surrounding engineering is
strong (honest gate accounting, integrity contracts, deterministic bounded levels)
but the **evidence and risk defenses are the weak link**:

1. The published backtest rebalances **once per year, always on January 31**, giving
   only ~80 trades over 2008–2024, with several "years" resting on 1–3 trades. The
   headline total return and max drawdown are artifacts of tiny, seasonally-conditioned
   samples — the honest conclusion is "not yet distinguishable from luck," but the app
   presents point estimates as if settled.
2. The published backtest scores **fixed-horizon** exits, while the app **displays**
   bounded stop-loss / take-profit levels to the owner. The exits actually shown are
   therefore **unvalidated** by the baseline.
3. The one cited crash defense (volatility scaling, Barroso & Santa-Clara 2015) only
   reorders the ranking; it never changes exposure or risk. Regime favorability is
   **display-only**. The 2020–2022 all-loss years (the classic momentum-crash pattern)
   are labeled but undefended.
4. Portfolio holding stops are anchored to **average cost** with no trailing view, so a
   large winner's "current-condition" stop can sit **below the purchase price** — the
   entire gain can be given back before anything flags.
5. Position sizing **fails open to cap-fill** when a stop is missing: the situation with
   the least risk information produces the largest cap-allowed position. Caps limit
   position/sector **value**, never aggregate open **risk** (portfolio heat).
6. Level rationale text mislabels the binding stop (says "200-day SMA trend stop" when
   the 4×ATR risk cap actually set the number), and the volatility reward ceiling is
   mathematically unreachable — decorative rather than binding.

This feature applies those findings. It is a **validation, risk-management, and
honesty** pass. Consistent with the project constitution and prior features (011 US4),
**no screening/selection rule, gate, default, citation, indicator, or backtest baseline
changes silently**: any change to the committed backtest baseline is gated on a
documented, reproducible improvement and remains fully visible; determinism,
`data_as_of` + `disclaimer`, and the zero-directive-language boundary are preserved
end-to-end.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trustworthy backtest evidence (Priority: P1)

The owner opens the momentum strategy's backtest panel and sees results based on a
sample large enough to be meaningful, with realistic trading frictions applied and the
per-year trade counts visible so thin, unreliable years are obvious rather than hidden.

**Why this priority**: Every downstream decision — whether the strategy is worth running,
how to size, whether the levels help — rests on the backtest. A once-a-year,
January-only, ~80-trade sample cannot support the point estimates currently shown. This
is the highest-leverage fix and a prerequisite for honestly evaluating Stories 2 and 5.

**Independent Test**: Run the backtest harness with the new rebalance cadence on the
frozen Stooq snapshot; confirm the trade count increases by roughly an order of
magnitude, that entries are no longer conditioned on a single calendar date, that a
trading-cost model reduces reported returns, and that each year's trade count is
surfaced in the walk-forward panel with a reliability note for thin years.

**Acceptance Scenarios**:

1. **Given** the frozen backtest snapshot, **When** the harness runs with the new
   cadence, **Then** entries occur on multiple rebalance dates across each year (not only
   January 31) and the total trade count is materially larger than the current ~80.
2. **Given** a completed backtest run, **When** results are summarized, **Then** an
   explicit per-side trading-cost assumption is applied and disclosed, and the `costs`
   bias-check line reflects that costs are now modeled rather than self-reporting "not
   included."
3. **Given** a year with very few trades, **When** the walk-forward panel renders,
   **Then** that year is marked as low-reliability (small-sample) so its return/drawdown
   is not read as a stable estimate.
4. **Given** the same snapshot and parameters, **When** the backtest is re-run, **Then**
   it produces byte-identical results (determinism preserved).

---

### User Story 2 - Validate the exits actually shown (Priority: P2)

The owner can see a backtest that models the **same** bounded stop-loss and take-profit
levels the app displays on candidate cards, so the risk levels are backed by evidence
rather than assumed, and can compare that against the fixed-horizon baseline before any
baseline change is adopted.

**Why this priority**: The app shows stop/target levels on every candidate, but the
committed baseline never measured them. A 3R take-profit cap may be cutting the right
tail that momentum depends on. The owner needs the comparison to know whether the
displayed exits help or hurt — and per constitution, a baseline swap must be gated on a
demonstrated improvement, never silent.

**Independent Test**: Run the harness in both fixed-horizon and modeled-exit modes on the
same frozen snapshot; produce a side-by-side comparison artifact; confirm the committed
baseline only changes if the modeled-exit result is a documented improvement, and that
the artifact is retained either way.

**Acceptance Scenarios**:

1. **Given** the frozen snapshot, **When** the modeled-exit backtest runs, **Then** it
   uses the same stop/target derivation the live screen displays (conservative when both
   stop and target are touched in a bar).
2. **Given** both exit models have run, **When** the comparison artifact is produced,
   **Then** it shows total return, hit rate, average win/loss, and drawdown for each, with
   a clear verdict on whether modeled exits improve on fixed-horizon.
3. **Given** the comparison verdict, **When** the baseline is (or is not) updated, **Then**
   the decision is recorded and reproducible, and no baseline change happens without a
   documented improvement.

---

### User Story 3 - Trailing stop for open holdings (Priority: P2)

For each open holding, in addition to the original-plan and current-condition blocks
anchored to average cost, the owner sees a **trailing** protective level derived from
current price/structure, so a position that has run up shows a stop that protects
realized gains instead of sitting below the purchase price.

**Why this priority**: This is the most user-visible risk-management gap. A holding that
doubled currently shows a "current-condition" stop below cost — the entire gain can
evaporate before anything flags. The trailing input (chandelier exit) is already computed
in the pipeline; the gap is presentation, not data.

**Independent Test**: For a synthetic holding whose current price is well above average
cost, confirm a third trailing-level view is returned whose stop is above the purchase
price and moves up as price rises, with neutral, non-directive rationale, while the
existing two blocks are unchanged.

**Acceptance Scenarios**:

1. **Given** a holding trading well above its average cost, **When** holding levels are
   computed, **Then** a trailing protective level is returned that sits above the purchase
   price (protecting gains), distinct from the cost-anchored blocks.
2. **Given** a holding trading at or below average cost, **When** holding levels are
   computed, **Then** the trailing view degrades gracefully (no worse than the
   cost-anchored stop) and never fabricates a level from insufficient data.
3. **Given** any holding, **When** the trailing level renders, **Then** its rationale is
   neutral and contains zero directive language ("buy"/"sell"/"recommended").

---

### User Story 4 - Sizing fails safe, and portfolio heat is bounded (Priority: P2)

When a position's stop is missing or invalid, sizing degrades to a **conservative**
estimate rather than filling the entire cap. Separately, the owner sees the **aggregate
open risk** (portfolio heat) implied by taking a new position alongside existing
holdings, bounded by a configurable ceiling, so ten 1%-risk positions cannot silently
stack into a large correlated drawdown.

**Why this priority**: The current fail-open-to-cap-fill behavior produces the largest
allowed position exactly when risk information is weakest — the opposite of safe. And
value-based caps say nothing about how much is actually at risk if correlated momentum
stops all trigger together, which is precisely the crash scenario.

**Independent Test**: Request sizing with no stop and confirm the suggested size is
conservative (not full cap-fill); request sizing against a portfolio already near a heat
ceiling and confirm the recommendation is bounded and the binding constraint is reported
as portfolio heat.

**Acceptance Scenarios**:

1. **Given** a sizing request with a missing/invalid stop, **When** sizing runs, **Then**
   the suggested size is materially smaller than the legacy cap-fill amount and the
   reasoning states that a conservative fallback was used.
2. **Given** existing holdings whose combined open risk is near the heat ceiling, **When**
   sizing a new position, **Then** the suggested size is reduced so total open risk stays
   within the ceiling, and the binding constraint is reported as portfolio heat.
3. **Given** a sizing request with a valid stop and ample room, **When** sizing runs,
   **Then** behavior matches the existing risk-per-trade result (no regression).

---

### User Story 5 - Regime-aware risk budget (Priority: P3)

The per-trade risk budget (and therefore sizing) responds to the market regime the app
already computes: in an unfavorable (down-trending) regime the risk fraction is reduced,
surfaced as a neutral, informational fact — adopted only if it demonstrably reduces
drawdown in the strengthened backtest.

**Why this priority**: Regime is currently display-only, and vol scaling only reorders
rank. This is the natural defense against the 2020–2022 momentum-crash pattern. But it
must be earned on real data (per the project rule: A/B every recommended default before
applying), so it ranks below the evidence and safety fixes it depends on.

**Independent Test**: With regime-aware budgeting enabled, confirm the risk-per-trade
fraction scales down in an unfavorable regime and is unchanged in a favorable one; run
the strengthened backtest with and without the overlay and confirm adoption is gated on a
documented drawdown improvement.

**Acceptance Scenarios**:

1. **Given** an unfavorable market regime, **When** sizing runs with the overlay enabled,
   **Then** the effective risk-per-trade fraction is reduced versus the favorable-regime
   case, described in neutral language.
2. **Given** the overlay, **When** the strengthened backtest is run with and without it,
   **Then** a comparison artifact records the drawdown effect and the overlay is adopted
   by default only if it improves risk-adjusted results.
3. **Given** the overlay is disabled, **When** sizing runs, **Then** results are identical
   to the current risk-per-trade behavior (opt-in, no silent change).

---

### User Story 6 - Honest level rationale (Priority: P3)

The stop/target rationale names the level that actually set the number: when the risk cap
(ATR bound) determined the stop, the rationale says so rather than crediting the 200-day
SMA; and the reward ceiling is either recalibrated so it can genuinely bind or removed
from the claim so nothing decorative is presented as a constraint.

**Why this priority**: Low effort, pure honesty. The owner is currently told the stop
comes from a rule that did not set it, and told there is a volatility ceiling that can
never bind. Neither changes any number materially, but both mislabel what the owner sees.

**Independent Test**: For a near-52-week-high name where the ATR risk cap binds, confirm
the rationale references the cap; construct a case exercising the reward ceiling and
confirm it either binds meaningfully or is not claimed.

**Acceptance Scenarios**:

1. **Given** a candidate whose stop was set by the ATR risk cap, **When** levels are
   derived, **Then** the rationale attributes the stop to the binding cap, not to the SMA
   rule that did not set it.
2. **Given** the reward-ceiling logic, **When** levels are derived, **Then** the volatility
   horizon ceiling is either recalibrated to a range where it can bind or omitted from the
   rationale, so no non-binding constraint is presented as binding.
3. **Given** the structure stop mode with a missing swing low, **When** levels are derived,
   **Then** the result does not silently fabricate a structure level under a
   structure-stop label — insufficient inputs are reported honestly.

---

### User Story 7 - Clearer risk presentation & workflow (Priority: P2)

The new risk information is presented so the owner can absorb it at a glance and act
without hunting: each candidate card shows its risk distance and reward-to-risk plainly;
holdings show the three protective levels (original plan, current condition, trailing)
side by side with clear status (holding / stop-breached / target-reached / gains-protected);
sizing shows the binding constraint and portfolio-heat headroom; and the backtest panel
visually flags low-reliability years. The presentation stays calm, uncluttered, and
strictly non-directive.

**Why this priority**: The preceding stories add genuinely useful risk facts, but facts
buried in dense tables or ambiguous labels don't change decisions. A solo operator
validating by driving the live app needs the risk picture to be legible and fast to scan
— otherwise the hardening work is invisible. UX sits at P2 because it multiplies the
value of Stories 3–4 without blocking the P1 evidence work.

**Independent Test**: Drive the live app for a candidate, a winning holding, and a sizing
request; confirm the risk distance, reward-to-risk, three holding levels with status, and
portfolio-heat headroom are each visible and unambiguous within a single screen, with no
directive language and with `data_as_of` + `disclaimer` present.

**Acceptance Scenarios**:

1. **Given** a candidate with derived levels, **When** its card renders, **Then** the risk
   distance (entry-to-stop) and reward-to-risk ratio are shown clearly alongside the stop
   and target, in neutral language.
2. **Given** a winning holding, **When** its detail renders, **Then** the three protective
   levels are presented together with an at-a-glance status that distinguishes a
   gains-protected trailing stop from the cost-anchored blocks.
3. **Given** a sizing result, **When** it renders, **Then** the binding constraint
   (risk target / conviction / position cap / sector cap / portfolio heat) and remaining
   portfolio-heat headroom are visible without expanding raw JSON or reasoning text.
4. **Given** the backtest walk-forward panel, **When** it renders, **Then** low-reliability
   (thin-sample) years are visually distinguished from well-sampled years.
5. **Given** any new or changed surface, **When** it renders, **Then** it contains zero
   directive language and preserves `data_as_of` + `disclaimer` (lint clean).

---

### Edge Cases

- **Sparse fundamentals in crisis years**: 2008–2010 have near-zero point-in-time
  fundamentals; the strengthened backtest must keep surfacing this as a coverage
  limitation, not conceal it by increasing cadence.
- **Overlapping holds under higher cadence**: multiple simultaneous open positions per
  name/period must be handled without double-counting or look-ahead.
- **Missing regime signal**: if the regime is unavailable, regime-aware budgeting must
  fail open to the current risk fraction, never error.
- **Trailing stop below cost-anchored stop**: when current price is below cost, the
  trailing view must not present a looser stop as protection.
- **Portfolio heat with a single position**: heat ceiling must behave sensibly for an
  empty or single-holding portfolio.
- **Determinism under new cost model**: costs and cadence must be deterministic — same
  snapshot in, same numbers out.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The backtest harness MUST support a rebalance cadence finer than annual
  (e.g., monthly or quarterly rebalance dates) that materially increases the trade sample
  and removes single-calendar-date entry conditioning, while preserving point-in-time
  correctness (no look-ahead).
- **FR-002**: The backtest MUST apply an explicit, disclosed per-side trading-cost/slippage
  assumption to reported returns, and the `costs` bias-check line MUST reflect that costs
  are modeled.
- **FR-003**: The walk-forward panel MUST surface each period's trade count and flag
  low-reliability (small-sample) periods so thin-sample returns are not read as stable
  estimates.
- **FR-004**: The harness MUST be able to score the **same** bounded stop-loss/take-profit
  levels the live screen displays (modeled exits), conservatively when both stop and
  target are touched within a bar.
- **FR-005**: The system MUST produce a reproducible comparison artifact between
  fixed-horizon and modeled-exit results (and, for Story 5, with/without the regime
  overlay) that records the metrics and an adoption verdict.
- **FR-006**: Any change to the committed backtest baseline MUST be gated on a documented,
  reproducible improvement and MUST remain fully visible; no baseline, gate, default,
  citation, indicator, or selection rule changes silently.
- **FR-007**: For each open holding, the system MUST provide a trailing protective level
  derived from current price/structure in addition to the existing cost-anchored blocks,
  such that for a winner the trailing stop can sit above the purchase price.
- **FR-008**: The trailing level MUST degrade gracefully (never worse than the
  cost-anchored stop, never fabricated from insufficient data) and MUST carry neutral,
  zero-directive rationale.
- **FR-009**: Position sizing with a missing/invalid stop MUST degrade to a conservative
  size (not full cap-fill), and the reasoning MUST state that a conservative fallback was
  applied.
- **FR-010**: The system MUST compute aggregate open risk (portfolio heat) for a proposed
  position alongside existing holdings, bound it by a configurable ceiling, and report
  portfolio heat as the binding constraint when it binds.
- **FR-011**: The system MUST support an opt-in, regime-aware risk-budget overlay that
  reduces the per-trade risk fraction in an unfavorable regime and is unchanged in a
  favorable one; when disabled it MUST be byte-identical to current sizing.
- **FR-012**: Level rationale MUST attribute the stop to the constraint that actually set
  it (e.g., the ATR risk cap when it binds) rather than to a non-binding rule.
- **FR-013**: The volatility/horizon reward ceiling MUST either be recalibrated so it can
  bind within the strategy's holding horizon or be omitted from the rationale so no
  non-binding constraint is presented as binding.
- **FR-014**: All new knobs (cadence, cost assumption, heat ceiling, regime-budget
  overlay, conservative-fallback behavior) MUST be operator-configurable following the
  existing env-flag / `StrategyParameter` conventions and default to values that preserve
  current live-screen output unless explicitly changed.
- **FR-015**: All user-visible outputs added or changed MUST preserve `data_as_of` +
  `disclaimer`, zero directive language, and determinism, and MUST keep hosted-mode
  directive-OFF behavior intact.
- **FR-016**: New financial logic MUST follow the project's test-first rule (golden/
  regression tests before dependence), and existing backend/frontend suites MUST remain
  green with zero silently-skipped financial-logic tests.
- **FR-017**: Candidate surfaces MUST present risk distance (entry-to-stop) and
  reward-to-risk plainly alongside the stop and target, in neutral, non-directive language.
- **FR-018**: Holding surfaces MUST present the original-plan, current-condition, and
  trailing protective levels together with an at-a-glance status that distinguishes a
  gains-protected trailing stop from the cost-anchored blocks.
- **FR-019**: Sizing surfaces MUST make the binding constraint and remaining portfolio-heat
  headroom visible without requiring the owner to read raw reasoning text or JSON.
- **FR-020**: The backtest walk-forward panel MUST visually distinguish low-reliability
  (thin-sample) periods from well-sampled ones.
- **FR-021**: All UX changes MUST reduce, not add, cognitive load — no new clutter, no
  directive framing, and no regression to `data_as_of`/`disclaimer` rendering — and MUST
  degrade gracefully when a level, heat value, or regime signal is unavailable.

### Key Entities *(include if feature involves data)*

- **Backtest run (strengthened)**: a reproducible result keyed by strategy + frozen
  snapshot + cadence + exit model + cost assumption; carries per-period trade counts,
  reliability flags, summary metrics, bias check, and equity curve.
- **Exit-model comparison artifact**: fixed-horizon vs modeled-exit (and vs regime
  overlay) metrics plus an adoption verdict and the decision record.
- **Holding trailing level**: a third protective-level view per open holding, derived from
  current price/structure, alongside original-plan and current-condition blocks.
- **Portfolio heat**: aggregate open risk (sum of per-position risk to stop) for the
  current portfolio plus a proposed position, with a configurable ceiling and binding-
  constraint reporting.
- **Regime risk-budget overlay**: mapping from computed market regime to a scaling of the
  per-trade risk fraction, opt-in and neutrally described.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The strengthened backtest produces a trade sample at least several times
  larger than the current ~80 trades and entries are distributed across multiple rebalance
  dates per year (no single-calendar-date conditioning).
- **SC-002**: Reported backtest returns reflect an explicit per-side cost assumption, and
  the backtest artifact discloses that costs are modeled (no self-reported "costs not
  included" while passing).
- **SC-003**: The owner can view a reproducible fixed-horizon vs modeled-exit comparison,
  and any baseline change is accompanied by a documented improvement verdict; re-running
  the harness on the same snapshot yields byte-identical output.
- **SC-004**: For a holding trading materially above average cost, the app shows a trailing
  protective stop above the purchase price; for a holding at/below cost the trailing view
  never presents a looser level as protection.
- **SC-005**: A sizing request with no stop yields a conservative size strictly smaller
  than the legacy cap-fill amount; a request against a portfolio at the heat ceiling is
  bounded with portfolio heat reported as the binding constraint.
- **SC-006**: With the regime overlay enabled, the effective risk fraction is lower in an
  unfavorable regime than in a favorable one; with it disabled, sizing output is identical
  to current behavior.
- **SC-007**: Every candidate/holding level whose stop was set by the ATR risk cap
  attributes the stop to that cap in its rationale, and no rationale claims a reward
  ceiling that cannot bind.
- **SC-008**: All existing and new financial-logic tests pass with zero silent skips, and
  no live-screen selection output changes versus today unless a knob is explicitly changed.
- **SC-009**: Zero directive-language violations across all new/changed surfaces (lint
  clean), and `data_as_of` + `disclaimer` present on every affected response.
- **SC-010**: For a candidate, a winning holding, and a sizing request, the owner can read
  the full risk picture — risk distance and reward-to-risk, the three holding levels with
  status, and the binding constraint with portfolio-heat headroom — each within a single
  screen without expanding raw text/JSON.
- **SC-011**: In the backtest panel, thin-sample years are visually distinguishable from
  well-sampled years at a glance.

## Assumptions

- "User" is the single owner/operator of this personal-use screener (solo dev, validates
  by driving the live app), consistent with the project's personal-use scope.
- The strengthened backtest continues to use the existing frozen Stooq deep-history
  snapshot; survivorship bias remains a surfaced, known limitation (the free bundle has no
  delisted tickers) — this feature does not attempt to fix survivorship coverage.
- The trailing-stop input reuses the chandelier-exit series already computed in the
  snapshot pipeline; no new indicator data source is introduced.
- Regime signals come from the existing regime calculator; no new regime model is built.
- The trading-cost assumption is a simple, disclosed per-side figure (e.g., a flat basis-
  point cost), not a full market-impact model — sufficient to move reported returns off
  the frictionless baseline honestly.
- Momentum is the primary strategy for deployment; the value strategy is postponed but its
  existing tests must still pass. This feature does not merge value work.
- Adopting any new default (cadence, exit model, regime overlay) is gated on the project's
  "test, don't trust" rule: A/B on real data before applying, never silent.
- Changes are presentation, validation, risk-management, and sizing only — no
  screening/selection rule, gate threshold, citation, or indicator definition changes.
