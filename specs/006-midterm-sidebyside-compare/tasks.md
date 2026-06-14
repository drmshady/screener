# Tasks: Mid-Term Side-by-Side Variant Comparison

**Feature**: `006-midterm-sidebyside-compare` | **Branch**: `006-midterm-sidebyside-compare`
**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included (test-first). Constitution Principle IV + the quickstart
runbook require failing tests before implementation for this feature's
orchestration/presentation logic. There are **no new indicators or screening
rules** — underlying gates are unchanged and already fixture-tested.

**Scope reminder**: Orchestration + presentation only. Do **not** change either
strategy's rules, defaults, parameters, or backtest baselines (FR-008). Both
toggles already exist and thread through `run_strategy(parameters)` →
`universe.attrs` ([engine.py:1071](../../backend/src/screening/engine.py#L1071),
[engine.py:1077](../../backend/src/screening/engine.py#L1077)).

**Fixed four-variant matrix** (research Decision 1):
`momentum_sector_on` (`sector_strength_top_fraction=0.5`), `momentum_sector_off`
(`=1.0`), `value_floor_on` (`min_momentum_12_1=-0.20`), `value_floor_off` (`=-1.0`).

---

## Phase 1: Setup

- [ ] T001 Confirm the two toggles and their per-run threading are intact before building on them: verify `sector_strength_top_fraction` (default 1.0) in [backend/src/strategies/midterm_52w_high_momentum.py](../../backend/src/strategies/midterm_52w_high_momentum.py) and `min_momentum_12_1` (default -1.0) in [backend/src/strategies/midterm_value_composite.py](../../backend/src/strategies/midterm_value_composite.py), and their forwarding in [backend/src/screening/engine.py](../../backend/src/screening/engine.py); record the exact attr keys in a one-line comment at the top of the new matrix module.
- [ ] T002 Create empty module skeletons so imports resolve: `backend/src/screening/midterm_matrix.py` (variant specs + `run_midterm_matrix` stub) and test files `backend/tests/screening/test_midterm_matrix.py`, `backend/tests/agent/test_midterm_matrix_prompt.py`, `backend/tests/api/test_midterm_compare_api.py`.

**Checkpoint**: Toggles confirmed; skeletons in place for TDD.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: The shared-snapshot seam that every user story builds on. MUST
complete before US1–US3.

- [ ] T003 In [backend/src/screening/engine.py](../../backend/src/screening/engine.py), factor `run_strategy` so the universe-snapshot build (steps up to `universe` assembly) and the "apply attrs → call `strategy.rules(universe)` → assemble candidates → build `ScreenResult`" steps are reusable helpers callable with a pre-built snapshot. Preserve `run_strategy`'s existing behaviour/signature exactly (pure refactor; existing tests must stay green).
- [ ] T004 Define the fixed `VariantSpec` set and `run_midterm_matrix(as_of_date=None, filters=None, shariah_overrides=None, parameters=None)` in `backend/src/screening/midterm_matrix.py`: build the snapshot **once** (T003 helper), then for each of the four variants set the variant's toggle on a copy of the shared frame, call its strategy's `rules()`, and assemble a per-variant `ScreenResult`. Ignore any caller-supplied `sector_strength_top_fraction`/`min_momentum_12_1` (matrix owns them). Return shared `regime` + `data_as_of` alongside the four results. Per research Decision 2.
- [ ] T005 [P] Add wire models in [backend/src/models/strategy.py](../../backend/src/models/strategy.py): `VariantResult` (key, label, strategy, toggle_param, toggle_value, toggle_on, screen, bias_check), `MidtermComparisonResponse` (variants, regime, data_as_of, disclaimer), `MidtermComparePromptResponse` (prompt, variant_count, personal_use_directive, data_as_of, disclaimer). Per [data-model.md](data-model.md).

**Checkpoint**: A single call builds one snapshot and returns four variant
`ScreenResult`s + shared regime/`data_as_of`. User stories can now proceed.

---

## Phase 3: User Story 1 — Run the four mid-term variants side by side (Priority: P1) 🎯 MVP

**Goal**: One action returns four labelled variant screens on one shared snapshot.

**Independent test**: `POST /strategies/midterm-compare` returns 4 labelled
variants, all sharing `data_as_of`/universe/regime, each with ranked candidates +
gate accounting + levels + `disclaimer`.

### Tests (write first, must fail)

- [ ] T006 [P] [US1] In `backend/tests/screening/test_midterm_matrix.py`: assert `run_midterm_matrix` returns exactly 4 variants in fixed order with correct keys/labels/toggle values; all four share one `data_as_of` and the same universe ticker set and the same `regime` (FR-002, SC-001); within each strategy pair every declared parameter except the toggled one is identical (FR-004, SC-003).
- [ ] T007 [P] [US1] In the same test file: determinism — two `run_midterm_matrix` calls on the same snapshot yield identical candidate sets, ranking, and levels for all four variants (FR-007, SC-002); and an empty variant returns `screen.candidates == []` with gate-accounting notes without dropping the other three (FR-016).
- [ ] T008 [P] [US1] In `backend/tests/api/test_midterm_compare_api.py`: `POST /strategies/midterm-compare` returns 200 with `len(variants)==4`, top-level `regime`/`data_as_of`/`disclaimer`, each variant's `screen` carries `data_as_of`+`disclaimer`, and caller-supplied toggle params are ignored (FR-009, SC-004).

### Implementation

- [ ] T009 [US1] Implement `run_midterm_matrix` fully (replace the T004 stub) so T006/T007 pass: correct labels, `toggle_on` flags, per-variant `bias_check` via `load_survivorship_status(slug=…)`, shared regime computed once.
- [ ] T010 [US1] Add `POST /strategies/midterm-compare` in [backend/src/api/strategies.py](../../backend/src/api/strategies.py): call `run_midterm_matrix`, map to `MidtermComparisonResponse`, reuse `ScreenRunRequest` for the body. Per [contracts/compare-api.md](contracts/compare-api.md).
- [ ] T011 [P] [US1] Frontend surface `frontend/src/app/compare/midterm/page.tsx`: fetch the comparison, render four columns (momentum ON/OFF, value floor ON/OFF), each reusing existing candidate/gate/levels components and showing the strategy declaration; ensure the standing `data_as_of` + disclaimer shell renders. Neutral copy only (no directive verbs).
- [ ] T012 [P] [US1] Add a typed client for `POST /strategies/midterm-compare` in [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts) (with a Zod schema for `MidtermComparisonResponse`).
- [ ] T013 [P] [US1] Add a hardcoded entry card for the mid-term side-by-side comparison on [frontend/src/app/page.tsx](../../frontend/src/app/page.tsx) linking to `/compare/midterm` (home cards are hardcoded per project convention).

**Checkpoint**: US1 fully usable — the four-variant side-by-side screen works
end-to-end and is independently testable.

---

## Phase 4: User Story 2 — Export all four variants in one advisor prompt (Priority: P2)

**Goal**: One "Copy advisor prompt" yields a single deterministic prompt covering
all four variants.

**Independent test**: `POST /strategies/midterm-compare/advisor-prompt` returns
one prompt with four delimited sections (declaration/gates/levels/regime/
bias-check each), byte-identical on re-export, directive-gated.

### Tests (write first, must fail)

- [ ] T014 [P] [US2] In `backend/tests/agent/test_midterm_matrix_prompt.py`: `build_midterm_matrix_advisor_prompt` output has one shared task header, one shared regime block, and four clearly delimited variant sections; each section contains its strategy declaration with citations, the toggled parameter value, the run-config (gate ON/OFF), candidate blocks (or an explicit "no candidates" line), and that strategy's bias-check verdict (FR-012, SC-006). Per [contracts/advisor-prompt.schema.md](contracts/advisor-prompt.schema.md).
- [ ] T015 [P] [US2] Same file: byte-identical re-export on a fixed input (FR-013, SC-007); and directive gating — neutral framing when `directive=False`, take/pass/size framing only when `directive=True`, with citations/as-of/bias-check still present in both (FR-014).
- [ ] T016 [P] [US2] In `backend/tests/api/test_midterm_compare_api.py`: `POST /strategies/midterm-compare/advisor-prompt` returns `prompt`, `variant_count==4`, `personal_use_directive` reflecting the flag, `data_as_of`, `disclaimer`.

### Implementation

- [ ] T017 [US2] Implement `build_midterm_matrix_advisor_prompt(variants, *, regime, directive)` in [backend/src/agent/advisor_prompt.py](../../backend/src/agent/advisor_prompt.py), reusing `_strategy_context`, `_run_config_block`, `_candidate_summary_block`, and a combined honesty footer (factor shared bits out of `_batch_honesty_block` if needed). Emit the per-strategy bias-check line in each variant section. Pure function (no wall-clock). Per research Decision 4.
- [ ] T018 [US2] Add `POST /strategies/midterm-compare/advisor-prompt` in [backend/src/api/strategies.py](../../backend/src/api/strategies.py): run the matrix, call the new builder with `directive=personal_use_directive()`, return `MidtermComparePromptResponse`.
- [ ] T019 [P] [US2] Wire a single "Copy advisor prompt" button on `frontend/src/app/compare/midterm/page.tsx` (reuse [frontend/src/components/CopyAdvisorPrompt.tsx](../../frontend/src/components/CopyAdvisorPrompt.tsx)) hitting the new endpoint; add the typed client in [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts).

**Checkpoint**: US2 works on top of US1 — one prompt, all four variants,
deterministic, directive-gated.

---

## Phase 5: User Story 3 — Honest backtest context for the variants (Priority: P3)

**Goal**: Each strategy's bias-check verdict is visible in the comparison and the
export, and a failing verdict is never hidden.

**Independent test**: The comparison view and the prompt both show each strategy's
bias-check verdict; a failing survivorship verdict travels with both of that
strategy's variants.

### Tests (write first, must fail)

- [ ] T020 [P] [US3] In `backend/tests/screening/test_midterm_matrix.py`: both variants of each strategy carry the same `bias_check` (keyed by slug), and a strategy whose survivorship check FAILS reports `passed == False` on both its variants (FR-015, SC-009, research Decision 6).

### Implementation

- [ ] T021 [US3] Surface each variant's `bias_check` verdict in `frontend/src/app/compare/midterm/page.tsx` (e.g. an honesty chip/line per column), worded honestly when failing; no directive copy.
- [ ] T022 [US3] Confirm the prompt's combined honesty footer + per-variant bias-check lines state the failing survivorship caveat as applying to all variants (verify against T014/T015; extend assertions if the footer wording needs a dedicated check).

**Checkpoint**: All three user stories complete; honesty is consistent across
screen and export.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T023 [P] Extend [frontend/tests/e2e/no-directive-copy.spec.ts](../../frontend/tests/e2e/no-directive-copy.spec.ts) to cover `/compare/midterm` so the new surface is linted directive-clean (FR-010, SC-005).
- [ ] T024 [P] Add an `openapi`/contract note (or update the relevant API doc) for the two new endpoints to match [contracts/compare-api.md](contracts/compare-api.md).
- [ ] T025 Run the full gate from [quickstart.md](quickstart.md): `py -3.12 -m pytest backend/tests` green, `npm run test` (Vitest) green, `npx playwright test no-directive-copy` green; verify byte-identical determinism for both endpoints (`fc.exe` on two captures) and confirm the home-page entry card navigates to the working surface.
- [ ] T026 [P] Update [CLAUDE.md](../../CLAUDE.md) advisor pack if needed and the value/momentum claude-project notes only if the side-by-side changes any user-facing wording (no strategy-rule changes expected; skip if none).

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → **Foundational (T003–T005)** → user stories.
- **US1 (T006–T013)** depends on Foundational; it is the MVP and must land first.
- **US2 (T014–T019)** depends on US1 (needs the matrix results) + Foundational models.
- **US3 (T020–T022)** depends on US1 (and refines US2's footer); lightest story.
- **Polish (T023–T026)** depends on the stories it touches.
- **Story independence**: US1 is independently shippable. US2 adds the prompt on
  top. US3 is a thin honesty overlay; its backend assertion (T020) only needs the
  Foundational matrix, so T020 may be written alongside US1 tests.

## Parallel Execution Examples

- **Foundational**: T005 (models) ∥ T003/T004 once the engine seam is agreed.
- **US1 tests**: T006, T007, T008 in parallel (different files).
- **US1 frontend**: T011, T012, T013 in parallel (different files) after T010.
- **US2 tests**: T014, T015, T016 in parallel.
- **Polish**: T023, T024, T026 in parallel; T025 runs last (whole-suite gate).

## Implementation Strategy

- **MVP = US1** (T001–T013): the four-variant side-by-side screen. Demonstrable
  and valuable on its own.
- **Increment 2 = US2** (T014–T019): the single combined advisor prompt.
- **Increment 3 = US3** (T020–T022) + **Polish** (T023–T026): honesty overlay,
  lints, and the full determinism gate.
- Keep every step test-first; never change strategy rules/defaults/backtests.
