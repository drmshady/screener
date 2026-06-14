---

description: "Task list for 005-value-midterm-strategy"
---

# Tasks: Value-Based Mid-Term Strategy

**Input**: Design documents from `/specs/005-value-midterm-strategy/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED (not optional) for this feature. The constitution's Principle
IV (Test-First for Financial Logic) mandates fixture-anchored tests, written and
failing **before** implementation, for every indicator (valuation multiples,
F-Score components) and every screening rule. Test tasks below are therefore
first-class and ordered before the code they cover.

**Organization**: Tasks are grouped by user story. **US1 is the MVP** and
produces the working strategy module; US2 (discovery/analysis/compare/export) and
US3 (backtest) build on US1's strategy file — this dependency is called out
explicitly rather than pretended away.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1 / US2 / US3 (setup, foundational, polish carry no story label)

## Path Conventions

Web app: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`.
All paths below are repository-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the branch and the frozen data snapshot the strategy reads.

- [X] T001 Confirm branch `005-value-midterm-strategy` is checked out and `specs/005-value-midterm-strategy/` design docs are present
- [X] T002 Verify the frozen data snapshot exists: `backend/data/prices/stooq_parquet/`, `backend/data/edgar_cache/`, and the momentum baseline `backend/data/backtests/midterm_52w_high_momentum.json` (used as the structural template); note any missing inputs in the PR description

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared data + indicator + model plumbing every user story needs.
None of US1/US2/US3 can begin until this phase is complete.

**⚠️ CRITICAL**: Indicator and fundamentals tests are written and MUST FAIL before
their implementations land (Principle IV).

### Indicators (test-first)

- [X] T003 [P] Write failing golden-fixture tests for valuation multiples in `backend/tests/indicators/test_valuation.py` — book/market, earnings/cash-flow/sales yields (positive, negative-earnings, negative-book-value firms) and `value_composite` over {4, 2, 0} present members; assert negatives sort as least-cheap (contracts/indicators.md, data-model §2)
- [X] T004 [P] Write failing golden-fixture tests for the Piotroski F-Score in `backend/tests/indicators/test_piotroski.py` — a known 9-signal total, a firm missing two inputs (reduced `n_evaluable`, no point awarded on missing data) (contracts/indicators.md, data-model §3)
- [X] T005 [P] Implement `backend/src/indicators/valuation.py` (pure: `book_to_market`, `earnings_yield`, `cashflow_yield`, `sales_yield`, `value_composite`) until T003 passes; `market_cap <= 0/None` → all yields `None`, negatives not clamped
- [X] T006 [P] Implement `backend/src/indicators/piotroski.py` (pure: `f_score(current, prior) -> (score, n_evaluable, per_signal_map)`) until T004 passes; missing-input signal scores 0 and decrements `n_evaluable`

### Point-in-time fundamentals (test-first)

- [X] T007 Write failing tests for point-in-time value fundamentals in `backend/tests/data/test_value_metrics_as_of.py` — only filings filed on/before `as_of` are visible (no look-ahead), TTM net income/CF/revenue, prior-year values for the F-Score deltas, and missing-input → `None` (never fabricated) (research D8, data-model §2/§3)
- [X] T008 Add `value_metrics_as_of(ticker, as_of, payload)` to `backend/src/data/fundamentals.py` (reusing `_latest_as_of` / `_annual_*_as_of` patterns) until T007 passes: common equity, TTM net income, operating CF, TTM revenue, shares outstanding, current assets/liabilities, long-term debt + their prior-year values
- [X] T009 Extend `NEEDED_TAGS` in `backend/src/backtests/runner.py` with the concepts T008 requires (`NetIncomeLoss`, `EntityCommonStockSharesOutstanding`/`CommonStockSharesOutstanding`, `AssetsCurrent`, `LiabilitiesCurrent`, `LongTermDebtNoncurrent` + documented fallbacks) so the slim EDGAR cache carries them for both the live screen and the backtest

### Snapshot, models, and threshold plumbing

- [X] T010 Thread the new value columns through the universe snapshot in `backend/src/screening/engine.py` — populate `market_cap`, `book_to_market`, `earnings_yield`, `cashflow_yield`, `sales_yield`, `value_composite`, `value_metrics_count`, and the nine F-Score signals + `f_score`/`f_score_evaluable` in `_compute_snapshot_rows`, sourced via `_edgar_profiles` calling `value_metrics_as_of`; missing keys default to `None` (mirror how `gp_to_assets`/`asset_growth` are threaded)
- [X] T011 [P] Add the additive optional value fields to `Candidate` and `AnalyzeResponse` in `backend/src/models/strategy.py` (`value_composite`, `book_to_market`, `earnings_yield`, `cashflow_yield`, `sales_yield`, `f_score`, `f_score_evaluable`; all default `None`) (contracts/api-fields.md, data-model §4)
- [X] T012 [P] Extend `backend/src/strategies/_helpers/reference_thresholds.py` (and the `refresh_reference_thresholds` caller in `engine.py`) to compute + cache the value-composite percentile cut alongside the existing gp/asset-growth thresholds, so a name's cheapness verdict is stable across the screen, single-ticker analysis, and candidate detail (research D3)

**Checkpoint**: Indicators green, point-in-time value fundamentals flow into the
snapshot, models carry the optional fields, and the cross-sectional threshold
cache exists. User stories can now begin.

---

## Phase 3: User Story 1 — Screen for under-priced, financially healthy candidates (Priority: P1) 🎯 MVP

**Goal**: A deterministic, value-ranked, F-Score-gated, sector-aware candidate
list with full per-gate accounting, levels, and the live declaration.

**Independent Test**: Run `midterm_value_composite` on the frozen snapshot →
every listed name clears the cheapness + F-Score gates, each carries a per-gate
pass/skip breakdown, the response has `data_as_of` + `disclaimer`, and a second
identical run yields byte-identical candidates/ranking/levels.

### Tests for User Story 1 (write first, ensure they FAIL) ⚠️

- [X] T013 [P] [US1] Write failing unit tests for the value-composite helper in `backend/tests/strategies/test_value_composite_helper.py` — cross-sectional percentile-rank composite, within-sector ranking, and `value_metrics_count` accounting (research D1/D4)
- [X] T014 [P] [US1] Write failing strategy unit tests in `backend/tests/strategies/test_midterm_value_composite.py` covering: F-Score gate excludes `f_score < min_f_score`; partial-coverage name reported `skipped` not false-pass; composite ranking order; within-sector cap via `rank_within_sector`; entry/stop/take-profit derivation; negative-book/negative-earnings names not top-ranked (FR-015); determinism on a fixed frame (SC-002); honest `gates_applied`/`gates_skipped` (FR-008); empty-universe returns empty with notes
- [X] T015 [P] [US1] Write a failing registry/declaration test in `backend/tests/strategies/test_value_strategy_registration.py` — the module declares NAME/CITATION/TIMEFRAME/PARAMETERS/REGIME_FAVORABILITY/MODIFICATIONS (each modification cited) and loads; `enabled_by_default` is `False` without a passing backtest (FR-002, contracts/strategy-declaration.md)

### Implementation for User Story 1

- [X] T016 [US1] Implement `backend/src/strategies/_helpers/value_composite.py` (cross-sectional composite scoring + within-sector percentile ranking) until T013 passes
- [X] T017 [US1] Implement `backend/src/strategies/midterm_value_composite.py` until T014/T015 pass — declaration (data-model §1), `rules(universe_df)` (contracts/strategy-declaration.md: composite rank → F-Score gate → leverage sanity → within-sector cap → levels), and `evaluate(row, context)` + `prepare_universe_gates(df)` helpers; reuse `_gate_mode()` hard/tiered switch, `rank_within_sector`, and the momentum level/stop machinery; register the `Strategy` in the registry
- [X] T018 [US1] Populate the new `Candidate` value fields (T011) in `backend/src/screening/engine.py`'s candidate assembly from the `rules()` output columns; add a value-specific fundamentals-coverage `data_note` (how many screened names lacked the value inputs), mirroring the existing quality-coverage note
- [X] T019 [P] [US1] Verify/extend the screen page `frontend/src/app/screen/[strategy]/page.tsx` (and the candidate card) to render the value diagnostics (composite, F-Score, yields) and the value `gate_results`; no new directive copy
- [X] T020 [US1] Add a screen integration test in `backend/tests/integration/test_value_screen.py` — `run_strategy("midterm_value_composite")` returns gated, ranked candidates with value fields, `data_as_of`, and `disclaimer` (SC-001/003/004/007)

**Checkpoint**: US1 is a fully functional, independently testable MVP — the value
screen works end-to-end on the frozen snapshot.

---

## Phase 4: User Story 2 — Discover, analyze, and compare the value strategy (Priority: P2)

**Goal**: The strategy appears in the listing with full metadata, supports
single-ticker analysis against the live universe, is comparable to momentum (003),
and is exportable via the advisor prompt (004).

**Independent Test**: The strategy shows in `/strategies` with declaration
metadata; a single-ticker `/analyze` returns value gate evaluations computed
against the universe (not skipped); it can be selected beside momentum in the
comparison view; and an advisor prompt for it carries the value citations +
diagnostics + honesty block with zero directive language (flag off).

**Depends on**: US1 (the `midterm_value_composite` strategy module must exist).

### Tests for User Story 2 (write first, ensure they FAIL) ⚠️

- [X] T021 [P] [US2] Write a failing single-ticker analysis test in `backend/tests/api/test_analyze_value.py` — `/analyze` for the value strategy computes the composite/F-Score gates against the live universe distribution (cross-sectional gates not silently skipped) and returns the value fields (FR-009, SC-007)
- [X] T022 [P] [US2] Write a failing listing test in `backend/tests/api/test_strategies_listing_value.py` — `/strategies` and `/strategies/{slug}` expose the value strategy's name, citation, timeframe, holding period, regime favorability, parameters, and each modification's citation (FR-010)
- [X] T023 [P] [US2] Write a failing advisor-prompt test in `backend/tests/agent/test_advisor_prompt_value.py` — building a prompt for `midterm_value_composite` reads its declaration + its own backtest artifact path, includes the Fama-French/LSV + Piotroski citations and the value diagnostics, ends with the honesty block, and (flag off) contains no directive words (FR-016)

### Implementation for User Story 2

- [X] T024 [US2] Wire single-ticker analysis for the value strategy in `backend/src/api/analyze.py` using the strategy's `prepare_universe_gates`/`evaluate` so percentile/F-Score gates evaluate against the universe; surface the value fields in `AnalyzeResponse` (until T021 passes)
- [X] T025 [US2] Generalize `backend/src/agent/advisor_prompt.py` (until T023 passes): parameterize `load_survivorship_status` backtest path by strategy slug (default stays momentum for back-compat) and extend `_diagnostics_lines` to emit value fields (composite, F-Score, the four yields) when present; replace the hardcoded momentum ranking sentence in `_strategy_context` with a strategy-derived/generic phrasing
- [X] T026 [P] [US2] Verify the strategy-comparison surface (003) includes `midterm_value_composite` beside momentum in `frontend/src/app/` (comparison page) and renders its declaration/metrics; data-driven, confirm no special-casing excludes it (SC-008)
- [X] T027 [P] [US2] Verify single-ticker analysis + advisor-prompt buttons render the value strategy on `frontend/src/app/analyze/page.tsx` and `frontend/src/app/candidate/[ticker]/page.tsx` (reuse existing `CopyAdvisorPrompt`/`CopyScreenAdvisorPrompt`)

**Checkpoint**: US1 and US2 both work independently; the value strategy is
discoverable, analyzable, comparable, and exportable.

---

## Phase 5: User Story 3 — Trust the honest, reproducible backtest (Priority: P3)

**Goal**: A walk-forward backtest spanning 2008–2024 with per-year metrics and an
honest, visible `bias_check` (survivorship FAIL surfaced; pre-2011 XBRL sparsity
noted), gating `enabled_by_default`.

**Independent Test**: `/strategies/midterm_value_composite/backtest` returns
≥15 yearly rows incl. 2008–2009, `survivorship_bias.passed=false`, and
`coverage_notes` explaining empty early years; the strategy stays
`enabled_by_default=false` unless an explicit operator override is set.

**Depends on**: US1 (strategy module) + Foundational (T009 NEEDED_TAGS).

### Tests for User Story 3 (write first, ensure they FAIL) ⚠️

- [X] T028 [P] [US3] Write a failing runner-branch test in `backend/tests/backtests/test_runner_value.py` — `run_backtest("midterm_value_composite", ...)` sets `uses_fundamentals=True`, builds a value candidate pool (liquid, ≥252-bar; no near-high pre-filter), produces per-year metric rows, and emits an honest `bias_check` (survivorship false on a Stooq-like frame) (research D9)

### Implementation for User Story 3

- [X] T029 [US3] Add the `midterm_value_composite` branch to `_candidate_pool` in `backend/src/backtests/runner.py` (liquid universe pool, ranking deferred to `rules()`), set `uses_fundamentals` True for the slug, and ensure the value fundamentals flow into `_build_snapshot` via `value_metrics_as_of` (until T028 passes)
- [X] T030 [US3] Run the backtest: `python -m src.backtests.runner --strategy midterm_value_composite --start 2008-01-01 --end 2024-12-31`; commit `backend/data/backtests/midterm_value_composite.json` + `backend/backtests/midterm_value_composite/` (FR-011, SC-006)
- [X] T031 [US3] Confirm the registry behavior on the committed artifact: `_window_meets_floor` true (2008→2024) but `enabled_by_default` stays `False` while survivorship fails; add the documented `SCREENER_*` operator-override path mirroring momentum's `OPERATOR_TREAT_AS_VALID` in `midterm_value_composite.py`, with a code comment explaining the honest survivorship caveat
- [X] T032 [P] [US3] Verify the backtest UI surface renders the value strategy's per-year metrics + bias-check honestly (data-driven; confirm no momentum-specific assumption breaks rendering)

**Checkpoint**: All three stories are independently functional; the backtest is
honest and reproducible.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T033 [P] Update `frontend/tests/e2e/no-directive-copy.spec.ts` to cover the value strategy's screen/analyze/compare surfaces (zero directive language; reuse the 004 scoped personal-use-preview exemption) (FR-013, SC-005)
- [X] T034 [P] Update docs: add the value strategy to the v1 strategy slate note in `CLAUDE.md` and cross-link `claude-project/04-workflow-and-prompts.md` if it enumerates strategies
- [X] T035 Run the full backend suite `cd backend && python -m pytest -q` and the frontend `npm run test` + `npx playwright test`; fix regressions
- [X] T036 Execute `specs/005-value-midterm-strategy/quickstart.md` end-to-end (steps 1–10) and confirm every "Definition of done" bullet, including the determinism diff (SC-002) and the p95 ≤ 10s screen budget

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; **blocks all user stories**. Within it: indicators (T003–T006) and fundamentals (T007–T009) are test-first pairs; T010 depends on T006+T008; T012 depends on T010.
- **US1 (Phase 3)**: depends on Foundational. The MVP.
- **US2 (Phase 4)**: depends on Foundational **and US1** (needs the strategy module).
- **US3 (Phase 5)**: depends on Foundational (esp. T009) **and US1** (strategy module).
- **Polish (Phase 6)**: depends on the desired user stories being complete.

### Within Each User Story

- Tests (T013–T015, T021–T023, T028) are written and FAIL before their implementation.
- Helpers/models before the strategy; strategy before engine wiring; backend before the frontend verification tasks.

### Parallel Opportunities

- T003/T004 (indicator tests) in parallel; then T005/T006 (their impls) in parallel.
- T011 and T012 in parallel after T010.
- US1 test-writing T013/T014/T015 in parallel.
- US2 tests T021/T022/T023 in parallel; frontend T026/T027 in parallel.
- Once Foundational + US1 land, US2 and US3 can proceed in parallel (different files).

---

## Parallel Example: Foundational indicators (test-first)

```bash
# Write both failing indicator test suites together:
Task: "Golden-fixture tests in backend/tests/indicators/test_valuation.py"
Task: "Golden-fixture tests in backend/tests/indicators/test_piotroski.py"

# Then implement both pure modules together:
Task: "Implement backend/src/indicators/valuation.py"
Task: "Implement backend/src/indicators/piotroski.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational (indicators green, value fundamentals
   flow into the snapshot).
2. Phase 3 US1 → working, deterministic value screen.
3. **STOP and VALIDATE**: run the US1 independent test on the frozen snapshot.

### Incremental Delivery

1. Foundational → US1 (MVP: the value screen).
2. US2 → discoverable/analyzable/comparable/exportable.
3. US3 → honest reproducible backtest; flip enablement only via the documented
   operator override.

---

## Notes

- [P] = different files, no incomplete dependencies.
- Principle IV is non-negotiable: indicator and rules tests precede their code and
  must fail first.
- Principle III: the survivorship FAIL and pre-2011 sparsity are surfaced, never
  hidden; the strategy ships disabled by default.
- Commit after each task or logical group; keep the momentum baseline backtest
  artifact untouched (FR: this feature adds a strategy, it does not modify momentum).
