---
description: "Task list for App & Strategy Validation"
---

# Tasks: App & Strategy Validation

**Input**: Design documents from `specs/002-app-strategy-validation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: This feature *is* a validation/test effort — the harness tasks are
test tasks by nature, and they are required (not optional) because the
deliverable is a verified `findings-report.md`.

**Organization**: Tasks are grouped by user story. The validation is additive:
a new `backend/tests/validation/` pytest package + one new frontend e2e spec,
reusing the existing suites as the regression floor. No production code changes
except defect fixes the run surfaces.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1, US2, US2b, US3, US4 (maps to spec.md)

## Path Conventions

- Backend tests: `backend/tests/validation/`
- Frontend e2e: `frontend/tests/e2e/`
- Report + contracts: `specs/002-app-strategy-validation/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Stand up the validation package and pin the snapshot.

- [X] T001 Create the validation test package directory `backend/tests/validation/` with an empty `__init__.py`.
- [X] T002 Record the frozen snapshot identity: capture the current `/meta` staleness panel `data_as_of`, the US (~591) and Saudi (~42) universe sizes, and a path/hash of `backend/data/`; write them into a `## Snapshot` stub at the top of `specs/002-app-strategy-validation/findings-report.md`.
- [X] T003 [P] Confirm the existing test runners work as the regression floor: run `python -m pytest backend/tests -q`, `npm run test` (frontend Vitest), and `npx playwright test` (frontend) once and note baseline pass/fail counts in `findings-report.md` §6.

**Checkpoint**: Validation package exists; snapshot pinned; baselines captured.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The read-only frozen-snapshot fixture every validation test depends on.

**⚠️ CRITICAL**: No user-story validation can run until T004 is complete.

- [X] T004 Create `backend/tests/validation/conftest.py` with a session-scoped, **read-only** `frozen_snapshot` fixture that loads the current `backend/data/` universe (compliant US via `build_universe_snapshot_stooq`, plus the Saudi `.SR` universe) and exposes the gate inputs via the existing `prepare_universe_gates(df)` helper — asserting it never writes to `backend/data/` (DataSnapshot.read_only).
- [X] T005 [P] Add a `reference_tickers` fixture in `conftest.py` encoding the oracle from `contracts/midterm-gate-expectations.md` (EA/BELFB/ASYS/AMAT/ROST → candidates; WYY → asset_growth fail; a >5%-below-high name → proximity fail; a D/E>1.5-or-FCF≤0 name → quality fail), resolving snapshot-relative symbols at fixture build time.

**Checkpoint**: Frozen snapshot + oracle available to all stories.

---

## Phase 3: User Story 1 - Confirm the app works end-to-end (Priority: P1) 🎯 MVP

**Goal**: Every primary surface runs cleanly and carries `data_as_of` +
disclaimer with zero directive language.

**Independent Test**: Drive all eight surfaces once on the frozen snapshot;
record pass/fail + evidence; assert as-of/disclaimer/no-directive on each.

- [X] T006 [P] [US1] Create `backend/tests/validation/test_surface_sweep_api.py` that hits each backend surface against the frozen snapshot — `screen` (midterm), `candidates`/candidate detail, `analyze` (single ticker), `backtest`, `regime`, `shariah`, `events`, `sizing` — asserting HTTP 200 and that each response body carries `data_as_of` and `disclaimer` (FR-002).
- [X] T007 [US1] In `test_surface_sweep_api.py`, assert cross-surface consistency: a candidate from the midterm screen shows the same price/sector/gate identity when fetched via candidate detail and `analyze` (US1 scenario 2).
- [X] T008 [P] [US1] Create `frontend/tests/e2e/validation-surface-sweep.spec.ts` that visits every primary page (midterm screen, candidate detail, single-ticker analysis, backtest view, regime, Shariah filter, events overlay, portfolio sizing), captures a screenshot per page as evidence, and asserts a visible `data_as_of` date and the standing disclaimer on each (FR-001/002, SC-001/002).
- [X] T009 [P] [US1] Confirm the no-directive-language guarantee across the swept pages by running the existing `frontend/tests/e2e/no-directive-copy.spec.ts` and recording the result; if any swept page is not covered, extend the spec's page list (FR-003, SC-003).
- [X] T010 [US1] Add a portfolio-sizing assertion to `test_surface_sweep_api.py` (or reuse `backend/tests/portfolio/test_sizing_no_breach.py`): adding a candidate with set capital returns a position size + sizing rationale and never breaches the cap (US1 scenario 4).
- [X] T011 [US1] Record all eight SurfaceCheck rows (status, as_of, disclaimer, directive, evidence) into `findings-report.md` §2 per `contracts/findings-report.schema.md`.

**Checkpoint**: App-works verdict (§2) complete and independently demonstrable.

---

## Phase 4: User Story 2 - Confirm the mid-term strategy works as intended (Priority: P1) 🎯 MVP

**Goal**: `midterm_52w_high_momentum` applies its declared rules, gate order,
modifications, and is deterministic.

**Independent Test**: Run the mid-term `rules()` over the frozen universe;
assert declaration, gate order/funnel, oracle, modification effects, determinism.

- [X] T012 [P] [US2] Create `backend/tests/validation/test_midterm_gate_order.py` asserting the mid-term declaration completeness (NAME, CITATION "George & Hwang (2004)", TIMEFRAME, PARAMETERS incl. the documented defaults, REGIME_FAVORABILITY, MODIFICATIONS each with its own citation, pure `rules()`) per `contracts/midterm-gate-expectations.md` (FR-004).
- [X] T013 [US2] In `test_midterm_gate_order.py`, assert the registry **rejects** a deliberately-incomplete strategy stub (missing CITATION or `rules()`) via `_registry.py` (FR-004).
- [X] T014 [US2] In `test_midterm_gate_order.py`, run the mid-term gate funnel on the frozen snapshot and assert the gates fire in the declared order — liquidity → proximity → trend → volume → quality → gross_profitability → asset_growth — and capture the surviving count after each as the GateStage list (FR-005, FR-008). Assert the sector-strength gate is **disabled** (T192 expected state), not silently re-enabled.
- [X] T015 [P] [US2] Create `backend/tests/validation/test_midterm_reference_tickers.py` asserting each oracle ticker's actual pass/fail matches `expected`, and for fails that the rejecting gate matches `expected_gate` (WYY→asset_growth, proximity fail→proximity, quality fail→quality) (FR-006, SC-004). Log any mismatch as a candidate Finding.
- [X] T016 [P] [US2] Create `backend/tests/validation/test_midterm_modifications.py` that toggles each declared modification — volatility scaling (`target_volatility`), sector-relative ranking, quality screen (`max_debt_equity`/FCF) — and asserts the candidate set or ordering changes; a zero-effect modification fails (FR-006a).
- [X] T017 [P] [US2] Create `backend/tests/validation/test_midterm_determinism.py` running the mid-term screen twice on the frozen snapshot and asserting byte-identical candidate set, ordering, and gate counts (FR-007, SC-005).
- [X] T018 [US2] Record the mid-term StrategyCheck (declaration, gate funnel, oracle table, modification effects, determinism) into `findings-report.md` §3.

**Checkpoint**: Mid-term "works as intended" verdict (§3) complete and independently demonstrable. **MVP (US1+US2) done.**

---

## Phase 5: User Story 3 - Confirm the mid-term backtest is honest and reproducible (Priority: P2)

**Goal**: ≥15-yr / 2008–2009 window, per-year metrics, reproducible, caveat visible.

**Independent Test**: Request the mid-term backtest; assert window, metrics,
reproducibility, and the survivorship caveat.

- [X] T019 [P] [US3] Create `backend/tests/validation/test_midterm_backtest.py` asserting the mid-term backtest window spans ≥15 years and includes 2008–2009 with per-year (walk-forward) metrics present (FR-009, SC-006), reusing/extending `backend/tests/integration/test_backtest_window_floor.py`.
- [X] T020 [US3] In `test_midterm_backtest.py`, run the backtest twice on the frozen snapshot and assert identical metrics (FR-009 reproducibility).
- [X] T021 [US3] Assert the enabled-by-default override is explicit and the survivorship caveat is still surfaced: confirm `backend/backtests/midterm_52w_high_momentum/bias_check.md` reports survivorship as failed and that the caveat remains visible in the backtest view (US3 scenarios 2 & 4).
- [X] T022 [US3] Record the BacktestCheck into `findings-report.md` §5.

**Checkpoint**: Backtest integrity verdict (§5) complete.

---

## Phase 6: User Story 2b - Smoke-check the short-term strategies (Priority: P3)

**Goal**: Both short-term strategies load, declare required fields, and run cleanly.

**Independent Test**: Load + run each short-term strategy without error.

- [X] T023 [P] [US2b] Create `backend/tests/validation/test_strategies_smoke.py` that loads `shortterm_minervini_vcp` and `shortterm_atr_breakout`, asserts declaration completeness, and runs each on the frozen snapshot expecting candidates or an explicit explained empty state (no exceptions) (US2b).
- [X] T024 [US2b] Record the short-term StrategyCheck (smoke) rows into `findings-report.md` §4.

**Checkpoint**: Short-term regression guard in place.

---

## Phase 7: User Story 4 - Distinguish real defects from free-data limitations (Priority: P3)

**Goal**: Every non-pass observation is classified defect vs data-tier limitation.

**Independent Test**: Each finding carries a classification + one-line justification.

- [X] T025 [US4] Walk every non-pass observation collected in T011/T015/T016/T017/T019–T021/T023 plus any failures from the T003 regression floor, and classify each as `defect` or `data_tier_limitation` using the `research.md` Decision 6 rubric (stale-price tickers, banks-no-FCF, Saudi asset-growth skip, survivorship → limitations; wrong gate/order, missing disclaimer/as-of, directive language, non-determinism, broken backtest window → defects) (FR-013, SC-007).
- [X] T026 [US4] Confirm edge-case handling and classify: zero-candidate screen shows an explained gate funnel; stale data surfaces via `/meta`; Saudi `.SR` asset-growth is explicitly skipped (not silent pass); out-of-universe single-ticker analysis builds a peer universe for the percentile gates (FR-010/011/012, spec Edge Cases).
- [X] T027 [US4] Write the Findings table (§7) into `findings-report.md`: every defect has a severity, every non-pass has a justification (SC-007).

**Checkpoint**: Clean, classified, actionable findings list.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T028 Run the complete validation per `quickstart.md` end-to-end (regression floor + `python -m pytest backend/tests/validation -q` + the surface-sweep e2e) on the frozen snapshot and confirm SuiteResults (§6) are recorded.
- [X] T029 Write `findings-report.md` §1 (run header + overall verdict) and §8 (verdict + ordered must-fix list), ensuring the verdict is consistent with the defect counts (data-model ValidationRun rules); confirm the report passes the §"Acceptance of the report" checklist in `contracts/findings-report.schema.md`.
- [X] T030 [P] For each blocker/major defect found, fix the production code, re-run the relevant existing test + the validation module, and update the affected report section and verdict (spec US3/US1/US2 — re-validate after each fix).

---

## Phase 9: Decision 7 — Tiered gates (hard eligibility vs pass-with-warning)

Context: the operator asked whether gates are "not equally important so some can pass
with warning," and supplied a sourced PTH-filter report proposing a hard/soft split.
Per the operator's directive ("don't take the report as a rule — test it"), the split
was validated empirically by A/B backtest, not assumed (research.md Decision 7 / 7a).

- [X] T193 [US2] Tier the mid-term gates in `midterm_52w_high_momentum.py`: only **52-week-high proximity** (+ the universe liquidity gate) is HARD; trend/volume/quality/gross-profitability/asset-growth/sector-strength become SOFT. `evaluate()` emits a new `warn` status for a failed soft gate; `rules()` filters on hard gates only and ranks survivors by `(warning_count, score)`. Gated behind `SCREENER_GATE_MODE` (default **hard** preserves the published validation contract; `tiered` is the opt-in research variant).
- [X] T194 [US2] Plumb warnings end-to-end: `GateResult.status` gains `warn`; `Candidate.warnings: list[str]`; engine + backtest runner sort by `(warning_count, score, ticker)`; analyze + screen responses carry per-gate `warn` and the `warnings` array.
- [X] T195 [US3] A/B backtest `scripts/ab_gate_modes.py` (2008-2024, same prices, both modes). **VERDICT: tiered wins** — total_return +214.3% vs +79.5%, max-drawdown 32% vs 34%, and it trades in 17 vs 11 positive years (soft quality does not fail-closed on missing crisis-era fundamentals, so 2008-2009 are covered). Trade-off: wider loss tail (avg_loss -19.4% vs -11.2%). Decision: keep **hard** as the default (validated contract) and ship **tiered** as the proven, opt-in variant pending formal walk-forward re-validation through this 002 suite.
- [X] T196 [US2] Tests: existing hard-filter tests pinned to hard mode (autouse fixture); added a tiered-mode test asserting soft gates `warn` while proximity still `fail`. `backend/tests/strategies` + `backend/tests/screening` green (32 passed).
- [X] T197 Frontend: `analyze` gate panel renders an amber `WARN` badge (skipped recoloured slate); `CandidateRow` shows a "⚠ N soft-gate warnings" chip with a hover tooltip listing them; Zod schemas accept `warn` + `warnings`.
- [ ] T198 [US3] Formal walk-forward re-validation of the tiered variant through this suite (determinism floor + per-year metrics + report §3/§5) before considering a default flip from hard → tiered.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup; **T004 BLOCKS all user stories** (every validation test uses the `frozen_snapshot` fixture).
- **User Stories (Phase 3–7)**: All depend on Phase 2. US1 (P1) and US2 (P1) are the MVP; US3 (P2), US2b (P3), US4 (P3) follow.
- **US4 (Phase 7)** consumes outputs of US1/US2/US3/US2b, so it runs after them.
- **Polish (Phase 8)**: Depends on all desired stories; T030 (fixes) re-runs earlier validations.

### User Story Dependencies

- **US1 (P1)**: After Foundational. Independent.
- **US2 (P1)**: After Foundational. Independent of US1 (different files).
- **US3 (P2)**: After Foundational. Independent.
- **US2b (P3)**: After Foundational. Independent.
- **US4 (P3)**: After US1/US2/US3/US2b produce observations (classification step).

### Within Each User Story

- The validation tests are the implementation; write them against the frozen
  snapshot, then record results into the corresponding report section.
- A story's report section (§) is complete only after its tests run.

### Parallel Opportunities

- T003 (regression floor) runs alongside T001/T002.
- Within Phase 2: T005 ∥ after T004.
- US1 and US2 can be built in parallel (different test files); within US2,
  T015/T016/T017 are separate files and run in parallel after T012/T014.
- US2b (T023) is fully independent and can run anytime after Phase 2.

---

## Parallel Example: User Stories 1 & 2 (MVP)

```bash
# After Phase 2, build the two P1 stories' test files in parallel:
Task: "T006 surface-sweep API test in backend/tests/validation/test_surface_sweep_api.py"
Task: "T008 surface-sweep e2e in frontend/tests/e2e/validation-surface-sweep.spec.ts"
Task: "T012 mid-term gate-order/declaration test in backend/tests/validation/test_midterm_gate_order.py"
Task: "T015 mid-term oracle test in backend/tests/validation/test_midterm_reference_tickers.py"
Task: "T016 mid-term modification-effect test in backend/tests/validation/test_midterm_modifications.py"
Task: "T017 mid-term determinism test in backend/tests/validation/test_midterm_determinism.py"
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Phase 1 Setup → Phase 2 Foundational (T004 is critical).
2. Phase 3 (US1) + Phase 4 (US2) — the two P1 stories.
3. **STOP and VALIDATE**: report §2 and §3 give a defensible "app works + mid-term works as intended" verdict.

### Incremental Delivery

1. Setup + Foundational → snapshot + fixture ready.
2. US1 → §2 (app works) → demo.
3. US2 → §3 (mid-term correct) → demo (**MVP**).
4. US3 → §5 (backtest honest).
5. US2b → §4 (short-term guard), US4 → §7 (classified findings).
6. Polish → §1/§6/§8 + fix any defects.

---

## Notes

- [P] tasks = different files, no incomplete dependencies.
- The frozen snapshot is read-only; never re-ingest mid-run (that starts a new ValidationRun).
- "As intended" is judged against the strategy's declared rules + constitution, not George & Hwang's published returns (spec Assumption).
- Defects vs data-tier limitations follow `research.md` Decision 6 — don't chase correct gate behavior (e.g. WYY at asset_growth) as a bug.
- Commit after each task or logical group.
