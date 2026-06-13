# Feature Specification: App & Strategy Validation

**Feature Branch**: `002-app-strategy-validation`
**Created**: 2026-06-12
**Status**: Draft
**Input**: User description: "i want to test current app if it work correctly and strategy work as intended"

## Overview

The MVP screener has been built end-to-end (screening, single-ticker analysis,
backtests, portfolio, regime, Shariah filter, events overlay, plus a Next.js
UI). Before relying on it, the operator needs **confidence that the running
application behaves correctly and that each screening strategy produces the
output its published rules promise** — not just that unit tests pass in
isolation, but that the assembled system, fed real (or realistically frozen)
market data, returns trustworthy, reproducible, correctly-gated results.

This feature is a **validation pass with a primary focus on the mid-term
strategy** (`midterm_52w_high_momentum` — "Mid-Term 52-Week High Momentum",
George & Hwang 2004, with Barroso–Santa-Clara volatility scaling, sector-
relative ranking, and a QMJ-style quality screen). It exercises every user-
facing capability against a known data snapshot, then drills deeply into the
mid-term strategy to confirm its behavior matches its declared rules,
modifications, and citations. It verifies the non-negotiable guardrails (data
provenance labels, no directive language, determinism) and produces a written
findings report that lists what works, what is broken, and what is a free-data
limitation rather than a defect. The two short-term strategies
(`shortterm_minervini_vcp`, `shortterm_atr_breakout`) are checked at a lighter
"does it run cleanly" level only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Confirm the app works end-to-end (Priority: P1)

As the operator, I run the full application against a fixed data snapshot and
walk every primary surface — screen a strategy, open a candidate, analyze a
single ticker, view its backtest, check market regime, apply the Shariah
filter, see event badges, and add a name to the portfolio with position
sizing — confirming each produces sensible, internally consistent output and
no surface errors out.

**Why this priority**: If the assembled app doesn't run cleanly through its
core journeys, nothing else matters. This is the smallest slice that delivers
real value: a go/no-go verdict on whether the app is usable today.

**Independent Test**: Start backend + frontend against the current data
snapshot, drive each page once, and record pass/fail with evidence
(screenshots or captured responses). Delivers a usability verdict even if no
other story is done.

**Acceptance Scenarios**:

1. **Given** the app is running on the current data snapshot, **When** the
   operator runs each of the three default strategies, **Then** each returns a
   candidate list (or an explicit, explained "no candidates" with a gate
   funnel) without server errors.
2. **Given** a candidate from a screen, **When** the operator opens its detail
   and analysis, **Then** the analysis page renders the same identifying data
   (price, sector, gate outcomes) consistently with the screen row.
3. **Given** any user-facing page, **When** it loads, **Then** a `data_as_of`
   date and the standing disclaimer are visible on that page.
4. **Given** the portfolio, **When** the operator adds a candidate and sets
   account capital, **Then** a position size is computed and shown with its
   sizing rationale, and no "Buy/Sell/Recommended" directive wording appears
   anywhere.

---

### User Story 2 - Confirm the mid-term strategy works as intended (Priority: P1)

As the operator, I verify in depth that the mid-term strategy
(`midterm_52w_high_momentum`) actually applies the rules and modifications its
declaration and citations claim — the documented gates fire in the right
order, the named modifications (volatility scaling, sector-relative ranking,
quality screen) genuinely shape the output, named tickers pass or fail for the
documented reason, and the result is the honest consequence of the rules
rather than a coding accident.

**Why this priority**: The mid-term strategy is the operator's primary screen
and the focus of this validation. A screen that returns names for the wrong
reasons (or silently drops the right ones) is worse than no screen. This story
is independently valuable: it can be validated against hand-checked tickers
regardless of the UI.

**Independent Test**: Pick a small set of tickers with known characteristics,
run the mid-term strategy's `rules()` against the snapshot, and confirm each
ticker's pass/fail and the gate-funnel counts match a hand expectation derived
from the strategy's documented rules. Delivers mid-term strategy trust on its
own.

**Acceptance Scenarios**:

1. **Given** the mid-term strategy declaration, **When** it is loaded, **Then**
   it exposes NAME ("Mid-Term 52-Week High Momentum"), CITATION (George & Hwang
   2004), TIMEFRAME (Mid-term), PARAMETERS, REGIME_FAVORABILITY, MODIFICATIONS
   (each carrying its own citation — Barroso–Santa-Clara vol scaling,
   sector-relative ranking, QMJ-style quality), and a pure `rules()` callable —
   and the registry refuses any strategy missing these.
2. **Given** the mid-term strategy run over the universe, **When** the gate
   funnel is inspected, **Then** the documented gates are applied in the
   declared order — liquidity → proximity (≤5% from 52-week high) → trend
   (200-day SMA) → volume → quality (D/E ≤ 1.5 + FCF > 0) → gross-profitability
   (top half) → asset-growth (bottom half) — and each stage's surviving count
   is reported (e.g. the documented funnel 591 → proximity → trend → volume →
   quality → GP → AG).
3. **Given** a ticker the operator hand-classifies as a pass, **When** the
   mid-term strategy runs, **Then** that ticker passes for the documented
   reason; and a hand-classified fail is rejected at the expected gate (e.g.
   WYY at ~11.5% asset growth fails the asset-growth gate; a name far below its
   high fails proximity; a high-debt or negative-FCF name fails the quality
   gate).
4. **Given** each declared modification, **When** it is toggled or inspected,
   **Then** its effect is observable — volatility scaling adjusts sizing/rank,
   sector-relative ranking re-orders within sector, and the quality screen
   removes names that would otherwise pass proximity/trend.
5. **Given** the same data snapshot run twice, **When** the mid-term output is
   compared, **Then** the candidate set, ordering, and gate counts are
   byte-identical (no hidden randomness).

---

### User Story 2b - Smoke-check the short-term strategies (Priority: P3)

As the operator, I confirm the two short-term strategies
(`shortterm_minervini_vcp`, `shortterm_atr_breakout`) still load, declare their
required fields, and run without error on the snapshot — a lighter check than
the mid-term deep dive.

**Why this priority**: They are not the focus of this validation, but a
regression that breaks them should still be caught.

**Independent Test**: Load each, confirm declaration completeness and a clean
run (candidates or an explained empty state) without exceptions.

**Acceptance Scenarios**:

1. **Given** each short-term strategy, **When** it is loaded and run, **Then**
   it declares all required fields and produces a candidate list or an
   explicit, explained empty state without server errors.

---

### User Story 3 - Confirm the mid-term backtest is honest and reproducible (Priority: P2)

As the operator, I verify that the mid-term strategy carries a walk-forward
backtest spanning at least 15 years including the 2008–2009 window, that its
per-year metrics are exposed in the UI, that re-running it on the same data
reproduces the same numbers, and that its known bias caveat (survivorship —
the free Stooq bundle lacks delisted tickers, currently overridden by an
operator flag) is still surfaced rather than hidden.

**Why this priority**: Backtest integrity is the difference between a research
tool and a slot machine, but it sits behind the live-screen verdict in
urgency, so P2.

**Independent Test**: Call each strategy's backtest endpoint, confirm the
window covers ≥15 years and includes 2008–2009, and re-run to confirm
identical metrics. Delivers backtest trust independently of the live screen.

**Acceptance Scenarios**:

1. **Given** the mid-term strategy, **When** its backtest is requested,
   **Then** the returned window spans ≥15 years and includes the 2008–2009
   period, with per-year (walk-forward) metrics present.
2. **Given** a strategy whose backtest does not meet the window floor, **When**
   the registry loads it, **Then** it cannot be marked enabled-by-default
   (except where an explicit, visible operator override applies and the failing
   bias check stays reported in the UI).
3. **Given** the mid-term backtest run twice on the same snapshot, **When**
   results are compared, **Then** the metrics are identical.
4. **Given** the mid-term backtest's survivorship-bias caveat, **When** the
   backtest is viewed, **Then** the caveat remains visible to the user.

---

### User Story 4 - Distinguish real defects from free-data limitations (Priority: P3)

As the operator, I want the validation findings to separate genuine bugs from
known free-data reliability limits (e.g. a handful of stale-price tickers from
yfinance/Stooq, banks lacking FCF, sub-2-year names lacking YoY asset growth),
so I fix what's broken and accept what is inherent to the data tier.

**Why this priority**: Prevents wasted effort chasing "failures" that are
correct gate behavior or upstream data gaps; valuable but only after the core
verdicts exist.

**Independent Test**: For each "missing data" or "dropped ticker" finding,
classify it as defect vs. data-tier limitation with a one-line justification.
Delivers a clean, actionable defect list.

**Acceptance Scenarios**:

1. **Given** a ticker dropped for missing fundamentals, **When** it is
   examined, **Then** the report states whether the gate behaved correctly
   (e.g. a bank with no FCF) or a defect caused the drop.
2. **Given** the validation run, **When** it completes, **Then** the findings
   report lists defects (must-fix), data-tier limitations (accept), and
   passes, with counts.

---

### Edge Cases

- What happens when a strategy returns **zero candidates**? The screen must
  show an explicit, explained empty state with the gate funnel — not a blank
  page or a silent error.
- How does the system behave when the **data snapshot is stale** or a ticker
  has no recent price? Staleness must be surfaced (the meta/staleness panel),
  not hidden behind a stale `data_as_of`.
- What happens for **non-US / `.SR` (Saudi)** tickers where gates such as
  asset-growth have no point-in-time source? The gate must be explicitly
  skipped/labeled, never silently passed as if evaluated.
- How does single-ticker analysis behave for a ticker **outside the screened
  universe** (cross-sectional gates need peers)? It must build/borrow a
  universe for the percentile gates rather than skip them or crash.
- What happens when the **same ticker appears in multiple strategy outputs** —
  is its identifying data consistent across them?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The validation MUST exercise every primary user surface (strategy
  screen, candidate detail, single-ticker analysis, backtest view, market
  regime, Shariah filter, events overlay, portfolio + position sizing) against
  one fixed data snapshot and record pass/fail with evidence for each.
- **FR-002**: The validation MUST confirm that each user-facing page renders a
  `data_as_of` date and the standing disclaimer.
- **FR-003**: The validation MUST confirm that no directive trading language
  ("Buy", "Sell", "Recommended", "Strong buy", and equivalents) appears in any
  user-facing copy.
- **FR-004**: The validation MUST confirm the **mid-term strategy** declaration
  exposes all required fields (NAME, CITATION, TIMEFRAME, PARAMETERS,
  REGIME_FAVORABILITY, MODIFICATIONS with per-item citations, and a pure
  `rules()` callable), and MUST confirm the registry rejects any strategy
  declaration missing required fields. The two short-term strategies MUST be
  confirmed to load and declare required fields (smoke level only).
- **FR-005**: For the **mid-term strategy**, the validation MUST confirm the
  documented gates are applied in the declared order (liquidity → proximity →
  trend → volume → quality → gross-profitability → asset-growth) and that a
  per-stage gate funnel (surviving count at each gate) is produced.
- **FR-006**: For the **mid-term strategy**, the validation MUST verify
  behavior against a small set of hand-classified tickers: each expected pass
  passes for the documented reason and each expected fail is rejected at the
  expected gate.
- **FR-006a**: The validation MUST confirm each declared **mid-term
  modification** (Barroso–Santa-Clara volatility scaling, sector-relative
  ranking, QMJ-style quality screen) has an observable effect on the output
  rather than being inert.
- **FR-007**: The validation MUST confirm determinism: the same data snapshot
  produces identical screen results, regime output, position sizing, event
  badges, and backtest metrics across repeated runs.
- **FR-008**: The validation MUST confirm the universe-wide liquidity gate
  (ADV ≥ $1M 20-day, price ≥ $5, user-configurable) is applied before any
  strategy runs.
- **FR-009**: For the **mid-term strategy**, the validation MUST confirm a
  walk-forward backtest exists covering ≥15 years including 2008–2009, with
  per-year metrics exposed through the backtest endpoint/view; that a strategy
  failing this floor cannot be enabled by default except via a visible operator
  override; and that the mid-term survivorship-bias caveat remains reported in
  the UI.
- **FR-010**: The validation MUST confirm cross-sectional/percentile gates
  (e.g. gross-profitability, asset-growth, sector strength) operate against a
  real peer universe for both in-universe screening and out-of-universe
  single-ticker analysis.
- **FR-011**: The validation MUST confirm that gates with no data source for a
  given market (e.g. asset-growth for `.SR` Saudi tickers) are explicitly
  skipped/labeled rather than silently treated as passed.
- **FR-012**: The validation MUST confirm empty results, stale data, and
  missing-data conditions surface explicit, explained states (gate funnel,
  staleness panel, data notes) rather than blank pages or silent errors.
- **FR-013**: The validation MUST produce a written findings report that
  classifies every finding as defect (must-fix), data-tier limitation
  (accept), or pass, with counts and a one-line justification per non-pass
  item.
- **FR-014**: The validation MUST run against a **frozen/recorded data
  snapshot** so the verdict is reproducible and not dependent on a particular
  day's live feed, while also noting any finding that only appears on live data.
- **FR-015**: The validation MUST confirm the existing automated suites
  (backend pytest including indicator golden-fixture and contract tests;
  frontend Vitest + Playwright including the disclaimer and no-directive lints)
  all pass on the snapshot, and treat any failure as a defect.

### Key Entities *(include if data involved)*

- **Validation Run**: one execution of the full validation against a named data
  snapshot; has a date, the snapshot identifier, and an overall verdict.
- **Surface Check**: a single user-surface exercised (e.g. "midterm screen",
  "portfolio sizing") with its pass/fail status and evidence reference.
- **Strategy Check**: per-strategy result capturing declaration completeness,
  gate-order/funnel correctness, hand-ticker outcomes, and determinism.
- **Backtest Check**: per-strategy confirmation of the ≥15-year/2008–2009
  window, per-year metrics presence, and reproducibility.
- **Finding**: a single observation classified as defect / data-tier limitation
  / pass, with a justification and (for defects) a severity.
- **Data Snapshot**: the frozen market dataset (prices, fundamentals, holdings,
  catalog) the run is evaluated against, identified by its `data_as_of`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of primary user surfaces (the eight in FR-001) are exercised
  and have a recorded pass/fail with evidence in a single validation run.
- **SC-002**: 100% of user-facing pages checked show both a `data_as_of` date
  and the disclaimer; 0 pages are missing either.
- **SC-003**: 0 instances of directive trading language are found in
  user-facing copy.
- **SC-004**: For the **mid-term strategy**, the gate funnel is reproduced and
  every hand-classified ticker (≥4, mixing expected passes and fails across at
  least the proximity, quality, and asset-growth gates) resolves to its
  expected outcome for the documented reason — target 100% match, and any
  mismatch is logged as a defect. The two short-term strategies are confirmed
  to load and run cleanly (smoke level).
- **SC-005**: Re-running the full validation on the same snapshot yields
  identical screen, regime, sizing, event, and backtest outputs — 0
  unexplained differences.
- **SC-006**: The mid-term strategy has a backtest covering ≥15 years including
  2008–2009 with per-year metrics visible to the user, and its survivorship-
  bias caveat is still shown.
- **SC-007**: Every non-pass finding is classified as defect or data-tier
  limitation with a one-line justification — 0 unclassified findings.
- **SC-008**: All existing backend and frontend automated suites pass on the
  snapshot, or each failure is captured as a defect in the report.
- **SC-009**: The operator can complete one full validation pass and read the
  verdict in a single sitting (target: under 60 minutes of active driving once
  the snapshot and app are running).

## Assumptions

- "Test the app" means a **structured validation pass with a written findings
  report**, not building a brand-new automated test framework from scratch; it
  reuses and extends the existing pytest/Vitest/Playwright suites and adds
  strategy-correctness and end-to-end surface checks where gaps exist.
- The validation runs in the **personal-use, single-user, single-machine**
  scope already established for the project; no hosted/multi-user concerns.
- A **frozen data snapshot** is preferred for reproducibility; where a finding
  depends on live data (e.g. stale-price tickers), it is noted as such.
- The **mid-term strategy (`midterm_52w_high_momentum`) is the primary, deep
  validation target** (operator focus). The two short-term strategies
  (`shortterm_minervini_vcp`, `shortterm_atr_breakout`) get a lighter
  loads-and-runs smoke check only; the deferred CAN SLIM strategy is out of
  scope entirely.
- "Works as intended" is judged against each strategy's **own declared rules,
  modifications, and citations** plus the project constitution — not against
  reproducing the original papers' published returns (free-data coverage and
  universe differ).
- Hand-classified reference tickers are chosen by the operator (or drawn from
  prior task notes such as WYY, EA, BELFB, ASYS, AMAT, ROST) and treated as the
  oracle for pass/fail expectations.
- The current data snapshot (`data_as_of` 2026-06-12 era, ~591-name compliant
  US universe plus the ~42-name Saudi `.SR` spike) is representative enough to
  validate against.
