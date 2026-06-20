# Feature Specification: Automated Daily Refresh, Realistic Risk Levels & Smarter Sizing

**Feature Branch**: `011-auto-refresh-risk-sizing`
**Created**: 2026-06-20
**Status**: Draft
**Input**: User description: "iwant update daily prices and deployment is automatic; stop loss and target sometimes is not realistic, investigate for better option; sizing of stock is fixed, investigate better option including use of fair price"

## Overview

Three improvements to the now-online (feature 010) single-owner screener, each a
distinct slice of value:

1. **Operations** — make the daily price update and the publish-to-host
   redeploy **automatic**, so the hosted instance shows fresh end-of-day data
   every trading day without the owner running a manual refresh/build/deploy
   sequence.
2. **Risk levels** — the displayed **stop-loss and take-profit are sometimes
   unrealistic** (e.g., a take-profit far above any plausible move, or a stop so
   far away that the risk-distance is meaningless). Investigate and adopt a
   better, **bounded, validated** method for deriving both.
3. **Position sizing** — sizing is currently **fixed/cap-only** (it fills to the
   per-position and per-sector caps and nothing else). Investigate and adopt a
   better method, **including using an estimate of fair price / fair value** so
   size reflects risk-per-trade and margin of safety rather than only exposure
   caps.

The screener is **already deployed and live** (feature 010): the backend runs as a
Hugging Face Docker Space serving a baked read-only snapshot, and the frontend runs
on Vercel. This feature does **not** re-stand-up hosting — it **automates the
existing publish-and-redeploy chain** against those live targets and improves the
risk overlay; it must not regress the live deployment's access gate, determinism,
or disclosure guarantees.

This feature changes **operational automation** and the **post-screen risk
overlay** (entry/stop/target levels and suggested size) shown to the owner. It is
explicitly an *investigate-then-validate* effort: candidate methods are compared
on real data and the winner is adopted only if it measurably improves realism and
robustness, consistent with the owner's "A/B every default change on real data
before applying" working rule.

Constitutional note: features 008–010 froze "no strategy rule, default, citation,
or backtest baseline change." This feature deliberately revisits the risk-level and
sizing logic. **Decision**: the improved levels become the single source of truth
used **both** in the live display and in the backtest's modeled exits — keeping the
backtest on the old levels while showing new levels would make it no longer reflect
what the owner would actually do, violating the reproducibility/transparency
principles. Therefore a **one-time, controlled re-baseline** of the affected
backtest metrics plus a constitution reproducibility re-check **is** performed,
**gated behind** the US4 comparison artifact proving the new method is an
improvement, and never applied silently. **Screening/selection rules, gates, and
citations stay unchanged.** Determinism (same snapshot → same output) and the
`data_as_of` + `disclaimer` + zero-directive-language non-negotiables are preserved
throughout.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fresh hosted data every trading day, no manual steps (Priority: P1)

As the owner, after each trading day's close the hosted instance automatically
reflects the latest end-of-day prices (and events/fundamentals on their existing
cadence) without me running any refresh, build, or deploy command. I just open the
URL the next morning and `data_as_of` has advanced.

**Why this priority**: Removing the manual publish chore is the most immediately
valuable, lowest-risk part of the request; it makes the already-deployed tool
trustworthy day-to-day without touching strategy output.

**Independent Test**: Let a full trading day elapse with the automation enabled;
the next morning open the hosted app without performing any manual step and confirm
`data_as_of` has advanced to the latest completed trading session and the screen
runs on the fresher snapshot.

**Acceptance Scenarios**:

1. **Given** the automation is enabled and a trading day has closed, **When** the
   owner opens the hosted app the next morning, **Then** `data_as_of` reflects the
   latest completed trading session with no manual action taken.
2. **Given** an automated daily update runs, **When** the refresh, integrity
   checks, and secret scan all pass, **Then** a new snapshot is published and the
   hosted instance is redeployed automatically and serves it.
3. **Given** an automated update step fails (refresh error, integrity failure,
   secret-scan hit, or build/deploy error), **When** the run aborts, **Then** the
   previous known-good snapshot stays live (never a partial/corrupt publish) and
   the owner is notified that the run failed.
4. **Given** a non-trading day (weekend/holiday) or no new completed session,
   **When** the schedule fires, **Then** no redundant rebuild/deploy is performed
   (or it is a documented, harmless no-op).

---

### User Story 2 - Realistic stop-loss and take-profit (Priority: P1)

As the owner, the stop-loss and take-profit shown for a candidate are plausible
for its price, volatility, and the strategy's horizon — not occasionally absurd
(a target implying an unrealistic move, or a stop so far away the risk distance is
meaningless). I can see why each level was chosen.

**Why this priority**: Unrealistic levels undermine trust in the whole tool and
make the suggested sizing meaningless (sizing depends on the stop). This is a
correctness/credibility fix on a primary user-facing surface.

**Independent Test**: Run the mid-term momentum screen on a real snapshot; for
every candidate, verify the stop and target fall within the defined realism bounds
(stop distance and target distance bounded relative to price/volatility/horizon),
and that no candidate shows a degenerate level (target below entry, stop ≥ entry,
target far beyond any plausible move).

**Acceptance Scenarios**:

1. **Given** any candidate on a real snapshot, **When** levels are derived,
   **Then** entry > stop_loss, take_profit > entry, and both the risk distance
   (entry − stop) and reward distance (target − entry) fall within documented,
   volatility-/horizon-aware bounds.
2. **Given** a name whose 200-day trend line sits far below the current price,
   **When** levels are derived, **Then** the resulting stop does **not** produce a
   risk distance so large that the reward target becomes implausible — the method
   bounds it.
3. **Given** the same snapshot, **When** levels are recomputed, **Then** they are
   byte-identical (deterministic).
4. **Given** a candidate, **When** the owner views its levels, **Then** a short,
   plain-language rationale states how the stop and target were derived, with zero
   directive language.

---

### User Story 3 - Smarter, risk- and conviction-aware position sizing (Priority: P2)

As the owner, the suggested position size reflects how much I'd risk on the trade
(distance to stop) and a conviction/quality signal investigated and chosen on real
data — margin of safety versus fair value being one candidate, alongside
volatility targeting and strategy-rank weighting — not merely "fill to the
position/sector cap." Exposure caps still hold as an upper bound, but within them
the size is risk- and conviction-aware.

**Why this priority**: Sizing is the action-facing output; cap-only sizing
over-allocates to wide-stop / overvalued names. It depends on US2 (a realistic
stop) and on a fair-value estimate, so it ranks below the level fix.

**Independent Test**: For a set of candidates with differing stop distances and
differing discount/premium to fair value, request sizing with a fixed capital and
caps; confirm size decreases as risk distance widens and (where fair value is
available) as the discount-to-fair-value shrinks, and that no suggestion ever
breaches a cap.

**Acceptance Scenarios**:

1. **Given** a fixed capital, caps, and a candidate with a known stop distance,
   **When** sizing is requested, **Then** the suggested size targets a bounded
   risk-per-trade (a configurable fraction of capital at risk to the stop) and
   never exceeds the per-position or per-sector cap.
2. **Given** two candidates identical except one has a wider stop, **When** sizing
   each, **Then** the wider-stop candidate gets a smaller suggested size.
3. **Given** the adopted conviction signal's input is available, **When** sizing two
   otherwise identical candidates that differ on it, **Then** the higher-conviction
   one is sized at least as large (and the lower-conviction one may be
   capped/penalized), per the documented rule. *(Fair-value case: deeper discount to
   fair value ⇒ ≥ size; trading above fair value ⇒ may be capped.)*
4. **Given** the adopted conviction signal's input is unavailable for a candidate
   (e.g. no trusted fair-value estimate), **When** sizing is requested, **Then**
   sizing falls back to risk-based-within-caps (fails open, clearly noted) rather
   than erroring.
5. **Given** any sizing result, **When** returned, **Then** it includes a
   plain-language rationale and respects all caps (no breach), with zero directive
   language.

---

### User Story 4 - Investigation & honest validation before adopting any default (Priority: P3)

As the owner, before any new level or sizing default is adopted, I get a
reproducible comparison of the candidate methods on real data, with the trade-offs
stated honestly (including any effect on the reproducible backtest), so I can
confirm the change is an improvement rather than trust a claim.

**Why this priority**: It is the guardrail that makes US2/US3 trustworthy and
matches the owner's working rule, but it is a process/validation deliverable rather
than a day-to-day surface.

**Independent Test**: Produce the comparison artifact on a frozen snapshot showing,
for each candidate method, the realism/robustness metrics and any backtest-baseline
impact; confirm the adopted default is the one the artifact justifies and that the
artifact is regenerable deterministically.

**Acceptance Scenarios**:

1. **Given** the candidate level/sizing methods, **When** the comparison runs on a
   frozen snapshot, **Then** it reports the realism and robustness metrics per
   method deterministically and identifies the selected default.
2. **Given** a method that would move the reproducible-backtest baseline, **When**
   it is evaluated, **Then** that impact is surfaced explicitly and the baseline is
   not silently changed.

---

### Edge Cases

- **Missing/insufficient indicators** (no ATR, no SMA-200, no swing low): levels
  degrade gracefully to a defined fallback or an explicit "not enough data"
  state — never a degenerate level (target ≤ entry, stop ≥ entry, negative stop).
- **Very low-priced or very high-volatility names**: realism bounds still hold;
  the method must not produce a stop ≤ 0 or a target implying an implausible move.
- **Fair value unavailable, stale, or wildly out of range**: sizing/targets fall
  back safely and note the absence; an out-of-range fair-value estimate is not
  trusted blindly.
- **Automation runs on a non-trading day or before the session completes**: no
  bogus snapshot is published; the latest-completed-session basis is respected.
- **Automated run partially completes** (e.g., refresh ok, build fails): the
  hosted instance keeps serving the last known-good snapshot; no partial publish.
- **Secret-scan or data-integrity check fails during an automated run**: the run
  aborts before publish/deploy and the owner is notified; no secret is ever
  written to an artifact.
- **Cap binds tighter than risk-based size**: the cap wins (suggested size never
  breaches caps); rationale states which constraint bound.

## Requirements *(mandatory)*

### Functional Requirements

#### Automated daily refresh & deployment

- **FR-001**: The system MUST update the live hosted instance's data to the latest
  completed trading session automatically on a daily schedule running **unattended
  in cloud CI** (no owner machine required), targeting the already-live Hugging
  Face Space backend + Vercel frontend.
- **FR-001a**: Running ingest in cloud CI **relaxes feature 010's "ingest is
  local-only" posture for the scheduled job only**; the hosted instance itself MUST
  still run no in-host ingest and serve only the published read-only snapshot. The
  CI job MUST produce a snapshot byte-equivalent to what the local pipeline would
  produce for the same session (determinism preserved, FR-012-equivalent).
- **FR-002**: The automated CI update MUST run the existing data pipeline
  (incremental price ingest plus events/fundamentals on their current cadence),
  the data-integrity checks, and the release secret scan, and MUST abort the
  publish/deploy if any of these fail.
- **FR-002a**: All secrets the CI job needs (provider keys, GHCR push credential,
  HF deploy token) MUST live only in the CI provider's encrypted secret store,
  injected at runtime; they MUST NEVER be committed to the repository or written
  into any deployed artifact, and the secret scan MUST still gate the publish.
- **FR-003**: On success, the automated update MUST publish a new read-only
  snapshot and redeploy the hosted instance so it serves the fresher data, with an
  advanced `data_as_of`, preserving the feature-010 guarantee that a partial or
  corrupt snapshot is never served.
- **FR-004**: On any failure in the automated update, the previously published
  known-good snapshot MUST remain live and the owner MUST be notified of the
  failure (with enough detail to act).
- **FR-005**: The automation MUST be idempotent and skip redundant work when no
  new completed trading session exists (non-trading days do not cause a spurious
  rebuild/deploy or a regressed `data_as_of`).
- **FR-006**: All secrets used by the automation (provider keys, deploy/auth
  tokens) MUST be supplied at runtime and MUST NEVER be committed to the
  repository or written into any deployed artifact (unchanged 010 obligation).

#### Realistic stop-loss & take-profit

- **FR-007**: For every mid-term candidate, derived levels MUST satisfy:
  `stop_loss < entry < take_profit`, `stop_loss > 0`, with no degenerate values.
- **FR-008**: The risk distance (`entry − stop_loss`) and the reward distance
  (`take_profit − entry`) MUST each be constrained to documented, volatility- and
  horizon-aware bounds so neither is implausibly large or small.
- **FR-009**: The take-profit MUST NOT imply a move beyond a defined realistic
  ceiling for the candidate (the ceiling MAY incorporate fair value, a measured
  technical move, or a volatility/horizon limit per the adopted method).
- **FR-010**: When required inputs are missing, levels MUST degrade to a defined,
  documented fallback or an explicit "insufficient data" state, never to a
  degenerate level.
- **FR-011**: Each candidate's levels MUST be accompanied by a short
  plain-language rationale of how stop and target were derived, containing zero
  directive language.
- **FR-012**: Level derivation MUST remain deterministic: the same snapshot yields
  byte-identical levels.

#### Smarter, risk- and conviction-aware sizing

- **FR-013**: Position sizing MUST size to a bounded, configurable risk-per-trade
  (capital fraction at risk to the stop) using the realistic stop from FR-007/008,
  instead of only filling to exposure caps. This risk-per-trade backbone is the
  non-negotiable part of the sizing change.
- **FR-014**: Sizing MUST continue to respect the per-position and per-sector
  exposure caps as hard upper bounds; no suggestion may breach a cap.
- **FR-015**: On top of the risk-per-trade backbone, sizing MUST incorporate a
  **conviction/quality modulation signal chosen by investigation** (FR-019) such
  that, all else equal, higher conviction does not reduce — and per the adopted
  rule may increase — suggested size, while lower conviction may reduce or cap it.
  The candidate signals MUST include at least: **(a) fair-value margin of safety**
  (deeper discount to fair value ⇒ higher conviction — the owner's "including use
  of fair price"), **(b) volatility targeting / inverse-volatility**, and **(c)
  strategy-rank / conviction weighting**, against a **(d) risk-per-trade-only**
  baseline. The adopted signal is the one the FR-019 artifact justifies; fair value
  is **not** assumed to win. No new screening/selection rule is introduced by any
  candidate.
- **FR-016**: When the **adopted** conviction signal's input is unavailable or
  untrustworthy for a candidate (e.g. no trusted fair-value estimate), sizing MUST
  fall back to risk-based-within-caps and clearly note the signal was not used
  (fail-open, no error).
- **FR-017**: Every sizing result MUST include a plain-language rationale stating
  the binding constraint (risk target, conviction adjustment, or cap), with zero
  directive language, and MUST be deterministic on a fixed input.
- **FR-018**: If **fair value** is adopted as the conviction signal (or used for the
  FR-009 reward ceiling), its basis MUST be chosen by investigating candidate
  options for **reliability and coverage** on real data — at least (a) reusing
  existing in-repo valuation inputs (book/market, earnings/cashflow/sales yields,
  sector context) and (b) a simple cited intrinsic-value model — and adopting the
  most reliable, documented in the FR-019 artifact. Any adopted fair-value estimate
  MUST be derived from a transparent, free, documented basis (and, if a new computed
  indicator, MUST follow the codebase's golden-fixture-test-first and citation
  rules) so it is reproducible and inspectable, and MUST carry its own
  freshness/provenance and an availability/trust flag. A non-fair-value conviction
  signal (b/c) MUST likewise reuse a transparent, free, point-in-time input already
  in the snapshot.

#### Investigation, validation & guardrails

- **FR-019**: Candidate level methods, candidate sizing methods, **and candidate
  fair-value bases** MUST be compared on real data via a reproducible artifact
  reporting per-method realism, robustness, and reliability/coverage metrics; the
  adopted default MUST be the one that artifact justifies.
- **FR-020**: The adopted levels MUST be used as the single source of truth in
  both the live display and the backtest's modeled exits. The resulting change to
  the reproducible-backtest baseline MUST be performed as a **one-time controlled
  re-baseline gated behind the FR-019 comparison artifact** (which must show the
  new method is an improvement), accompanied by a constitution reproducibility
  re-check, and MUST be surfaced explicitly — never applied silently.
  Screening/selection logic, gates, and citations MUST remain unchanged.
- **FR-021**: Every user-visible response MUST keep carrying `data_as_of` and
  `disclaimer`, and directive personal-use mode MUST remain forced OFF on the
  hosted instance (unchanged 010 obligations).
- **FR-022**: Momentum remains the primary strategy; value remains postponed
  (009/010 scope) but its existing tests MUST still pass. Full backend + frontend
  suites MUST be green after the change.

### Key Entities *(include if feature involves data)*

- **Daily update run**: one scheduled execution — refresh → integrity check →
  secret scan → snapshot publish → redeploy — with a success/failure outcome and
  notification; produces an advanced `data_as_of` on success only.
- **Candidate risk levels**: the entry, stop-loss (and tighter variant),
  take-profit, the realism bounds they satisfy, and the derivation rationale.
- **Conviction signal**: the per-candidate sizing-conviction input adopted in US4 —
  fair-value margin of safety, inverse-volatility, or strategy-rank — each with its
  provenance, freshness, and an availability/trust flag. *(Fair value is one such
  signal: a per-candidate estimate of intrinsic/fair price with a documented basis.)*
- **Sizing suggestion**: suggested shares/value, the risk-per-trade target used,
  the adopted conviction signal + its adjustment, the binding constraint, and
  cap-respect status.
- **Method comparison artifact**: the reproducible per-method realism/robustness
  report on a frozen snapshot that justifies the adopted defaults.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On every trading day with the automation enabled, the hosted
  `data_as_of` advances to the latest completed session by the next morning with
  zero manual steps, across a 5-consecutive-trading-day observation.
- **SC-002**: 100% of automated runs that hit a refresh, integrity, secret-scan,
  or build/deploy failure leave the prior known-good snapshot live (zero
  partial/corrupt publishes) and notify the owner.
- **SC-003**: On a real snapshot, 100% of mid-term candidates show non-degenerate
  levels (`stop_loss < entry < take_profit`, `stop_loss > 0`) within the documented
  realism bounds, and 0 candidates show a take-profit beyond the realistic ceiling.
- **SC-004**: For two candidates differing only in stop distance, the wider-stop
  one is sized smaller in 100% of cases; no sizing suggestion breaches a cap in any
  case.
- **SC-005**: Where the adopted conviction signal's input is available, sizing
  reflects it per the documented rule (e.g. margin of safety if fair value is
  adopted); where unavailable, sizing falls back to risk-based-within-caps without
  error in 100% of cases.
- **SC-006**: Levels and sizing are deterministic — recomputing on the same
  snapshot yields byte-identical results in 100% of cases.
- **SC-007**: A reproducible comparison artifact exists that justifies each adopted
  default and explicitly states any backtest-baseline impact; it regenerates
  identically on the frozen snapshot.
- **SC-008**: Full backend + frontend suites are green (value tests still pass);
  every user-visible response carries `data_as_of` + `disclaimer` with zero
  directive language; no secret appears in the repo or any deployed artifact.

## Assumptions

- **Decision**: the daily automation runs **unattended in cloud CI** on a schedule
  (after the session closes), reusing the existing refresh + publish + deploy chain
  (`scripts/publish.ps1` equivalent: refresh → integrity → secret-scan → build →
  push GHCR → Factory-rebuild the HF Space) with secrets in the CI secret store.
  The hosted instance stays read-only and runs no in-host ingest (consistent with
  feature 010); only the scheduled CI job performs ingest.
- "Realistic" bounds are defined relative to price, recent volatility (ATR), and
  the strategy's mid-term horizon; exact numeric bounds are set during the
  investigation and recorded in the comparison artifact.
- The sizing conviction signal is selected during the investigation (FR-015/019)
  from at least fair-value margin of safety, volatility targeting / inverse-vol,
  and strategy-rank weighting (vs a risk-per-trade-only baseline); fair value is one
  candidate, not assumed to win. Any adopted signal uses a transparent, free,
  point-in-time input already in the snapshot — never a paid feed. If fair value is
  adopted, its **most reliable** basis is selected (FR-018) from the existing
  value-composite/valuation inputs and a simple cited intrinsic-value model.
- Risk-per-trade default (capital fraction risked to the stop) is a small,
  configurable value chosen during validation; caps from existing config remain the
  hard upper bound.
- End-of-day snapshot scope is unchanged (no intraday/real-time data).
- Momentum is primary; value postponed but its tests pass; no screening/selection
  rule, gate, or citation changes beyond what the owner explicitly authorizes.

## Dependencies

- Feature 010 online deployment — **already live**: backend on a Hugging Face
  Docker Space (baked read-only snapshot, owner-gated access), frontend on Vercel,
  secret-scan release check, and the `scripts/publish.ps1` publish chain (refresh →
  verify → secret-scan → build → push GHCR → Factory-rebuild the Space). The
  automation wraps/triggers this existing chain; it does not replace the hosting.
- The existing local data pipeline/scripts (seed, ingest, refresh) and the
  data-integrity harness (008) and startup freshness gate (009).
- Existing level derivation (`derive_levels`) and sizing (`size_position`) and the
  backtest runner that consumes levels.

## Out of Scope

- New screening strategies or changes to gate/selection rules and citations
  (beyond the explicitly-authorized risk-level/sizing change).
- Intraday/real-time data or always-on paid hosting.
- Multi-user access or any change to single-owner scope.
- Paid analyst/fair-value data feeds.
