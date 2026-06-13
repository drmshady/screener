# Data Model: App & Strategy Validation

**Feature**: 002-app-strategy-validation | **Date**: 2026-06-12

These are **record/report entities** — the structures the validation run
produces and serializes into `findings-report.md`. They are not new persistent
database tables; the app stays stateless on user data (per the project's
browser-local model). They define the shape of the report and the in-memory
objects the validation tests build.

---

## ValidationRun

The top-level record of one full validation pass.

| Field | Type | Notes |
|-------|------|-------|
| `run_date` | date | When the pass was executed (e.g. 2026-06-12). |
| `snapshot_as_of` | date | `data_as_of` of the frozen snapshot validated. |
| `snapshot_id` | string | Identifier/path or hash of the frozen `backend/data/` snapshot. |
| `verdict` | enum `pass` \| `pass_with_defects` \| `fail` | Overall go/no-go. |
| `surface_checks` | SurfaceCheck[] | One per primary surface (FR-001). |
| `strategy_check` | StrategyCheck | The mid-term deep result (one). |
| `smoke_checks` | StrategyCheck[] | Short-term load+run (lighter, US2b). |
| `backtest_check` | BacktestCheck | Mid-term backtest (one). |
| `findings` | Finding[] | All classified observations. |
| `suite_results` | SuiteResult[] | Existing pytest/Vitest/Playwright runs. |

**Validation rules**: `verdict` is `fail` if any defect with severity
`blocker` exists; `pass_with_defects` if only non-blocker defects exist; `pass`
if zero defects. `snapshot_as_of` MUST be non-null (no live-only runs claim a
verdict).

---

## SurfaceCheck

One primary user surface exercised (FR-001, FR-002, FR-003).

| Field | Type | Notes |
|-------|------|-------|
| `surface` | enum | `midterm_screen`, `candidate_detail`, `single_ticker_analysis`, `backtest_view`, `market_regime`, `shariah_filter`, `events_overlay`, `portfolio_sizing`. |
| `status` | enum `pass` \| `fail` | Rendered/responded without error and consistent. |
| `data_as_of_present` | bool | The page/response carried a `data_as_of`. |
| `disclaimer_present` | bool | The standing disclaimer was shown. |
| `directive_language_found` | bool | MUST be false to pass (FR-003). |
| `evidence_ref` | string | Screenshot path or captured response id. |

**Validation rules**: `status=pass` requires `data_as_of_present=true`,
`disclaimer_present=true`, `directive_language_found=false`, and no server
error. All eight enum surfaces MUST appear exactly once (SC-001).

---

## StrategyCheck

Per-strategy result. Full depth for mid-term; smoke fields only for short-term.

| Field | Type | Notes |
|-------|------|-------|
| `slug` | string | e.g. `midterm_52w_high_momentum`. |
| `declaration_complete` | bool | NAME, CITATION, TIMEFRAME, PARAMETERS, REGIME_FAVORABILITY, MODIFICATIONS(+citations), `rules()` all present (FR-004). |
| `registry_rejects_incomplete` | bool | Registry refused a deliberately-incomplete stub (FR-004). |
| `gate_order_ok` | bool | Gates applied in declared order (FR-005). |
| `gate_funnel` | GateStage[] | Surviving count after each gate. |
| `oracle_results` | OracleResult[] | Hand-ticker outcomes (FR-006). |
| `modification_effects` | ModificationEffect[] | Per-modification toggle delta (FR-006a). |
| `deterministic` | bool | Two runs identical (FR-007). |
| `smoke_only` | bool | True for the two short-term strategies (US2b). |

### GateStage

| Field | Type | Notes |
|-------|------|-------|
| `gate` | enum | `liquidity`, `proximity`, `trend`, `volume`, `quality`, `gross_profitability`, `asset_growth`. |
| `order_index` | int | 0-based position; MUST match the declared sequence. |
| `survivors` | int | Count remaining after this gate. |

### OracleResult

| Field | Type | Notes |
|-------|------|-------|
| `ticker` | string | e.g. `WYY`, `EA`. |
| `expected` | enum `pass` \| `fail` | Hand classification. |
| `actual` | enum `pass` \| `fail` | Observed. |
| `expected_gate` | enum (GateStage.gate) \| null | For fails: which gate should reject it. |
| `actual_gate` | enum \| null | Gate that actually rejected it. |
| `match` | bool | `expected==actual` AND (if fail) `expected_gate==actual_gate`. |

### ModificationEffect

| Field | Type | Notes |
|-------|------|-------|
| `modification` | enum | `vol_scaling`, `sector_relative_rank`, `quality_screen`. |
| `citation` | string | The modification's own citation. |
| `has_effect` | bool | Output set/order changed when toggled (FR-006a). |

---

## BacktestCheck

Mid-term backtest integrity (US3, FR-009).

| Field | Type | Notes |
|-------|------|-------|
| `slug` | string | `midterm_52w_high_momentum`. |
| `window_years` | number | MUST be ≥ 15. |
| `covers_2008_2009` | bool | MUST be true. |
| `per_year_metrics_present` | bool | Walk-forward per-year metrics exposed. |
| `reproducible` | bool | Re-run identical (FR-009). |
| `bias_caveat_visible` | bool | Survivorship caveat still shown in UI (US3 #4). |
| `enabled_by_default` | bool | And, if true, justified by a visible operator override. |

---

## Finding

A single classified observation (FR-013, SC-007).

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Stable id, e.g. `F-001`. |
| `summary` | string | One-line description. |
| `classification` | enum `defect` \| `data_tier_limitation` \| `pass` | Per Decision 6 rubric. |
| `severity` | enum `blocker` \| `major` \| `minor` \| null | Required when `classification=defect`. |
| `justification` | string | One line; required for every non-pass. |
| `related_surface_or_gate` | string | Where it was observed. |

**Validation rules**: every Finding with `classification != pass` MUST have a
non-empty `justification`; defects MUST carry a `severity` (SC-007).

---

## SuiteResult

Result of running an existing automated suite (FR-015).

| Field | Type | Notes |
|-------|------|-------|
| `suite` | enum | `backend_pytest`, `frontend_vitest`, `frontend_playwright`. |
| `passed` | int | Tests passed. |
| `failed` | int | Tests failed (each failure → a Finding). |
| `command` | string | The exact command run. |

---

## DataSnapshot

The frozen dataset under validation (read-only).

| Field | Type | Notes |
|-------|------|-------|
| `data_as_of` | date | Snapshot freshness stamp. |
| `universe_size_us` | int | e.g. ~591 compliant US names. |
| `universe_size_saudi` | int | e.g. ~42 `.SR` names. |
| `components` | string[] | `prices_parquet`, `catalog_db`, `edgar_cache`, `strategy_snapshots`. |
| `read_only` | bool | MUST be true during the run (no mutation). |
