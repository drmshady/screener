---
description: "Task list for feature 007 — Value Strategy Data Coverage & Correctness Hardening"
---

# Tasks: Value Strategy — Data Coverage & Correctness Hardening

**Input**: Design documents from `/specs/007-value-coverage-hardening/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/
**Tests**: INCLUDED — the spec mandates test-first for all financial-logic
changes (FR-014, Constitution Principle IV). Test tasks precede their
implementation and MUST fail first.

**Branch note**: target branch is `007-value-coverage-hardening`. The repo is
currently on `006-midterm-sidebyside-compare`; create/switch the 007 branch
before implementing (operator's git call).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (coverage), US2 (correctness), US3 (disclosure)

## Path Conventions

Web app: `backend/src/`, `backend/scripts/`, `backend/tests/`, `frontend/src/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Skeletons so imports resolve and the new surfaces exist.

- [ ] T001 Create stub module `backend/src/data/instruments.py` with the `InstrumentType` enum and a `classify(ticker, payload)` signature returning `unknown`, plus empty test files `backend/tests/data/test_instruments.py`, `backend/tests/data/test_refresh_edgar_coverage.py`, `backend/tests/screening/test_value_staleness_split.py`, `backend/tests/screening/test_value_coverage_guard.py`.
- [ ] T002 Create stub CLI `backend/scripts/refresh_edgar_coverage.py` with argparse per `contracts/refresh-coverage.md` (`--scope/--limit/--dry-run/--report`) that classifies and prints a CoverageReport but fetches nothing yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The instrument classifier + coverage data structures that BOTH the
refresh (US1) and the engine non-equity filter (US1) depend on.

**⚠️ CRITICAL**: US1 cannot complete until this phase is done.

- [ ] T003 [P] Write golden-fixture tests in `backend/tests/data/test_instruments.py` for `classify`: preferred suffix (`ALL_B`, `AHT_D`, `APO_A`), ADR (`AEG`, `ABVEF`), closed-end fund by SIC 6726 (`ACP`, `ADX`), common equity (`AAPL`, `CTRA`), and `unknown` fallback. MUST fail first.
- [ ] T004 Implement `classify(ticker, payload) -> InstrumentType` in `backend/src/data/instruments.py` (ticker-suffix + SIC + facts-presence layering per research D2); make T003 pass.
- [ ] T005 [P] Add `CacheEntryClassification` and `CoverageReport` dataclasses (per data-model.md) in `backend/src/data/instruments.py` (or a sibling `coverage.py`), with the `state`/`action` derivation rule.

**Checkpoint**: classifier + coverage types ready.

---

## Phase 3: User Story 1 — Complete, current data (Priority: P1) 🎯 MVP

**Goal**: Re-fetch failed-stub real filers, filter non-equity instruments from the
value universe, and stop branding stale-local-feed names as "halted."

**Independent Test**: Run the refresh + ingest, re-run the live value screen; the
"no value yield" count collapses toward the non-equity floor and AMWD/CTRA/EXAS/
HOLX return as eligible while only CTLP stays excluded.

### Tests for User Story 1 ⚠️ (write first, must fail)

- [ ] T006 [P] [US1] Tests in `backend/tests/data/test_refresh_edgar_coverage.py`: classification buckets the screened set correctly; `action=refetch` only for fixable_stub/partial + common_equity/unknown + resolvable CIK; **write-if-better** never replaces a complete payload with a stub; a name with no CIK is skipped; CoverageReport `counts_before/after` populated.
- [ ] T007 [P] [US1] Tests in `backend/tests/screening/test_value_staleness_split.py`: a name stale only locally (peers fresh, still in universe) yields the "stale local data — run ingest" note and is NOT dropped as halted; a name stale beyond the delist horizon / absent from the universe is labeled halted/delisted; an all-names-stale store emits one store-level warning.

### Implementation for User Story 1

- [ ] T008 [US1] Implement the re-fetch loop in `backend/scripts/refresh_edgar_coverage.py`: throttle ≤8 req/s + backoff, descriptive UA, no API key, resume-safe, write-if-better, schema-v3 payloads with `dei:EntityCommonStockSharesOutstanding` + value `NEEDED_TAGS`; emit CoverageReport. Make T006 pass.
- [ ] T009 [P] [US1] Update `backend/scripts/build_edgar_cache.py` to write schema-v3 (dei + value tags) and never stub-over-good, so future builds don't recreate the 530-stub problem.
- [ ] T010 [US1] In `backend/src/screening/engine.py` `_edgar_profiles`/universe assembly, exclude `instruments.classify(...) ∈ {preferred, adr, fund}` from the value universe before gates; add the "N non-common-equity instruments out of value scope" data-note and set `out_of_scope_count`.
- [ ] T011 [US1] In `backend/src/screening/engine.py`, split the staleness verdict (research D7): local-lag → "stale local data — run ingest" (surface, don't drop) vs. corroborated halt/delist; add the store-level all-stale warning. Make T007 pass.
- [ ] T012 [P] [US1] Update `backend/scripts/ingest_daily.py` to cover the full screened universe and retry tickers it failed (close the warm-store coverage gap behind the false "halted").
- [ ] T013 [US1] OPERATIONAL: run `refresh_edgar_coverage --scope screened` + `ingest_daily`; commit the refreshed `CoverageReport` to the feature dir as evidence (SC-001/SC-002).

**Checkpoint**: live value universe is populated and correctly scoped.

---

## Phase 4: User Story 2 — Correct selection and level math (Priority: P1)

**Goal**: Loss-makers excluded by a profitability gate; no degenerate stops;
falling-knife guard on at −0.20 by default.

**Independent Test**: On the reference snapshot, no hard-mode candidate has CFO≤0/
ROA≤0, every candidate has `risk_per_share ≥ 1·ATR`, and 12-1 momentum < −0.20 is
excluded by default.

### Tests for User Story 2 ⚠️ (write first, must fail)

- [ ] T014 [P] [US2] Add tests in `backend/tests/strategies/test_midterm_value_composite.py`: a loss-maker (CFO≤0 or ROA≤0, OIS profile) is excluded in hard mode and shows a `"Profitability"` gate fail; missing CFO/ROA → skipped + excluded (not fail-open).
- [ ] T015 [P] [US2] Add tests in `backend/tests/strategies/test_midterm_value_composite.py`: when the SMA-200 stop would sit within 1×ATR of entry (OIS 8.50/8.39), the stop falls back to the 3-ATR floor, `risk_per_share ≥ 1·ATR`, `stop_basis == "atr_floor_fallback"`, and the displayed R equals `(tp−entry)/risk`.
- [ ] T016 [P] [US2] Update the momentum-floor default tests so the **default** (no env, no attr) now excludes a −50% name and `PARAMETERS["min_momentum_12_1"].default == -0.20`; the existing per-run/env/attr override tests still hold.

### Implementation for User Story 2

- [ ] T017 [US2] Add the **Profitability gate** to `backend/src/strategies/midterm_value_composite.py` `rules()` (hard filter, after F-Score, before leverage) and an `evaluate()` line using `operating_cf>0 AND roa>0`; reuse Piotroski signal extraction. Make T014 pass.
- [ ] T018 [US2] Add the **minimum-risk ATR floor** (`min_risk_atr_multiple=1.0`) to BOTH `derive_levels` and the vectorized `rules()` level block; set `stop_basis`; derive `take_profit` from the floored risk. Make T015 pass.
- [ ] T019 [US2] Change `PARAMETERS["min_momentum_12_1"].default` to `-0.20` and add `min_risk_atr_multiple` to `PARAMETERS` (with documented range). Ensure `return_12_1` is present on the live value universe frame. Make T016 pass.
- [ ] T020 [P] [US2] In `frontend/src/app/screen/[strategy]/page.tsx`, default the value falling-knife toggle to checked (reflecting the −0.20 default) while leaving it user-overridable.

**Checkpoint**: value candidates are correctly gated and have sane levels.

---

## Phase 5: User Story 3 — Honest, verifiable disclosure (Priority: P2)

**Goal**: Cheapness-cut as its own gate, F-Score low-confidence flag, within-sector
grouping/cap visible, regime-blind banner, data-quality flags.

**Independent Test**: Inspect a candidate — distinct cheapness-cut PASS/FAIL line,
low-confidence badge when F-Score evaluable <9, sector groups with dropped names,
regime-blind banner on a regime-unavailable run, data-quality badges.

### Tests for User Story 3 ⚠️ (write first, must fail)

- [ ] T021 [P] [US3] Backend tests (`backend/tests/strategies/` and `backend/tests/api/`): `evaluate()` emits a distinct `"Cheapness cut"` gate; `f_score_low_confidence` true iff `f_score_evaluable<9`; ScreenResult carries `regime_available`, `sector_groups`, `out_of_scope_count`, and per-candidate `data_quality_flags` (negative_fcf, outlier_yield).
- [ ] T022 [P] [US3] Coverage-guard test `backend/tests/screening/test_value_coverage_guard.py`: on a fixture universe, the screened value set retains ≥ the defined minimum value-metric coverage (regression guard for FR-015).

### Implementation for User Story 3

- [ ] T023 [US3] Split the cheapness-cut into its own `evaluate()` gate entry in `backend/src/strategies/midterm_value_composite.py`; set `f_score_low_confidence` on rows where evaluable <9. Make the relevant part of T021 pass.
- [ ] T024 [P] [US3] Add additive fields to `backend/src/models/strategy.py`: `f_score_low_confidence`, `sector_rank`, `stop_basis`, `data_quality_flags` (Candidate); `regime_available`, `sector_groups`, `out_of_scope_count` (ScreenResult/AnalyzeResponse).
- [ ] T025 [US3] In `backend/src/screening/engine.py`, populate `regime_available`, `sector_groups` (kept/dropped per sector), and per-candidate `data_quality_flags` from existing row fields. Make the rest of T021 pass.
- [ ] T026 [P] [US3] Mirror the additive fields in `frontend/src/lib/api.ts` (CandidateSchema + ScreenResult/AnalyzeResponse schemas).
- [ ] T027 [US3] Render disclosure in `frontend/src/app/screen/[strategy]/page.tsx` + the gates/candidate-row components: regime-blind banner when `regime_available===false`, low-confidence badge, sector grouping with dropped names, data-quality badges — all neutral copy.
- [ ] T028 [P] [US3] Extend `frontend/tests/e2e/no-directive-copy.spec.ts` to cover the new badges/banner copy (directive lint passes, SC-006).

**Checkpoint**: every declared gate and low-confidence signal is visible.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T029 Rebuild the slim cache + regenerate the value backtest: `SCREENER_VALUE_TREAT_AS_VALID=1 py -3.12 -m backend.src.backtests.runner --strategy midterm_value_composite --start 2008-01-01 --end 2024-12-31`; confirm `bias_check.survivorship_bias.passed` stays **false** and visible (SC-008).
- [ ] T030 [P] Re-sync the advisor pack: update `claude-project/00-custom-instructions.md`, `claude-project/05-value-strategy-rules.md`, `claude-project/06-value-modifications-and-citations.md` for the momentum floor now default ON at −0.20, the new profitability gate (Piotroski 2000), and the minimum-risk stop floor.
- [ ] T031 Run the full suites: `py -3.12 -m pytest backend/tests -q` (from repo root) and `cd frontend && npm.cmd run test && npx.cmd playwright test`; all green.
- [ ] T032 Execute `specs/007-value-coverage-hardening/quickstart.md` end-to-end on the live app; confirm the data-notes counts dropped, no loss-makers/degenerate stops, banner + sector groups render, toggle on by default.
- [ ] T033 [P] Update the memory note `value-strategy.md` (and add `value-coverage-hardening-007.md`) once shipped, recording the new gates/defaults and the coverage refresh.

---

## Dependencies & Execution Order

- **Setup (P1)** T001–T002 → no deps.
- **Foundational (P2)** T003–T005 → blocks US1 (engine filter + refresh use the classifier).
- **US1 (P1)** T006–T013 → after Foundational. MVP increment (correct data).
- **US2 (P1)** T014–T020 → after Foundational; independent of US1 logically but best validated on US1's populated data. Touches `midterm_value_composite.py`.
- **US3 (P2)** T021–T028 → after US2 (shares `midterm_value_composite.py`/models). Some frontend tasks [P].
- **Polish (P6)** T029–T033 → after US1–US3; T029 (backtest) last so numbers reflect final gates.

### Within-file serialization (NOT parallel)

- T017, T018, T019, T023 all edit `midterm_value_composite.py` → run sequentially.
- T010, T011, T025 all edit `engine.py` → sequentially.
- T020, T027 edit `screen/[strategy]/page.tsx` → sequentially.

### Parallel Opportunities

- T003 ∥ (T005 different concern); T006 ∥ T007 (different test files).
- T009, T012 ∥ within US1 (different scripts).
- T014 ∥ T015 ∥ T016 (same test file — author together, but they assert distinct behaviors; treat as one editing session).
- T024 ∥ T026 ∥ T028 (backend model vs frontend schema vs e2e — different files).
- T030, T033 ∥ in Polish (docs/memory).

---

## Implementation Strategy

### MVP (Stop-and-validate after US1)

Setup → Foundational → US1, then run the refresh and re-screen. If the coverage
numbers collapse and the false "halted" names return, the highest-value fix is
already delivered and demoable before any strategy-logic change.

### Incremental

US1 (data) → US2 (correctness) → US3 (disclosure) → Polish (rebuild + advisor
sync). Each phase is independently testable; the value backtest is regenerated
once, last.

## Notes

- Verify every ⚠️ test FAILS before implementing (Principle IV).
- No API keys to disk; SEC fetch uses only a UA header.
- Survivorship verdict stays visible — coverage work must not hide it.
- Out of scope: regenerating the clobbered `006/plan.md` (separate cleanup).
