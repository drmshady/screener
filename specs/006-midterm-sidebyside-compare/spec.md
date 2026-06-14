# Feature Specification: Mid-Term Side-by-Side Variant Comparison

**Feature Branch**: `006-midterm-sidebyside-compare`
**Created**: 2026-06-14
**Status**: Draft
**Input**: User description: "i want option to run for medterm strategy side b side momentum with and withoput sectore gate value with and without momentum floor and dont forget to updtae ai advisor prompet to give result of 4 strtegy"

## User Scenarios & Testing *(mandatory)*

The screener ships two mid-term strategies — `midterm_52w_high_momentum`
(trend) and `midterm_value_composite` (cheapness) — and each already exposes a
toggle the user wants to A/B: momentum's **sector-relative gate** and value's
**momentum floor**. Today the user can run one strategy under one configuration
at a time and must re-run, remember, and eyeball the differences by hand. This
feature lets the user run the mid-term band as a **single side-by-side matrix of
four variants** on one shared universe snapshot, and export all four results in
**one** advisor prompt. It changes neither strategy's underlying rules; it
orchestrates and presents existing capabilities together so the toggle's effect
is visible at a glance and reproducibly.

The four variants are:

1. **Momentum — sector gate ON** (`midterm_52w_high_momentum`, sector-relative ranking applied)
2. **Momentum — sector gate OFF** (same strategy, sector gate disabled)
3. **Value — momentum floor ON** (`midterm_value_composite`, momentum floor applied)
4. **Value — momentum floor OFF** (same strategy, momentum floor disabled)

### User Story 1 - Run the four mid-term variants side by side (Priority: P1)

As the single screener user, I select the mid-term side-by-side comparison and
run it once. I get all four variants screened and ranked against the **same**
liquid-universe snapshot, presented together so I can see how toggling the
sector gate (momentum) and the momentum floor (value) changes each strategy's
candidate set and ranking — without manually re-running or reconciling four
separate screens.

**Why this priority**: This is the feature. Without the one-shot four-variant
run there is no side-by-side comparison. It is independently valuable: the user
can act on the comparison without the advisor-prompt export (Story 2).

**Independent Test**: Run the side-by-side comparison against the frozen
reference snapshot and confirm it returns four labelled variant result sets, all
computed from one shared universe snapshot, each with its own ranked candidates,
per-gate accounting, and price levels, and each carrying `data_as_of` and
`disclaimer`.

**Acceptance Scenarios**:

1. **Given** the liquid universe on the reference snapshot, **When** the user
   runs the mid-term side-by-side comparison, **Then** four clearly labelled
   variants (momentum gate ON/OFF, value floor ON/OFF) are returned together,
   each with its own ranked candidate list and per-gate pass/skip breakdown.
2. **Given** the four variants, **When** the user inspects the difference within
   a strategy, **Then** the only declared difference between its two variants is
   the single toggled parameter (sector gate for momentum, momentum floor for
   value); all other parameters and the universe snapshot are identical.
3. **Given** the same data snapshot run twice, **When** the user runs the
   side-by-side comparison each time, **Then** all four variants' candidate sets,
   ranking, and price levels are identical (no hidden randomness).
4. **Given** any variant's candidate, **When** the user inspects it, **Then** the
   strategy's name, peer-reviewed citation, timeframe, parameters (including the
   toggled parameter's value for that variant), regime favorability, and each
   modification's own citation are displayed.
5. **Given** a variant where a toggle removes a gate (e.g. momentum sector gate
   OFF, or value momentum floor OFF), **When** that variant runs, **Then** the
   now-absent gate is reported as intentionally disabled for that variant, not
   silently dropped.

---

### User Story 2 - Export all four variants in one advisor prompt (Priority: P2)

As the user, after running the side-by-side comparison I click "Copy advisor
prompt" once and get a **single** self-contained, deterministic prompt that
contains the results of all four variants — each variant's live strategy
declaration (with citations), its gate results, its derived price levels, the
shared market regime, and each strategy's honest backtest bias-check — so I can
paste one prompt into an external AI advisor and have it reason across all four
at once.

**Why this priority**: Discovery and external-advisor hand-off make the
comparison actionable in the existing feature-004 workflow, but it depends on
Story 1 producing the four variant results first.

**Independent Test**: With the four-variant comparison loaded, trigger the advisor
prompt export and confirm the produced prompt is one document that names and
separates all four variants, includes each variant's declaration/gates/levels/
regime, includes each underlying strategy's honest bias-check verdict, and is
byte-for-byte identical on repeat export for the same snapshot.

**Acceptance Scenarios**:

1. **Given** a completed four-variant comparison, **When** the user copies the
   advisor prompt, **Then** the single prompt contains four clearly delimited
   variant sections, each labelled with its strategy and toggle state.
2. **Given** the exported prompt, **When** the user inspects any variant section,
   **Then** it contains that variant's strategy declaration with citations, its
   per-gate results, its price levels, the shared regime, and the underlying
   strategy's honest backtest bias-check verdict.
3. **Given** the same snapshot, **When** the user exports the prompt twice,
   **Then** the two prompts are byte-for-byte identical.
4. **Given** the default personal-use settings, **When** the prompt is assembled,
   **Then** any directive framing remains behind the existing personal-use
   directive flag (OFF by default), exactly as the single-strategy export does.

---

### User Story 3 - Honest backtest context for the variants (Priority: P3)

As the user, when I compare the four variants I can still see each underlying
strategy's honest, reproducible backtest context (walk-forward per-year metrics
spanning ≥15 years including 2008–2009, and the bias-check verdict), so the
side-by-side view never implies a variant is validated when its strategy's
bias-check still fails.

**Why this priority**: Required so the comparison and its export stay honest, but
the comparison itself (Story 1) is demonstrable before the backtest context is
wired into the side-by-side view.

**Independent Test**: Open the side-by-side comparison and confirm each
strategy's bias-check verdict is visible (and surfaced honestly when it fails),
and that the advisor prompt carries the same verdict per variant.

**Acceptance Scenarios**:

1. **Given** the side-by-side comparison, **When** the user inspects backtest
   context, **Then** each underlying strategy's bias-check verdict is shown and
   is not hidden when it fails.
2. **Given** a strategy whose bias-check fails (e.g. survivorship on the free
   archive), **When** its variants appear in the comparison and the export,
   **Then** the failing verdict travels with both of that strategy's variants.

---

### Edge Cases

- **A variant returns an empty candidate list** on a given snapshot: that variant
  shows an empty list with gate-accounting notes explaining why, and the other
  three variants are unaffected; the comparison does not error.
- **Toggle removes a gate**: when a toggle disables a gate (momentum sector gate
  OFF, value momentum floor OFF), the variant records that gate as intentionally
  disabled rather than skipped-for-missing-data, so the two states are
  distinguishable.
- **The same name appears in multiple variants** with different ranks: each
  variant ranks independently; the comparison does not deduplicate or merge
  rankings across variants.
- **One underlying strategy is disabled-by-default** (bias-check failing): the
  comparison still runs its variants for inspection but carries the failing
  bias-check verdict honestly; it does not present a disabled strategy as
  validated.
- **Advisor prompt size**: with four variants the prompt is larger; it must
  remain a single self-contained document and must not silently truncate any
  variant's required content.
- **Determinism across variants**: the shared universe snapshot, regime, and
  per-variant levels must be computed deterministically so repeated runs are
  identical.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a mid-term side-by-side comparison run that,
  in a single user action, produces results for four variants: momentum with the
  sector gate ON, momentum with the sector gate OFF, value with the momentum
  floor ON, and value with the momentum floor OFF.
- **FR-002**: All four variants MUST be evaluated against the **same** liquid-
  universe snapshot (same names, same `data_as_of`, same regime), so differences
  between variants are attributable only to the strategy and its toggled
  parameter.
- **FR-003**: Each variant MUST be labelled unambiguously with its strategy and
  the state of its toggled parameter (sector gate ON/OFF for momentum, momentum
  floor ON/OFF for value).
- **FR-004**: Within a strategy, the two variants MUST differ only by the single
  toggled parameter; all other parameters MUST be identical and the difference
  MUST be inspectable by the user.
- **FR-005**: Each variant MUST expose its ranked candidate list, per-candidate
  gate accounting (pass/fail/skip with reason), and derived mid-term price levels,
  with the same transparency a single-strategy screen provides.
- **FR-006**: When a toggle disables a gate for a variant, that gate MUST be
  recorded as intentionally disabled for that variant (distinct from
  skipped-for-missing-inputs), so the on/off states are distinguishable.
- **FR-007**: The side-by-side comparison MUST be deterministic: the same data
  snapshot MUST yield identical candidate sets, ranking, gate results, and price
  levels for all four variants on every run.
- **FR-008**: The comparison MUST NOT alter the underlying strategies' declared
  rules, defaults, parameters, or backtest baselines; it only runs them under the
  specified toggle states.
- **FR-009**: Each variant's surfaced result MUST carry the `data_as_of` and
  `disclaimer` fields, and the UI MUST render them.
- **FR-010**: No user-visible copy introduced by this feature may contain
  directive trading language ("Buy", "Sell", "Recommended", "Strong buy", etc.);
  the existing copy lint MUST pass for all new surfaces.
- **FR-011**: The "Copy advisor prompt" export (feature 004) MUST be extended so a
  single exported prompt assembles all four variants' results into one
  self-contained, deterministic document.
- **FR-012**: For each variant, the exported prompt MUST include that variant's
  strategy declaration (name, citation, timeframe, parameters with the toggled
  value, regime favorability, modifications with their citations), its gate
  results, its derived price levels, the shared market regime, and the underlying
  strategy's honest backtest bias-check verdict.
- **FR-013**: The exported four-variant prompt MUST be byte-for-byte identical on
  repeat export for the same snapshot, and MUST NOT silently truncate any
  variant's required content.
- **FR-014**: Directive framing in the four-variant prompt MUST remain gated
  behind the existing personal-use directive flag (OFF by default), consistent
  with the single-strategy export.
- **FR-015**: Each underlying strategy's honest backtest bias-check verdict MUST
  be surfaced in the comparison view and MUST travel with both of that strategy's
  variants; a failing verdict MUST NOT be hidden.
- **FR-016**: If a variant produces an empty candidate list, the comparison MUST
  show that variant's empty result with gate-accounting notes and MUST NOT error
  or suppress the other three variants.

### Key Entities *(include if data involved)*

- **Variant**: one (strategy, toggled-parameter-state) pair — e.g. "momentum,
  sector gate OFF". Carries a label, the strategy declaration, the toggle's value,
  and its result set.
- **Side-by-side comparison result**: the set of four variant results computed
  from one shared universe snapshot, plus the shared regime and `data_as_of`.
- **Variant result**: a variant's ranked candidates, each candidate's gate
  accounting and price levels, and any empty-result gate notes.
- **Four-variant advisor prompt**: one deterministic document assembling all four
  variant results (declarations, gates, levels, shared regime, per-strategy
  bias-check verdict) for external-advisor hand-off.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single side-by-side run returns exactly four labelled variant
  result sets (momentum ON/OFF, value ON/OFF) computed from one shared snapshot.
- **SC-002**: Running the side-by-side comparison twice on the identical snapshot
  yields byte-for-byte identical candidate sets, ranking, and price levels for all
  four variants.
- **SC-003**: For each strategy's pair of variants, 100% of declared parameters
  other than the toggled one are identical across the two variants.
- **SC-004**: 100% of variant results surfaced to the user include a visible
  data-as-of date and disclaimer.
- **SC-005**: The directive-language lint passes on 100% of new surfaces (zero
  occurrences of prohibited trading verbs).
- **SC-006**: A single advisor-prompt export contains all four variants, each in a
  clearly delimited section with its declaration, gate results, price levels,
  shared regime, and the underlying strategy's bias-check verdict — 0 variants
  missing any required element.
- **SC-007**: Exporting the four-variant advisor prompt twice on the identical
  snapshot yields byte-for-byte identical prompt text.
- **SC-008**: For every variant where a toggle disables a gate, the user can see
  that gate reported as intentionally disabled (distinct from skipped) — 0 gates
  with an ambiguous status.
- **SC-009**: Each underlying strategy's bias-check verdict is visible in the
  comparison and in the export, including when it fails — 0 hidden failing
  verdicts.

## Assumptions

- The momentum strategy already exposes a sector-relative gate toggle and the
  value strategy already exposes a momentum-floor parameter; this feature drives
  those existing toggles and does not invent new strategy behavior.
- The four-variant set is fixed for this feature (momentum sector gate ON/OFF,
  value momentum floor ON/OFF); arbitrary user-defined variant matrices are out of
  scope for v1.
- The mid-term holding-period band, level derivation, regime computation, and the
  comparison surface (feature 003) are reused as-is; no redefinition.
- The advisor-prompt export builder (feature 004) is the single source of truth
  and is extended to a multi-variant assembly; the personal-use directive flag and
  its default-OFF behavior are unchanged.
- Personal-use, single-user, single-machine scope continues to apply; no hosted or
  multi-user deployment is introduced.
- This feature does not change either underlying strategy's rules, defaults, or
  backtest baseline, and does not enable a disabled-by-default strategy.

## Dependencies

- `midterm_52w_high_momentum` (feature 001/002) and its sector-relative gate
  toggle.
- `midterm_value_composite` (feature 005) and its momentum-floor parameter.
- Strategy-comparison surface (feature 003) — where the four variants are shown
  side by side.
- Advisor-prompt export (feature 004) — extended here to assemble four variants
  into one prompt.
- The project constitution's Strategy Transparency (II), Reproducible Backtesting
  (III), and User-Safety/No-Advice (V) principles, which set the transparency,
  honesty, and no-directive obligations above.
