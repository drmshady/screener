---
description: "Task list for feature 012 â€” Entry-Timing & Candidate Coverage"
---

# Tasks: Entry-Timing & Candidate Coverage

**Input**: Design documents from `specs/012-entry-timing-coverage/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED. The constitution mandates test-first for financial logic (Principle IV)
and the spec/plan explicitly request golden-fixture, component-arithmetic, determinism,
tier-ordering, cadence, and zero-directive-lint tests. New indicators are golden-fixture
tested **before** any surface consumes them.

**Organization**: Tasks are grouped by user story (US1 P1, US2 P2, US3 P3). All three slices
are additive and default-OFF so the baseline screen stays byte-identical (SC-009); they can
ship in any order.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish carry no story label)

## Path Conventions

Web app: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`, `scripts/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm a working baseline before additive changes.

- [X] T001 Confirm prerequisites per [quickstart.md](quickstart.md): warm snapshot present (run `py -3.12 scripts/ingest_daily.py` once if needed) and full backend+frontend suites green on a clean checkout from the repo root (`py -3.12 -m pytest backend/tests`, `cd frontend && npm.cmd run test`) to establish the pre-feature baseline for the SC-009 byte-identical check.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared model scaffolding that US1 and US2 both build on (one shared file, so done once up front). US3 is independent of this phase.

**âš ï¸ CRITICAL**: T002 blocks US1 and US2 implementation.

- [X] T002 Extend `backend/src/models/strategy.py` with the additive, backward-compatible nested models from [data-model.md](data-model.md) â€” `EntryComponent` (name/status/value/reason), `Disqualifier` (name/triggered/value/reason/forces_not_entry_ready), `EntryDiagnostics` (pivot, base_type, base_length_weeks, base_depth, breakout_volume_ratio, dist_above_pivot, dist_above_sma_200), `EntryTimingClassification` (state/components/disqualifiers/diagnostics/summary), and `SkippedGate` (gate, reason) â€” plus `Candidate.entry_timing: Optional[EntryTimingClassification] = None` and `Candidate.skipped_gates: list[SkippedGate] = []`. Defaults keep the serialized payload byte-identical for default-off / non-momentum runs (SC-009); `ScreenResult` shape unchanged.

**Checkpoint**: Model fields exist (all Optional/empty by default) â€” user stories can begin.

---

## Phase 3: User Story 1 - Entry-timing quality overlay (Priority: P1) ðŸŽ¯ MVP

**Goal**: Attach a neutral, deterministic, momentum-only entry-timing classification (entry-ready / not-entry-ready / entry-undetermined) from six pass/fail/undetermined components + disqualifiers, driven by an explicit geometric base-pattern classifier, with an optional default-OFF "entry-ready only" filter and zero directive language.

**Independent Test**: On a frozen snapshot, run a momentum screen; confirm each candidate carries `entry_timing` with six components whose measured values reproduce the FR-002 thresholds exactly (SC-001), the "entry-ready only" filter yields a strict, repeatable subset (SC-002), undetectable bases â†’ entry-undetermined (never false entry-ready), and no directive language appears (SC-008).

### Tests for User Story 1 (write FIRST, ensure they FAIL) âš ï¸

- [X] T003 [P] [US1] Golden-fixture tests for the base-pattern classifier in `backend/tests/indicators/test_base_pattern.py` (TEST-FIRST, Principle IV / FR-002a): assert flat / cup / cup-with-handle / double-bottom labelling, `pivot` = base high (handle high for cup-with-handle), `base_length_weeks`, `base_depth`, most-recent-qualifying-base tie-break, and that unclassifiable / insufficient-history series return `detected=False` (never a fabricated pivot).
- [X] T004 [P] [US1] Component + disqualifier + determinism tests for the overlay in `backend/tests/screening/test_entry_timing.py` (FR-001â€“004/008/022): cover each acceptance scenario US1.1â€“US1.7 (entry-ready all-pass; extended >5%; weak-volume; immature base; base too deep; far above SMA-200; insufficient-data â†’ entry-undetermined), the climax-top and huge-gap disqualifiers forcing not-entry-ready, the short-lived-catalyst warning NOT forcing not-entry-ready, and identical classification on a repeated snapshot.
- [X] T005 [P] [US1] Frontend tests in `frontend/tests/` for entry-timing rendering (state + per-component chips + diagnostics + neutral summary), the "entry-ready only" toggle (default OFF â†’ annotate all; ON â†’ strict subset, US1.8), the empty-state copy when zero entry-ready, and EXTEND the zero-directive copy lint over all new entry-timing copy (SC-008); `data_as_of`/`disclaimer` presence stays green.

### Implementation for User Story 1

- [X] T006 [US1] Implement `backend/src/indicators/base_pattern.py` (after T003 is red): pure, deterministic geometric classifier over one ticker's adjusted OHLC history returning `{detected, base_type, pivot, handle_high, base_start, base_end, base_length_weeks, base_depth, confidence}` per research Decision 1; high-precision stance (below confidence cutoff â†’ `detected=False`). Make T003 green.
- [X] T007 [US1] Add documented, env-overridable entry-timing threshold knobs to `backend/src/lib/flags.py` (011 idiom): pivot max extension (0.05), volume ratio min/preferred (1.4/1.5), per-type base-maturity weeks (flat 5 / cup-family 7), base-depth max (0.33, 30â€“35% band), SMA-200 extension max (0.40), and the climax-top window/advance bounds + huge-gap threshold (FR-002/022).
- [X] T008 [US1] Implement `backend/src/screening/entry_timing.py` (after T004 is red): pure overlay composing the six components (pass rules in [data-model.md](data-model.md) Â§1a) + the three disqualifiers from the scalar base/pivot/volume/SMA-200 columns plus `close`; computes `state` as a pure function of components+disqualifiers; emits neutral zero-directive `summary`; attributes base/pivot/breakout to Minervini (2013) (FR-007). Make T004 green.
- [X] T009 [US1] Modify `_compute_snapshot_rows` in `backend/src/screening/engine.py` to compute the base/pivot/breakout-volume scalar columns (`base_type`, `pivot`, `handle_high`, `base_length_weeks`, `base_depth`, `breakout_volume_ratio`, `dist_above_pivot`, `dist_above_sma_200`) from the in-scope adjusted history via `base_pattern` â€” no new price I/O â€” and **bump `_STOOQ_SNAPSHOT_CACHE_VERSION` v6 â†’ v7** so older cached snapshots lacking the columns are invalidated ([[snapshot-cache-version-gotcha]]).
- [X] T010 [US1] Modify `_screen_from_universe` in `backend/src/screening/engine.py` to invoke the `entry_timing` overlay **only for `midterm_52w_high_momentum`** (FR-023), after `rules()`/contract validation and before candidate assembly, populate `Candidate.entry_timing`, and honor the `entry_ready_only` screen parameter (default OFF â†’ annotate all; ON â†’ return only entry-ready, FR-005). Non-momentum strategies leave `entry_timing=None`.
- [X] T011 [P] [US1] Render the entry-timing classification in `frontend/src/components/CandidateRow.tsx` and `frontend/src/components/ScreenerTable.tsx` â€” overall state + per-component pass/fail/undetermined chips, the auditable diagnostics, and the neutral summary; all copy zero-directive (SC-008).
- [X] T012 [US1] Add the "entry-ready only" screen control (default OFF) wired to the `entry_ready_only` request parameter in the frontend screen controls, plus the neutral empty-state message when the filter returns zero candidates.

**Checkpoint**: Momentum candidates carry an auditable, deterministic, zero-directive entry classification; the filter narrows the list reproducibly. US1 is independently demoable (MVP).

---

## Phase 4: User Story 2 - Expanded candidate coverage (Priority: P2)

**Goal**: A per-strategy three-tier gate classification (essential / preferred / disqualifier) so that, with `expanded_coverage` ON, candidates failing/unevaluable on a *preferred* gate are retained (marked `skipped` + reason, demoted strictly below all clean names) instead of dropped â€” while essential failures and disqualifiers are always excluded and no gate threshold changes. Default OFF reproduces today's screen exactly.

**Independent Test**: On a frozen snapshot, enabling expanded coverage increases the count, 100% of added names fail only preferred gates (zero essential failures, SC-003), every skipped-gate name ranks below every clean name (SC-004), and `expanded_coverage` OFF is byte-identical to today (SC-009).

### Tests for User Story 2 (write FIRST, ensure they FAIL) âš ï¸

- [X] T013 [P] [US2] Tier retention/exclusion/ordering tests in `backend/tests/screening/test_gate_tiers.py` (FR-009â€“015, SC-003/004/009): preferred non-pass retained + `skipped` + reason + demoted (US2.1/2.2); essential failure and disqualifier excluded regardless of toggle (US2.3); `expanded_coverage` OFF â†’ identical to baseline (US2.4/SC-009); strict ordering invariant (no skipped name above any clean name); no gate threshold altered (FR-015).
- [X] T014 [P] [US2] Frontend tests in `frontend/tests/` for the skipped-gate badge + reason on the candidate, the three-tier map in `StrategyGatesPanel`, the `expanded_coverage` toggle (default OFF â†’ identical output), and zero-directive lint over the new copy (SC-008).

### Implementation for User Story 2

- [X] T015 [US2] Implement `backend/src/screening/gate_tiers.py`: per-strategy `gate_tiers(strategy_slug)` map (configurable) defaulting for `midterm_52w_high_momentum` to essential = {liquidity, data-integrity, 52w-high proximity}, preferred = {market regime, sector strength, relative strength}, disqualifier = {climax-top, huge-gap} per [data-model.md](data-model.md) Â§3 / research Decision 3; expose the demote-not-exclude policy for preferred and hard-exclude for disqualifier.
- [X] T016 [US2] Add the `expanded_coverage` flag (default OFF) and gate-tier override knobs to `backend/src/lib/flags.py` (FR-009/013), same idiom as the entry knobs.
- [X] T017 [US2] Modify `backend/src/strategies/midterm_52w_high_momentum.py` (additive only) to consume the three-tier map: preferred gates demote-not-exclude when enabled and add the new relative-strength preferred soft confirmation (RS line vs SPY near new highs, fail-open â†’ `skipped` when SPY history unavailable, research Decision 3) â€” WITHOUT changing any threshold, default, citation, ranking, or the output contract (FR-006/015).
- [X] T018 [US2] Modify `_screen_from_universe` in `backend/src/screening/engine.py` for the `expanded_coverage` path: on a preferred-gate non-pass, retain the candidate, record `Candidate.skipped_gates` (gate + reason), and demote via the **existing** `warning_count`/`data_suspect` sort (reuse, do not reinvent) so skipped names sink below all clean names (FR-010/012, SC-004); essential failures and disqualifiers still exclude regardless of the toggle (FR-011); OFF â†’ existing hard-mode path unchanged (FR-013/SC-009).
- [X] T019 [US2] Carry the skipped gate(s) + reason(s) verbatim into the advisor prompt in `backend/src/agent/advisor_prompt.py` and the candidate detail (FR-014), reusing existing section builders without changing other prompt content.
- [X] T020 [P] [US2] Render the skipped-gate badge + reason on `frontend/src/components/CandidateRow.tsx` and the three-tier (essential/preferred/disqualifier) gate map in `frontend/src/components/StrategyGatesPanel.tsx`; neutral, zero-directive copy.
- [X] T021 [US2] Add the "expanded coverage" screen control (default OFF) wired to the `expanded_coverage` request parameter in the frontend screen controls.

**Checkpoint**: Coverage widens transparently when opted in; clean-above-skipped ordering holds; default-off is byte-identical. US1 + US2 both work independently.

---

## Phase 5: User Story 3 - Quarterly Shariah universe refresh (Priority: P3)

**Goal**: Refresh the Halal Terminal compliant universe only when â‰¥ 90 calendar days have elapsed (or on force), reuse the cache with zero API calls inside the window, fail-safe toward freshness on a missing timestamp, surface a loud "compliance data stale" warning on lapse-without-refresh, and report the ~90-day interval. Deterministic given (elapsed-time, key-availability, force).

**Independent Test**: Simulate consecutive refreshes at varying elapsed times against a recorded timestamp; confirm the API is consulted only at â‰¥90 days (or force) with a key, the cache is reused with zero calls inside the window (SC-006), staleness is surfaced when the window lapses without success (SC-007), and â‰¤ ~4 calls occur over a simulated year (SC-005).

### Tests for User Story 3 (write FIRST, ensure they FAIL) âš ï¸

- [X] T022 [P] [US3] Cadence-decision tests in `backend/tests/shariah/test_refresh_cadence.py` with injected clocks (FR-016â€“021, SC-005/006/007): 30-days â†’ skip (zero calls); 95-days + key â†’ refresh; â‰¥90-days + no key â†’ stale (reuse cache, loud warning); force + key â†’ refresh (bypass gate); missing/unreadable timestamp â†’ due; same elapsed input â†’ same decision (deterministic); simulated year â†’ â‰¤ ~4 refresh actions.

### Implementation for User Story 3

- [X] T023 [US3] Implement `backend/src/shariah/refresh_cadence.py` with the pure, clock-injected `should_refresh(now, last_success_at, *, interval_days=90, force=False, key_present=True)` returning `{action: refresh|skip|stale, elapsed_days, reason}` per research Decision 4 / [data-model.md](data-model.md) Â§4a. Make T022 green.
- [X] T024 [US3] Add the Shariah `refresh_interval_days` knob (default 90) to `backend/src/lib/flags.py` (FR-020), same idiom.
- [X] T025 [US3] Modify `backend/src/data/shariah_halal_terminal.py` so `seed_halal_terminal_results` / `bulk_screen_universe` consult `should_refresh` **before** any `httpx` call (short-circuit on skip/stale), and change the Halal Terminal manifest `refresh_interval_days` 7 â†’ 90 so `ShariahLookup._source_is_stale` reports staleness on the ~90-day basis (FR-016/017/020). Read the API key for presence only â€” never write it to any artifact ([[api-keys-never-write]]).
- [X] T026 [US3] Modify `scripts/ingest_daily.py` to route the Halal Terminal seed through the cadence guard (skip the API call inside the 90-day window; surface a loud "compliance data stale" condition when the window lapsed without a successful refresh), and honor `--force-shariah` (bypass the gate) and `--skip-shariah` flags (FR-019, quickstart).

**Checkpoint**: API usage drops to ~quarterly with honest staleness surfacing; decision is deterministic. All three stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Cross-cutting guarantees and validation across all three slices.

- [X] T027 Add/confirm a default-off byte-identical baseline test (SC-009): with all three features at defaults, a momentum screen on a frozen snapshot serializes identically to the pre-feature baseline (backend `backend/tests/screening/` + frontend default-off identity check).
- [ ] T028 [P] Run the full backend + frontend suites from the repo root on a clean checkout and confirm green, momentum primary, value strategy's existing tests still pass ([[momentum-primary-value-postponed]], [[deploy-010-gotchas]]).
- [X] T029 [P] Execute the [quickstart.md](quickstart.md) validation steps end-to-end (US1 overlay + entry-ready filter, US2 expanded-coverage toggle, US3 90-day cadence incl. `--force-shariah`/`--skip-shariah`) and confirm SC-001â€“SC-008 observable behaviour.
- [X] T030 Repoint the `<!-- SPECKIT START -->â€¦<!-- SPECKIT END -->` agent-context pointer in `CLAUDE.md` to this feature's plan (per plan "Agent context update").

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies â€” establishes the baseline.
- **Foundational (Phase 2 / T002)**: Depends on Setup â€” BLOCKS US1 and US2 (shared `models/strategy.py`). US3 does not depend on it.
- **User Stories (Phase 3â€“5)**: US1 and US2 depend on T002; US3 is fully independent. Stories are otherwise independent and can proceed in priority order (P1 â†’ P2 â†’ P3) or in parallel.
- **Polish (Phase 6)**: Depends on the desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: After T002. Test-first: T006 (indicator) requires T003 red; T008 (overlay) requires T004 red.
- **US2 (P2)**: After T002. Independent of US1 (different files; both touch `engine.py` `_screen_from_universe` â€” sequence T010 then T018 to avoid a merge conflict).
- **US3 (P3)**: Independent of Foundational and the other stories.

### Within Each User Story

- Tests written and FAILING before implementation (Principle IV).
- Indicator (base_pattern) golden-green before the overlay consumes it.
- Models/flags before services; services before engine wiring; backend before frontend rendering.

### Parallel Opportunities

- US3 can run start-to-finish in parallel with US1/US2 (no shared files).
- Test tasks T003/T004/T005 (US1), T013/T014 (US2), T022 (US3) are all [P] â€” different files.
- Frontend render tasks T011 and T020 are [P] relative to their backend siblings.
- Within US1, T006 and (after it) T008 are sequential; T007 (flags) is independent of both.
- âš ï¸ T010 and T018 both edit `engine.py _screen_from_universe` â€” NOT parallel; order T010 â†’ T018.

---

## Parallel Example: User Story 1

```bash
# Write the failing tests first (parallel â€” different files):
Task T003: "Golden-fixture tests in backend/tests/indicators/test_base_pattern.py"
Task T004: "Overlay tests in backend/tests/screening/test_entry_timing.py"
Task T005: "Frontend entry-timing render + filter + lint tests in frontend/tests/"

# Then implement to green (T006 before T008; T007 independent):
Task T006: "indicators/base_pattern.py"
Task T007: "entry-timing flag knobs in lib/flags.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup â†’ 2. Phase 2 Foundational (T002) â†’ 3. Phase 3 US1 â†’ **STOP & VALIDATE** (SC-001/SC-002/SC-008) â†’ demo the entry-timing overlay.

### Incremental Delivery

1. Setup + Foundational â†’ 2. US1 (MVP, P1) â†’ 3. US2 (P2) â†’ 4. US3 (P3). Each ships default-OFF so adding it never changes the baseline (SC-009).

### Parallel Team Strategy

After T002: Developer A â†’ US1, Developer B â†’ US2, Developer C â†’ US3 (US3 needs no foundational dependency). Reconcile the two `engine.py` edits (T010, T018) in sequence.

---

## Notes

- [P] = different files, no incomplete dependencies.
- Verify each test fails before implementing.
- Bumping `_STOOQ_SNAPSHOT_CACHE_VERSION` (T009) is required or the new base columns are silently absent ([[snapshot-cache-version-gotcha]]).
- Zero directive language in ALL new copy (Playwright/copy lint, SC-008); "good entry point" is an objective cited classification, never advice.
- Default-OFF / non-momentum runs must stay byte-identical to the baseline (SC-009).
