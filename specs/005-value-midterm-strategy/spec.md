# Feature Specification: Value-Based Mid-Term Strategy

**Feature Branch**: `005-value-midterm-strategy`
**Created**: 2026-06-13
**Status**: Draft
**Input**: User description: "i want to add new midterm strategy based on value"

## User Scenarios & Testing *(mandatory)*

The screener today ships one mid-term strategy — `midterm_52w_high_momentum`,
a momentum strategy. Momentum and value are the two most-documented, weakly-
correlated return premia in the equity literature; offering a value-based
mid-term strategy lets the single user screen the same universe from a
complementary, mean-reversion angle and compare the two (the comparison surface
already exists from feature 003). This feature adds a second, fully-gated
mid-term strategy whose selection thesis is *cheapness* rather than *trend*.

### User Story 1 - Screen for under-priced, financially healthy mid-term candidates (Priority: P1)

As the single screener user, I open the new value strategy and run it against
the liquid US-equity universe. I get a ranked list of stocks that are cheap on
established valuation measures **and** clear a financial-health gate, each shown
with the same transparency the momentum strategy provides: which gates it
passed or was skipped, why it ranked where it did, the live strategy
declaration (name, peer-reviewed citation, parameters, modifications), and the
price levels (entry / stop / take-profit) consistent with a mid-term holding
period.

**Why this priority**: This is the feature. Without the ranked, gated,
transparent value screen there is no value strategy. It is independently
valuable on its own — a user can act on it without any of the later stories.

**Independent Test**: Run the strategy against the frozen reference snapshot and
confirm it returns a deterministic, value-ranked candidate list where every
listed name clears the cheapness and financial-health gates, each candidate
carries a per-gate pass/skip breakdown, and the response carries `data_as_of`
and `disclaimer`.

**Acceptance Scenarios**:

1. **Given** the liquid universe on the reference snapshot, **When** the user
   runs the value strategy, **Then** the result is a list ranked from cheapest-
   and-healthiest to least, each candidate exposing its valuation rank and the
   gates it passed/skipped.
2. **Given** a stock that is statistically cheap but fails the financial-health
   gate (a likely value trap), **When** the strategy runs in its default
   (hard-gate) mode, **Then** that stock is excluded from the candidate list and
   the exclusion reason is recorded.
3. **Given** the same data snapshot run twice, **When** the user runs the value
   screen each time, **Then** the candidate list, ranking, and price levels are
   identical (no hidden randomness).
4. **Given** a returned candidate, **When** the user inspects it, **Then** the
   strategy's name, peer-reviewed citation, timeframe, parameters, regime
   favorability, and each modification's own citation are all displayed.

---

### User Story 2 - See the value strategy alongside the others and compare (Priority: P2)

As the user, I see the new value strategy listed among the available strategies
with its declared metadata, I can read its declaration page, I can run a
single-ticker analysis against it (the per-gate breakdown for one symbol
evaluated against the live universe), and I can compare it head-to-head with the
momentum strategy using the existing comparison surface.

**Why this priority**: Discovery, single-name analysis, and comparison make the
strategy usable in the existing workflow, but they depend on Story 1 existing
first.

**Independent Test**: Confirm the strategy appears in the strategy list and
detail surfaces with full declaration metadata, that a single-ticker analysis
returns a gate-by-gate evaluation against the live universe distribution, and
that it can be selected in the comparison view next to the momentum strategy.

**Acceptance Scenarios**:

1. **Given** the strategy registry, **When** the user lists available
   strategies, **Then** the value strategy appears with name, citation,
   timeframe, holding period, and regime favorability.
2. **Given** a single ticker, **When** the user analyzes it against the value
   strategy, **Then** the response shows each value/health gate's pass/fail/
   skipped status evaluated against the same universe distribution the screen
   uses (so percentile gates are not silently skipped for one symbol).
3. **Given** both mid-term strategies, **When** the user opens the comparison
   surface, **Then** the value and momentum strategies can be compared side by
   side.

---

### User Story 3 - Trust the value strategy's honest, reproducible backtest (Priority: P3)

As the user, before relying on the value strategy I open its backtest and see
walk-forward, per-year metrics spanning at least 15 years and explicitly
including the 2008–2009 drawdown, together with the honest bias-check status
(the same survivorship / look-ahead disclosure the momentum strategy carries).

**Why this priority**: Required by the project's backtest discipline before the
strategy may be enabled by default, but the screen itself (Story 1) is
demonstrable before the full backtest artifact exists.

**Independent Test**: Open the value strategy's backtest and confirm it reports
per-year metrics across ≥15 years including 2008–2009, on point-in-time data,
with an explicit, visible bias-check verdict.

**Acceptance Scenarios**:

1. **Given** the value strategy, **When** the user opens its backtest, **Then**
   walk-forward per-year metrics covering ≥15 years including 2008–2009 are
   shown.
2. **Given** the backtest artifact, **When** the user inspects data integrity,
   **Then** the bias-check status (e.g. survivorship, look-ahead) is shown
   honestly and is not hidden when it fails.

---

### Edge Cases

- **Missing or stale fundamentals**: a name lacking the inputs a valuation or
  health gate needs is handled by an explicit, recorded skip/pass-through rule
  (consistent with how the momentum strategy records skipped gates), never by a
  silent guess.
- **Negative or zero book value / negative earnings**: valuation ratios become
  meaningless or sign-flipped; these names must not rank as "cheapest" by
  accident.
- **Sectors where the valuation measure is structurally distorted** (e.g.
  financials, REITs): the strategy must define how such sectors are treated so
  they are not spuriously ranked cheap or expensive.
- **Value trap**: a statistically cheap but deteriorating company is excluded
  (default hard mode) or flagged with a warning (tiered mode), mirroring the
  momentum strategy's soft/hard gate behavior.
- **Empty result**: when no name clears the gates on a given snapshot, the
  screen returns an empty list with the gate-accounting notes explaining why,
  rather than erroring.
- **Look-ahead in fundamentals**: backtests must use the financials as they were
  known at each historical date (point-in-time), not restated later figures.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST add a new mid-term strategy whose selection thesis
  is valuation (cheapness), registered through the same strategy registry as the
  existing strategies and refused at load time if it is missing any required
  declaration field.
- **FR-002**: The strategy MUST declare a name, a peer-reviewed citation for its
  core value thesis, its timeframe (mid-term), its parameters, its regime
  favorability, and its modifications — each modification carrying its own
  citation — exactly as the constitution's Strategy Transparency principle
  requires.
- **FR-003**: The strategy MUST rank candidates by a multi-metric value composite
  (combining cheapness measures such as book/market, earnings yield, cash-flow
  yield, and sales yield) rather than a single ratio, so cheaper qualifying names
  rank ahead of more expensive ones and no single distorted ratio dominates the
  ranking. The composite anchors on the academic value premium (Fama & French
  (1992); Lakonishok, Shleifer & Vishny (1994), Contrarian Investment,
  Extrapolation, and Risk).
- **FR-004**: The strategy MUST apply a financial-health gate based on the
  Piotroski (2000) F-Score (Value Investing: The Use of Historical Financial
  Statement Information) to screen out likely value traps (statistically cheap
  but financially deteriorating names), and MUST record, per candidate, whether
  that gate passed, failed, or was skipped for missing inputs.
- **FR-005**: The strategy MUST inherit the universe-wide liquidity gate (ADV and
  minimum price) that applies before any strategy runs; it MUST NOT screen
  illiquid or sub-threshold names.
- **FR-006**: For every candidate, the strategy MUST derive mid-term-appropriate
  price levels (entry, stop-loss, take-profit) and expose them, consistent with
  the holding-period horizon it declares.
- **FR-007**: The strategy MUST produce identical screen output — candidate set,
  ranking, gate results, and price levels — for the same data snapshot (no
  hidden randomness).
- **FR-008**: The strategy MUST record honest gate accounting: every gate it
  declares either runs or is recorded as skipped, with the reason, surfaced the
  same way the momentum strategy surfaces applied/skipped gates.
- **FR-009**: The strategy MUST be evaluable for a single ticker against the live
  universe distribution, so cross-sectional (percentile/rank) gates are computed
  rather than silently skipped for one symbol.
- **FR-010**: The strategy MUST appear in the available-strategies list, its
  declaration detail surface, the single-ticker analysis surface, and the
  strategy-comparison surface (feature 003), with its full declared metadata.
- **FR-011**: The strategy MUST ship a walk-forward backtest covering ≥15 years
  including 2008–2009 on point-in-time data with no look-ahead, exposing per-year
  metrics and an honest, visible bias-check verdict; it MUST NOT be enabled by
  default unless that backtest exists and its bias checks are satisfied (or an
  explicit, recorded operator override is in force, as with the momentum
  strategy).
- **FR-012**: Every user-visible response from the new strategy MUST carry the
  `data_as_of` and `disclaimer` fields, and the UI MUST render them.
- **FR-013**: No user-visible copy introduced by this strategy may contain
  directive trading language ("Buy", "Sell", "Recommended", "Strong buy", etc.);
  the existing copy lint MUST pass for all new surfaces.
- **FR-014**: The strategy MUST define how it treats sectors whose chosen
  valuation measure is structurally distorted (e.g. financials, REITs) — by
  sector-relative comparison, exclusion, or another documented rule — so such
  names are not spuriously ranked.
- **FR-015**: Valuation inputs that are negative, zero, or otherwise undefined
  for the chosen ratio (e.g. negative book value, negative earnings) MUST be
  handled by an explicit rule and MUST NOT rank as artificially cheap.
- **FR-016**: The strategy MUST be exportable through the "Copy advisor prompt"
  capability (feature 004) — its live declaration, gate results, levels, regime,
  and backtest bias-check assemble into the deterministic advisor prompt the same
  way the momentum strategy does.

### Key Entities *(include if feature involves data)*

- **Value strategy declaration**: the registered strategy's metadata — name,
  core value citation, timeframe, holding period, parameters, regime
  favorability, and the list of modifications (each with its own citation).
- **Valuation inputs**: the per-company fundamental quantities the value
  composite and health gate consume (e.g. valuation ratios and financial-health
  measures), each with a point-in-time as-of date.
- **Candidate result**: a screened name with its valuation rank/score, its
  per-gate pass/fail/skip breakdown, derived price levels, and a plain-language
  reason.
- **Backtest artifact**: the walk-forward, per-year metrics plus bias-check
  verdict for the value strategy on the reference snapshot.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running the value strategy on the reference snapshot returns a
  ranked candidate list in which 100% of listed names clear both the cheapness
  and financial-health gates.
- **SC-002**: Running the value screen twice on the identical snapshot yields
  byte-for-byte identical candidate sets, ranking, and price levels.
- **SC-003**: 100% of returned candidates display the strategy's name,
  peer-reviewed citation, and each modification's citation, with zero candidates
  missing any declaration field.
- **SC-004**: 100% of value-strategy responses surfaced to the user include a
  visible data-as-of date and disclaimer.
- **SC-005**: The directive-language lint passes on 100% of new surfaces (zero
  occurrences of prohibited trading verbs).
- **SC-006**: The value strategy's backtest reports per-year metrics for ≥15
  distinct years including 2008 and 2009, each year individually visible.
- **SC-007**: For any candidate, the user can see, for every declared gate,
  whether it passed, failed, or was skipped (and why) — 0 gates reported with an
  unexplained status.
- **SC-008**: The user can select the value strategy and the momentum strategy
  together in the comparison surface and view their metrics side by side.

## Assumptions

- The strategy's holding-period horizon matches the existing mid-term band
  (roughly 60–180 days), so the momentum strategy's level-derivation and
  comparison surfaces apply without redefinition.
- The valuation and financial-health inputs are obtainable from the project's
  existing free, personal-use fundamental sources (SEC EDGAR filings, plus
  current fundamentals already used by the momentum strategy's quality gates);
  where point-in-time history is unavailable, the strategy records a skip/pass-
  through rather than fabricating data — the same honesty rule the momentum
  strategy follows for missing fundamentals.
- The default gate mode is hard (value-trap names are excluded); a tiered mode
  that warns-and-ranks instead may be offered behind the same switch the
  momentum strategy already exposes.
- Personal-use, single-user, single-machine scope continues to apply; no hosted
  or multi-user deployment is introduced.
- The strategy ships disabled-by-default until its ≥15-year backtest and bias
  checks are in place, then is enabled under the same gating the momentum
  strategy uses (bias-check pass or recorded operator override).
- This feature adds one new strategy; it does not modify the existing momentum
  strategy's behavior or backtest baseline.

## Dependencies

- Strategy registry and declaration contract (feature 001) — the load-time
  enforcement of required declaration fields.
- Universe-wide liquidity gate (feature 001) — applied before this strategy runs.
- Strategy-comparison surface (feature 003) — where value vs. momentum are
  compared.
- Advisor-prompt export (feature 004) — the value strategy must be exportable
  through it.
- The project constitution's Strategy Transparency (II) and Reproducible
  Backtesting (III) principles, which set the citation and backtest obligations
  above.
