---
description: "Task list for Strategy Defect Detection & Output Integrity (Momentum Pilot)"
---

# Tasks: Strategy Defect Detection & Output Integrity (Momentum Pilot)

**Input**: Design documents from `/specs/008-momentum-data-integrity/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: INCLUDED. This feature is test-first by mandate — Constitution Principle IV (test-first for financial logic), FR-007/SC-001 (the seeded-defect suite is a blocking CI gate), and FR-012/FR-013/FR-015 (seam-adjustment math is financial logic requiring golden fixtures). Test tasks are written before the implementation they cover.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Web-app layout: `backend/src/`, `backend/tests/`, `frontend/src/`, `scripts/`

## Path Conventions

Existing repository layout (per plan.md "Structure Decision"): backend Python under `backend/src/` + `backend/tests/`, frontend under `frontend/src/`, on-demand scripts under `scripts/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding the new detector package and test homes so all later phases have a place to land.

- [X] T001 Create the strategy-agnostic detector package: `backend/src/screening/integrity/__init__.py` (empty package marker) and the test home `backend/tests/integrity/__init__.py`, per plan.md Project Structure.
- [X] T002 [P] Create the harness-only test fixtures directory `backend/tests/integrity/fixtures/` with a README noting the 2026-06-12 frozen snapshot is the canonical seeded-defect / cross-check input (quickstart §1, §4).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The output-contract type system, the additive wire-model fields, and the strategy-agnostic evaluation engine. Every user story reads these types.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Define `OutputContract`, `Invariant`, and `ContractViolation` dataclasses/Pydantic types in `backend/src/screening/integrity/contract.py` per data-model.md §1–§3 (fields: contract `strategy_slug`+`invariants`; invariant `name`/`family`/`severity`/`predicate`/`figure`/`message`; violation `invariant_name`/`family`/`figure`/`reason`/`severity`). Predicates are pure `Callable[[row, signals], bool]`.
- [X] T004 [P] Add additive wire fields in `backend/src/models/strategy.py` per data-model.md §4–§6: new `DataIntegrityWarning` model (`figure`/`rule`/`reason`), `Candidate.data_integrity_warnings: list[DataIntegrityWarning] = []` and `Candidate.data_suspect: bool = False` (leave existing soft-gate `warnings` untouched), and `Strategy.output_contract: OutputContract | None = None` (optional → registry still loads contract-less strategies).
- [X] T005 [P] [Test] Write the strategy-agnostic engine unit test FIRST in `backend/tests/integrity/test_engine.py`: a toy 2-invariant contract over a small DataFrame asserts `evaluate_contract` returns per-row `ContractViolation` lists + `data_suspect`, raises no warning on clean rows (SC-002), and never re-fetches/does I/O. Must FAIL before T006.
- [X] T006 Implement `evaluate_contract(results_df, contract) -> annotated_df` in `backend/src/screening/integrity/engine.py` (depends on T003): runs each invariant predicate per row, collects candidate-severity violations into `data_integrity_warnings`, sets `data_suspect`, and returns aggregate-severity violations separately. No per-strategy branching (FR-001). Makes T005 pass.

**Checkpoint**: Contract types, model fields, and the generic engine exist and are unit-tested — user stories can begin.

---

## Phase 3: User Story 1 - Every screen self-checks its output and surfaces any defect (Priority: P1) 🎯 MVP

**Goal**: Every live momentum screen validates its returned candidates against a declared output contract using deterministic no-network checks, flags any violation per-candidate, and demotes flagged names below all clean candidates.

**Independent Test**: On the frozen 2026-06-12 snapshot, corrupt one candidate's figure (inconsistent price/series, broken score, or a NaN). Re-run the screen: that candidate carries a specific data-integrity warning naming the violated invariant and sorts below all clean candidates; clean candidates carry no warning; the run does not crash; a re-run yields an identical warning set.

### Tests for User Story 1 (write first, ensure they FAIL) ⚠️

- [X] T007 [P] [US1] Invariant-builder unit tests in `backend/tests/integrity/test_invariants.py`: one case per family — coherence (`dist_to_high==(52w_high−close)/close`, `entry==close`), gate satisfaction at the stated parameter, score reproduction within tolerance, level sanity (`0<stop_loss<entry<take_profit` + R-multiple), value-domain (NaN/inf/zero/negative + `return_12_1` plausibility bound), series integrity (monotonic-unique dates, unexplained single-session jump). Each asserts pass on clean input and a fired violation on a corrupted input (FR-003, FR-005).
- [X] T008 [P] [US1] Momentum contract test in `backend/tests/strategies/test_momentum_contract.py`: load `midterm_52w_high_momentum.OUTPUT_CONTRACT` and assert it declares all six invariant families of FR-003 with correct severities (candidate vs aggregate).
- [X] T009 [P] [US1] Engine-wiring test in `backend/tests/screening/test_integrity_wiring.py`: after a screen, a corrupted candidate gets `data_suspect=True` + a populated `data_integrity_warnings`; the result is sorted `["data_suspect","warning_count","score","ticker"]` so a flagged high-score name (BELFB-like at #2) sorts below every clean name (FR-018); an aggregate data note records the flagged/corrected count (FR-004, US4-AC4); and screening twice over the same snapshot yields an identical figure set AND identical warning set (FR-024/SC-005). Asserts no network call on the live path.
- [X] T010 [P] [US1] Value-backstop equivalence test in `backend/tests/strategies/test_value_backstop_contract.py`: the value strategy's implausible-yield drop, re-expressed as an `OutputContract`, runs through the same `evaluate_contract` engine with no per-strategy engine code and produces behaviour consistent with the existing backstop (FR-006/SC-009), with the value backtest baseline unchanged (SC-010).

### Implementation for User Story 1

- [X] T011 [US1] Implement reusable invariant builders in `backend/src/screening/integrity/invariants.py` (depends on T003): `coherence_*`, `gate_satisfied`, `score_reproduces`, `level_sanity`, `value_domain`, `series_integrity` factory functions returning `Invariant`s with `figure`/`message`/`severity`. Series/value-domain invariants read only precomputed `signals` columns (Decision 7), never re-fetch. Makes T007 pass.
- [X] T012 [US1] Declare `OUTPUT_CONTRACT` on `backend/src/strategies/midterm_52w_high_momentum.py` (depends on T011) composing the six families from contracts/momentum-contract.md. No change to `rules()`, defaults, citation, or `REGIME_FAVORABILITY` (FR-023). Makes T008 pass.
- [X] T013 [US1] Wire the detector into the live screen in `backend/src/screening/engine.py::_screen_from_universe` (depends on T006, T012): after `strategy.rules(universe)` call `evaluate_contract`, attach `data_integrity_warnings` + `data_suspect` to each `Candidate`, extend the sort key to `["data_suspect","warning_count","score","ticker"]` (FR-018), and append an aggregate data note of how many names were flagged/corrected (FR-004). Deterministic, no network (FR-002/FR-024). Makes T009 pass.
- [X] T014 [US1] Re-express the value strategy's implausibility backstop as an `OUTPUT_CONTRACT` in `backend/src/strategies/midterm_value_composite.py` (depends on T011) — same engine, no behaviour or baseline change (FR-006). Makes T010 pass.

**Checkpoint**: Contract types, model fields, and the generic engine exist and are unit-tested — user stories can begin.

---

## Phase 4: User Story 2 - Robustness proven by an offline harness (seeded defects + independent cross-check) (Priority: P1)

**Goal**: An offline harness injects synthetic defect classes (100% must be caught — blocking CI gate) and cross-checks top-N candidate prices/52w-highs against a free-tier independent vendor outside the pipeline (on-demand, non-blocking), emitting a classified report.

**Independent Test**: Run the harness on the 2026-06-12 snapshot. Per seeded class it reports flagged=yes (100% required); per top-N candidate it reports screener price, independent price, divergence, and a verdict — BELFB→DIVERGES_AND_FLAGGED, JBHT/CW→AGREES, missing source→UNVERIFIED (no crash). Re-run: screener side of every verdict identical, only `independent_fetch_at` varies.

### Tests for User Story 2 (write first, ensure they FAIL) ⚠️

- [X] T015 [P] [US2] **Seeded-defect suite (the blocking CI gate)** in `backend/tests/integrity/test_seeded_defects.py`: for each `SeededDefect` class (corrupted_price, broken_score, stale_but_fresh, nan_field, inconsistent_dist_to_high, seam_discontinuity, share_class_swap) inject the fault into a frozen-snapshot copy, run the contract, and assert the expected invariant family fires (SC-001 = 100%); assert the un-corrupted control copy raises zero warnings (SC-002). A miss is a failing test.
- [X] T016 [P] [US2] Independent-provider unit test in `backend/tests/integrity/test_independent_quote.py`: with a mocked HTTP layer, assert Finnhub `/quote`+`/stock/metric` parse to price+52w-high, Alpha Vantage `GLOBAL_QUOTE` fallback parses, a missing/unset key or network error yields a clean "unavailable" result (→ UNVERIFIED, no crash, FR-009), and the key is read from `SCREENER_INDEPENDENT_QUOTE_API_KEY` only (never read from a file).
- [X] T017 [P] [US2] Cross-check verdict test in `backend/tests/integrity/test_cross_check.py`: given screener vs independent figure pairs, assert verdict assignment AGREES(<10%)/DIVERGES_AND_FLAGGED(≥10%+warning)/DIVERGES_UNFLAGGED(≥10%+no warning→FAILURE)/UNVERIFIED/STALE, and that genuine staleness is classified STALE not DIVERGES_UNFLAGGED (FR-010/FR-011/SC-004).

### Implementation for User Story 2

- [X] T018 [P] [US2] Implement the harness-only `IndependentQuoteProvider` interface + Finnhub primary and Alpha Vantage fallback adapters in `backend/src/data/independent_quote.py` (Decision 5). Process-local key, never written to file (FR-009); imported only by the harness so no live path can make a network call. Makes T016 pass.
- [X] T019 [US2] Implement the offline harness in `backend/src/screening/integrity/harness.py` (depends on T006, T012, T018): (a) `SeededDefect` injection over a frozen snapshot asserting 100% detection; (b) top-N (≤10) cross-check producing `CrossCheckVerdict` rows (data-model.md §9–§10) distinguishing STALE from DIVERGES_UNFLAGGED; (c) a classified, human-readable report matching contracts/harness-report.schema.md with `independent_fetch_at` recorded. Makes T015/T017 pass.
- [X] T020 [US2] Add the on-demand runner `scripts/run_integrity_harness.py` (depends on T019): `--as-of 2026-06-12 --out <report.md>`, runs seeded test + cross-check, writes the report. NOT a CI gate; a network outage / UNVERIFIED reports but exits 0 for the cross-check section (FR-007, Decision 6), while the seeded section is what CI runs via pytest (T015).

**Checkpoint**: Robustness is provable — `pytest tests/integrity` gates CI on 100% seeded detection; the on-demand harness cross-checks reality and resolves BELFB to DIVERGES_AND_FLAGGED.

---

## Phase 5: User Story 3 - Momentum figures computed correctly so clean names are not falsely flagged (Priority: P2)

**Goal**: Remediate the known momentum data defects so correct names compute coherent figures: lookback figures on a split+dividend-adjusted series, the cross-source seam back-adjusted onto one basis (or flagged), no cross-share-class joins, corporate actions sourced from provider adjustment data. This feeds the series-integrity signals the US1 contract reads.

**Independent Test**: Re-run the momentum screen on 2026-06-12. BELFB's `return_12_1` is no longer the spurious +221%; its `close`/`52w_high`/`return_12_1` derive from one adjustment-consistent series across the full window; BELFB reconciles within 10% of its independent price OR carries a warning; clean names compute without false flags.

### Tests for User Story 3 (write first, ensure they FAIL) ⚠️

- [x] T021 [P] [US3] **Golden-fixture test for the seam back-adjustment helper** in `backend/tests/indicators/test_seam_adjust.py` (Constitution IV — financial logic first): a stitched Stooq+overlay fixture with a split at the seam yields one adjustment-consistent series via the median 5-day-overlap factor; an empty/unstable-overlap fixture returns `seam_consistent=False` (no silent correction, FR-013); a single-source fixture returns factor 1.0.
- [x] T022 [P] [US3] Snapshot series-integrity-signals test in `backend/tests/screening/test_snapshot_signals.py`: `_compute_snapshot_rows` emits the data-model.md §8 columns (`series_dates_ok`, `series_max_session_move`, `seam_consistent`, `seam_factor`, `corporate_action_in_window`, `adj_close_basis_used`, `share_class_consistent`) for a fixture ticker, computed once with no extra network pass (Decision 7).
- [x] T023 [P] [US3] Adjusted-series + share-class + corporate-action test in `backend/tests/screening/test_momentum_correctness.py`: `return_12_1`/`52w_high` compute from the adjusted series while displayed `entry`==latest raw close==latest `adj_close` (FR-012); a split inside the window creates no artificial jump/inflated high and is NOT flagged because the action is known (FR-015); a BELFA/BELFB cross-class join is detected and `share_class_consistent=False` (FR-014).

### Implementation for User Story 3

- [x] T024 [P] [US3] Stop dropping `adj_close`: add it to `_OVERLAY_COLUMNS` so it survives the stitch in `backend/src/screening/engine.py` (Decision 2 step 1) — and/or `backend/src/data/prices_store.py` where overlay columns are defined.
- [x] T025 [P] [US3] Implement the seam back-adjustment helper in `backend/src/data/prices.py` (or a new `backend/src/indicators/seam_adjust.py`): per-ticker median factor `f = yfinance_adj_close/stooq_close` over the 5-day overlap, back-adjust the Stooq segment onto the overlay basis, with the empty/unstable/Stooq-only guardrail returning `seam_consistent=False` (Decision 2 steps 2–3). Makes T021 pass.
- [x] T026 [US3] Compute the §8 series-integrity signals inside `_compute_snapshot_rows` in `backend/src/screening/engine.py` (depends on T024, T025): dates monotonic+unique, max single-session move, seam flag+factor, corporate-action-in-window (from the `adj_close/close` ratio curve, Decision 3), `adj_close_basis_used`, `share_class_consistent`. Attached as row columns; no second pass (Decision 7). Makes T022 pass.
- [x] T027 [US3] Derive `return_12_1` and `52w_high` from the adjusted series while keeping displayed `entry`/`close` as the latest raw close in `_compute_snapshot_rows` (depends on T026), and resolve price-series ticker vs fundamentals ticker to one share class (no cross-class join, FR-014). Makes T023 pass. No rule/default/baseline change (FR-023/SC-010).

---

## Phase 6: User Story 4 - Detected defects surface loudly, are demoted, and propagate to exports (Priority: P2)

**Goal**: A flagged candidate stays listed with a prominent, specific, actionable per-candidate warning, is ranked below all clean candidates (done in US1 sort), the warning travels verbatim into the advisor-prompt export, the result's data notes honestly record the flag/correction count, and the UI shows a distinct integrity badge.

**Independent Test**: Replay a BELFB-like bad bar. The candidate appears with a "price may be stale or erroneous — verify before acting" warning naming the suspect figure, sits below all clean candidates regardless of raw score, its advisor-prompt export contains the same warning verbatim, and the UI shows a distinct data-integrity badge. A clean candidate has none of this.

### Tests for User Story 4 (write first, ensure they FAIL) ⚠️

- [X] T028 [P] [US4] Advisor-prompt propagation test in `backend/tests/agent/test_advisor_integrity.py`: for a flagged candidate the per-candidate block and the honesty footer include its `data_integrity_warning.reason` verbatim (FR-019/SC-008); a clean candidate's prompt has none; the builder stays a pure deterministic function and the directive flag stays OFF by default.
- [X] T029 [P] [US4] Frontend e2e in `frontend/tests/e2e/integrity-badge.spec.ts`: a flagged candidate row shows a prominent data-integrity badge **distinct** from the existing soft-gate badge; clean rows show none; the no-directive-language lint still passes.

### Implementation for User Story 4

- [X] T030 [P] [US4] Include each candidate's data-integrity warning verbatim in the per-candidate blocks and honesty footer in `backend/src/agent/advisor_prompt.py` (FR-019). Makes T028 pass.
- [X] T031 [P] [US4] Extend the `Candidate` Zod schema in `frontend/src/lib/api.ts` with `data_integrity_warnings` + `data_suspect` (additive, optional).
- [X] T032 [US4] Render a prominent, distinct data-integrity badge (separate from the soft-gate badge) naming the suspect figure in `frontend/src/components/CandidateRow.tsx` (depends on T031) (FR-017). Makes T029 pass.
- [X] T033 [US4] Surface the integrity warning on the candidate detail view `frontend/src/app/candidate/[ticker]/page.tsx` (depends on T031) (US4-AC1).
- [X] T034 [US4] Confirm the aggregate "flagged/corrected N names" data note renders in the screen result data-notes surface (it is produced in T013) — verify wiring through to the frontend data-notes display (US4-AC4).

**Checkpoint**: A defect cannot be silently acted on — it is loud in the UI, demoted, and carried verbatim into any shared advisor prompt.

---

## Phase 7: User Story 5 - Value-composite momentum sign visibility (Priority: P3)

**Goal**: Each near-high momentum candidate prominently surfaces its 12-1 trailing momentum value and sign so a "near the high but falling" name (IOSP −9.8%) is self-evidently distinguishable from a rising one. No rule changes; no momentum-floor gate (FR-021).

**Independent Test**: List a near-high candidate with negative 12-1 momentum; its 12-1 value and sign are visible and it is not excluded. Two near-high candidates (one rising, one falling) keep their existing score ordering.

### Tests for User Story 5 (write first, ensure they FAIL) ⚠️

- [X] T035 [P] [US5] Frontend e2e in `frontend/tests/e2e/momentum-sign.spec.ts`: a candidate with negative 12-1 momentum renders the value with its sign prominently (a reviewer identifies a negative-momentum near-high name from the row alone, SC-011); a clean rising name shows a positive value; no directive language introduced.
- [X] T036 [P] [US5] Ordering-unchanged test in `backend/tests/screening/test_momentum_rank_only.py`: two near-high candidates (one rising, one falling, both clean) keep the existing score-based order — no momentum-floor gate added (FR-021/US5-AC2).

### Implementation for User Story 5

- [X] T037 [US5] Surface the 12-1 momentum value **with sign** prominently in `frontend/src/components/CandidateRow.tsx` (FR-020); ensure `return_12_1` is exposed by the `Candidate` schema in `frontend/src/lib/api.ts` if not already. Makes T035 pass.

**Checkpoint**: The rank-only nature of momentum is self-evident on every candidate; no gating behaviour changed.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Performance gate, baseline-stability proof, and the operator's "drive the live app" validation.

- [ ] T038 [P] Performance check: assert live contract checks add < 5% to total screen runtime (SC-005) — a timing test in `backend/tests/screening/test_integrity_perf.py` or a measured note, full-universe screen still within p95 ≤ 10 s.
- [X] T039 [P] Backtest-baseline stability proof: re-run the committed backtest summary tests for `midterm_52w_high_momentum` and `midterm_value_composite` and confirm byte-stable metrics versus the pre-feature baseline (SC-010/FR-023).
- [ ] T040 Run the full quickstart.md (§1 suites, §2 live BELFB inspection, §3 advisor propagation, §4 on-demand harness, §5 frontend build + Playwright) and confirm SC-001…SC-011 all hold on the 2026-06-12 snapshot.
- [X] T041 [P] Update `claude-project/` advisor pack and the value/EDGAR memory pointers if any strategy-facing surface changed (per the "Claude Project advisor pack" / memory re-sync note); confirm the CLAUDE.md SPECKIT pointer already targets this plan.
