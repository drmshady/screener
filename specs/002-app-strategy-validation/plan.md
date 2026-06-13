# Implementation Plan: App & Strategy Validation

**Branch**: `002-app-strategy-validation` | **Date**: 2026-06-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-app-strategy-validation/spec.md`

## Summary

Validate that the already-built screener runs correctly end-to-end and that the
**mid-term strategy** (`midterm_52w_high_momentum`) behaves exactly as its
declared rules, modifications, and citation promise. The approach is a
**reproducible validation harness** layered on the existing test stack, run
against a single **frozen data snapshot**, producing a written **findings
report** that classifies every observation as defect / data-tier limitation /
pass.

Technical approach: (1) freeze the current computed snapshot so the run is
deterministic and re-runnable; (2) add a focused `backend/tests/validation/`
pytest module that drives the mid-term strategy's `rules()` over the frozen
universe and asserts gate order, the gate funnel, hand-classified reference
tickers (the oracle), modification-effect (toggle each modification and observe
the delta), and run-to-run determinism; (3) add a consolidated frontend e2e
"surface sweep" that walks every primary page on the snapshot and lints
`data_as_of` + disclaimer presence and zero directive language; (4) run the
full existing backend pytest + frontend Vitest/Playwright suites as the
regression floor; (5) emit `findings-report.md`. No production app code is
modified by this feature except defect fixes that the run surfaces (each fix
re-runs the relevant existing tests).

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Node 20 (frontend) — unchanged from 001
**Primary Dependencies**: pytest + hypothesis, FastAPI TestClient + schemathesis (contract), pandas/numpy; Vitest + Playwright (frontend) — all already installed
**Storage**: Frozen read-only data snapshot under `backend/data/` (Parquet price store, SQLite catalog, EDGAR cache, computed strategy snapshots); findings report is a markdown file in this spec dir
**Testing**: `python -m pytest backend/tests`, `npm run test` (Vitest) + `npx playwright test` (frontend); new `backend/tests/validation/` module
**Target Platform**: Local single-machine (Windows 11), personal-use scope — unchanged
**Project Type**: Web application (FastAPI backend + Next.js frontend) — existing
**Performance Goals**: Validation is correctness-first, not perf; it reuses the existing perf test (`test_perf.py`) as the floor (p95 ≤ 10s full-universe screen per constitution)
**Constraints**: Determinism is mandatory (same snapshot → identical output); validation must not require live network beyond what is already cached in the frozen snapshot; free-data-tier limitations are accepted, not fixed
**Scale/Scope**: ~591-name compliant US universe + ~42-name Saudi `.SR` spike on the current snapshot; 1 strategy validated deeply, 2 smoke-checked, 8 user surfaces swept

**No NEEDS CLARIFICATION remain** — the spec's Assumptions section resolved
scope (mid-term focus, frozen snapshot, "as intended" judged against the
strategy's own declared rules), and the reference-ticker oracle is drawn from
prior task notes (WYY, EA, BELFB, ASYS, AMAT, ROST) and confirmable on the
snapshot.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This feature is a **verifier of the constitution**, so each principle maps to a
validation obligation rather than a risk:

- **I. Data Integrity & Provenance (NON-NEGOTIABLE)**: The validation runs on a
  frozen snapshot whose rows already carry `source` + `source_as_of`; the
  surface sweep (FR-002) asserts `data_as_of` is visible on every page. The
  report explicitly flags any datapoint lacking provenance as a defect. The
  known survivorship limitation (free Stooq lacks delisted) is recorded as a
  data-tier limitation, not silently passed (FR-009, US3 scenario 4). ✅ PASS
- **II. Strategy Transparency & Peer-Reviewed Foundations**: US2 directly
  verifies the mid-term declaration exposes NAME/CITATION (George & Hwang
  2004)/PARAMETERS/MODIFICATIONS-with-citations and that the registry rejects
  incomplete declarations (FR-004). ✅ PASS
- **III. Reproducible Backtesting & Bias Avoidance (NON-NEGOTIABLE)**: US3 +
  FR-009 confirm the ≥15-yr / 2008–2009 window and per-year metrics; FR-007
  asserts determinism across the whole pipeline; the existing
  `test_backtest_window_floor.py`, `test_determinism.py`,
  `test_survivorship_delisted.py` are part of the regression floor. ✅ PASS
- **IV. Test-First for Financial Logic**: This feature *adds* tests, never
  weakens them; the existing indicator golden-fixture tests are run as the
  floor (FR-015) and any new mid-term assertion is fixture/oracle-anchored. ✅ PASS
- **V. User Safety, Risk Disclosure & No-Advice Boundary**: FR-002/FR-003 +
  the surface sweep assert disclaimer presence and zero directive language on
  every page (reusing the existing `disclaimer-everywhere` and
  `no-directive-copy` Playwright lints). ✅ PASS

**No violations. Complexity Tracking is empty.** The feature adds only test and
report artifacts; it introduces no new runtime project, no new data source, and
no new persistence.

## Project Structure

### Documentation (this feature)

```text
specs/002-app-strategy-validation/
├── plan.md              # This file
├── research.md          # Phase 0 — validation method decisions
├── data-model.md        # Phase 1 — validation record entities
├── quickstart.md        # Phase 1 — how to run the validation pass
├── contracts/
│   ├── findings-report.schema.md      # the report's required structure
│   └── midterm-gate-expectations.md   # the mid-term gate-order + oracle contract
├── findings-report.md   # OUTPUT of running the validation (produced during /implement)
└── tasks.md             # Phase 2 — /speckit-tasks (NOT created here)
```

### Source Code (repository root)

The feature touches only test + report locations; production directories are
listed for reference because the validation reads them.

```text
backend/
├── src/
│   ├── strategies/midterm_52w_high_momentum.py   # (read) the validation target
│   ├── strategies/_registry.py                   # (read) declaration enforcement
│   ├── api/{screen,analyze,backtest,regime,...}.py # (read) surfaces exercised
│   └── ...
└── tests/
    ├── validation/                # NEW — focused mid-term + snapshot-freeze module
    │   ├── conftest.py            # frozen-snapshot fixture (session-scoped, read-only)
    │   ├── test_midterm_gate_order.py        # FR-005 declared gate order + funnel
    │   ├── test_midterm_reference_tickers.py # FR-006 hand-ticker oracle
    │   ├── test_midterm_modifications.py     # FR-006a each modification has an effect
    │   ├── test_midterm_determinism.py       # FR-007 run-twice identical (mid-term)
    │   ├── test_strategies_smoke.py          # US2b short-term load+run
    │   └── test_surface_sweep_api.py         # FR-001/002 API-side surface presence
    ├── strategies/ integration/ indicators/ ... # (existing) regression floor

frontend/
└── tests/e2e/
    ├── validation-surface-sweep.spec.ts  # NEW — walk every page, assert as-of+disclaimer
    ├── disclaimer-everywhere.spec.ts      # (existing) reused
    ├── no-directive-copy.spec.ts          # (existing) reused
    └── us1-midterm-screen.spec.ts         # (existing) mid-term UI path reused
```

**Structure Decision**: Web-application layout (existing). The validation is
additive: a new `backend/tests/validation/` pytest package plus one new
frontend e2e spec, all reusing the established fixtures and the existing test
runners. No new top-level project. The frozen snapshot is the current
`backend/data/` contents pinned by `data_as_of`, accessed read-only through a
session-scoped fixture so the run cannot mutate it.

## Complexity Tracking

> No constitution violations. No entries.
