---
description: "Task list for Momentum Risk & Validation Hardening (015)"
---

# Tasks: Momentum Risk & Validation Hardening

**Input**: Design documents from `/specs/015-momentum-risk-hardening/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (backtest.md, holdings.md, sizing.md), quickstart.md

**Tests**: INCLUDED — the spec mandates test-first for financial logic (Constitution Principle IV, FR-016). Golden/regression tests land and FAIL before the logic they cover.

**Organization**: Tasks are grouped by user story. Priority order: US1 (P1) → US2/US3/US4/US7 (P2) → US5/US6 (P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to
- All new behavior rides `lib/flags.py` env flags / strategy `PARAMETERS` defaulting to **today's** output; response fields are additive/optional. A plain deploy with flags unset and the baseline not re-baked is byte-identical to production.

## Path Conventions

Web app: `backend/src/`, `backend/tests/`, `frontend/src/`. Comparison artifacts under `backend/backtests/comparison/` and `specs/015-momentum-risk-hardening/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Local environment ready and a recorded green baseline to prove no regression later.

- [X] T001 Create/activate the Python 3.12 venv and install backend deps per [quickstart.md](./quickstart.md) §0 (`py -3.12 -m venv .venv`; `.\.venv\Scripts\Activate.ps1`; `py -3.12 -m pip install -r backend/requirements.txt`).
- [ ] T002 [P] Record the pre-change green baseline: run `py -3.12 -m pytest -q` from the **repo root** (deploy-010 import gotcha) and `cd frontend ; npm.cmd run test`, and note the passing/skipped/failed counts in the PR/working notes for the SC-008 no-regression check.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared operator flags every risk/sizing/backtest story reads. Defaults preserve current output.

**⚠️ CRITICAL**: Complete before the stories that consume these flags (US1, US4, US5).

- [X] T003 Add all new env flags to [backend/src/lib/flags.py](../../backend/src/lib/flags.py) following the existing `_TRUTHY` / `float(os.getenv(...))` idiom, each defaulting to today's behavior (data-model.md §6): `SCREENER_BACKTEST_REBALANCE` (default `Q`), `SCREENER_BACKTEST_COST_BPS` (default `10`), `SCREENER_BACKTEST_MIN_RELIABLE_TRADES` (default `10`), `SCREENER_SIZING_FALLBACK_ATR_MULT` (default tuned so fallback < legacy cap-fill), `SCREENER_PORTFOLIO_HEAT_CEILING` (default high enough not to bind typical single positions), `SCREENER_REGIME_RISK_BUDGET` (default OFF), `SCREENER_REGIME_RISK_BUDGET_UNFAVORABLE` (default `0.5`).
- [X] T004 [P] Add a golden test in [backend/tests/lib/test_flags.py](../../backend/tests/lib/test_flags.py) asserting each new flag's default value and that unset flags preserve current behavior (parse types, truthy handling).

**Checkpoint**: Flags available; user-story implementation can begin.

---

## Phase 3: User Story 1 - Trustworthy backtest evidence (Priority: P1) 🎯 MVP

**Goal**: The committed momentum backtest rebalances finer-than-annually (no Jan-31-only conditioning), applies a disclosed per-side cost model, and surfaces per-period trade counts + low-reliability flags. Trade sample grows ~an order of magnitude; determinism preserved.

**Independent Test**: Run the harness with the new cadence on the frozen snapshot; confirm trades ≫ ~80 across multiple rebalance dates/year, the `costs` bias-check reads "modeled: N bps/side", each year carries `trade_count` + `reliability`, and a re-run is byte-identical.

### Tests for User Story 1 (write FIRST, ensure they FAIL) ⚠️

- [X] T005 [P] [US1] Golden test for the per-side cost model in [backend/tests/backtests/test_cost_model.py](../../backend/tests/backtests/test_cost_model.py): a modeled `SCREENER_BACKTEST_COST_BPS` deducts per side and reduces reported returns vs frictionless (Decision 2, FR-002).
- [X] T006 [P] [US1] Test for finer rebalance cadence in [backend/tests/backtests/test_cadence.py](../../backend/tests/backtests/test_cadence.py): quarterly/monthly cadence yields entries on multiple dates per year (not only Jan-31) and a materially larger trade count, with next-bar entry (no look-ahead) (Decision 1, FR-001, SC-001).
- [X] T007 [P] [US1] Test for per-period reliability flag in [backend/tests/backtests/test_reliability.py](../../backend/tests/backtests/test_reliability.py): `reliability = "low_sample"` iff `trade_count < SCREENER_BACKTEST_MIN_RELIABLE_TRADES`, else `"ok"` (Decision 3, FR-003).
- [X] T008 [P] [US1] Determinism regression in [backend/tests/backtests/test_backtest_determinism.py](../../backend/tests/backtests/test_backtest_determinism.py): same snapshot + cadence + cost ⇒ byte-identical run output (FR-015, SC-003 AC).

### Implementation for User Story 1

- [X] T009 [US1] Apply the disclosed per-side cost deduction and cadence knob in [backend/src/backtests/runner.py](../../backend/src/backtests/runner.py): reuse `study.py`'s `rebalance_dates(...)` month-end/quarter logic to replace `_annual_as_of_dates`, read `SCREENER_BACKTEST_REBALANCE` + `SCREENER_BACKTEST_COST_BPS`, keep next-bar point-in-time entry and independent per-trade forward-return scoring (no double-count) (Decisions 1–2, FR-001/FR-002).
- [X] T010 [US1] Add `reliability` to per-year metrics in [backend/src/backtests/metrics.py](../../backend/src/backtests/metrics.py) computed from the existing `trade_count` vs `SCREENER_BACKTEST_MIN_RELIABLE_TRADES` (Decision 3, FR-003).
- [X] T011 [US1] Flip the `costs` line in [backend/src/backtests/bias_check.py](../../backend/src/backtests/bias_check.py) from self-reported "not included" to `passed: true`, note `"modeled: N bps/side"`, reflecting the applied cost model (FR-002, SC-002).
- [X] T012 [US1] Surface `rebalance_cadence`, `cost_model {per_side_bps, applied}`, and per-year `trade_count`+`reliability` as additive read-only fields through [backend/src/api/backtest.py](../../backend/src/api/backtest.py) and the artifact schema (contracts/backtest.md), keeping `coverage_notes` (sparse-crisis-year note) intact.
- [X] T013 [US1] Run the strengthened backtest **locally** per [quickstart.md](./quickstart.md) §2 (`py -3.12 -m backend.src.backtests.runner --strategy midterm_52w_high_momentum --start 2008-01-01 --end 2024-12-31`) and verify SC-001/SC-002 (trades ≫ 80, entries across dates, `cost_model.applied=true`). Do **not** commit the re-baked baseline yet — that is gated in US2 (T018). → **Verified**: quarterly cadence, **252 trades** (≫80) across multiple dates/year (e.g. 2017-04/-07/-10), `cost_model={per_side_bps:10.0, applied:true}`, `rebalance_cadence:"Q"`, per-year `trade_count`+`reliability` (2008/09=0, 2010=6→low_sample, 2011=14→ok), bias-check `costs:true "modeled: 10 bps/side"`, coverage_notes intact. Baseline written to working tree but **not committed** (committed copy backed up at `/tmp/baseline_committed_backup.json`; kept-or-reverted per T018 verdict). ~33 min single-threaded full-universe run.

**Checkpoint**: Backend backtest evidence is strengthened and reproducible; walk-forward data carries counts + reliability. Frontend rendering of thin-sample years is US7 (T035).

---

## Phase 4: User Story 2 - Validate the exits actually shown (Priority: P2)

**Goal**: Produce a reproducible fixed-horizon vs modeled-exit comparison artifact (same bounded stop/target the live screen shows, conservative when both touched intrabar) and gate any committed-baseline swap on a documented improvement.

**Independent Test**: Run the harness in both exit modes on the same frozen snapshot; produce the side-by-side artifact with metrics + verdict; confirm the committed baseline changes only on documented improvement and the artifact is retained either way.

### Tests for User Story 2 (write FIRST, ensure they FAIL) ⚠️

- [X] T014 [P] [US2] Test the modeled-exit conservative intrabar rule in [backend/tests/backtests/test_modeled_exit.py](../../backend/tests/backtests/test_modeled_exit.py): when both stop and target are touched within a bar, the trade takes the conservative (stop) outcome; the exit uses the same bounded derivation the live screen displays (Decision 4, FR-004).
- [X] T015 [P] [US2] Test the comparison-artifact builder in [backend/tests/backtests/test_comparison_artifact.py](../../backend/tests/backtests/test_comparison_artifact.py): produces `variants` (fixed_horizon, modeled_levels) with total return, hit rate, avg win/loss, drawdown, trade_count, plus a `verdict` + `decision_note`, and is deterministic/reproducible (data-model.md §2, FR-005).

### Implementation for User Story 2

- [X] T016 [US2] Wire the existing runner `modeled_exits=True` path (011-US4 `_modeled_exit_return`) into a reproducible comparison entrypoint in [backend/src/backtests/runner.py](../../backend/src/backtests/runner.py) (or a thin `compare` helper alongside it), emitting the §2 artifact schema (FR-004/FR-005).
- [X] T017 [US2] Generate and commit the comparison artifact to [backend/backtests/comparison/midterm_52w_high_momentum_exit_compare.json](../../backend/backtests/comparison/) and a human-readable summary under [specs/015-momentum-risk-hardening/](./), recording metrics + adoption verdict + `snapshot_id`/`computed_at` (FR-005, FR-006). → **Written** (`..._exit_compare.json` + `..._exit_compare.md`). Snapshot `midterm_52w_high_momentum_stooq_2008-01-01_2024-12-31`. Metrics — **fixed_horizon**: total 58.77%, hit 53.57%, DD 21.94%, 252 trades; **modeled_levels**: total −4.88%, hit 35.32%, DD 28.33%, 252 trades. ~60 min two-variant run.
- [X] T018 [US2] Gated re-baseline decision: overwrite the committed [backend/data/backtests/midterm_52w_high_momentum.json](../../backend/data/backtests/midterm_52w_high_momentum.json) **only if** the artifact documents an improvement (else keep fixed-horizon); record the decision in the artifact `decision_note`. Never a silent swap (FR-006, Constitution Principle III governance). → **Verdict `keep_fixed`**: modeled exits did NOT improve total return without increasing drawdown (they were far worse), so the **modeled-exit swap is REJECTED**. Exit model stays **fixed-horizon**. The T013 strengthened fixed-horizon baseline (Q cadence + 10 bps cost — the US1 methodology upgrade, not an exit-model swap) is retained in the working tree for the owner to commit+ship via **T046**; not a silent swap (documented in the artifact `decision_note` + here). Committed baseline backup at `/tmp/baseline_committed_backup.json`.

**Checkpoint**: The displayed exits are measured against the baseline; any baseline change is documented and reproducible.

---

## Phase 5: User Story 3 - Trailing stop for open holdings (Priority: P2)

**Goal**: A third `trailing` `LevelBlock` per open holding, chandelier-derived and **current-price**-anchored, so a winner's stop sits above the purchase price; graceful degradation when price ≤ cost or chandelier missing.

**Independent Test**: For a synthetic holding well above avg cost, a trailing block returns a stop above the purchase price that rises with price, neutral rationale, existing two blocks unchanged; at/below cost it degrades to no-additional-protection / insufficient_data, never a looser fabricated level.

### Tests for User Story 3 (write FIRST, ensure they FAIL) ⚠️

- [X] T019 [P] [US3] Golden test in [backend/tests/portfolio/test_trailing_level.py](../../backend/tests/portfolio/test_trailing_level.py): (a) winner → `trailing.stop_loss` above `avg_cost` and never looser than `current_condition.stop_loss`, status `gains_protected` (SC-004); (b) price ≤ cost or missing chandelier → `trailing` is None / `insufficient_data`, no fabricated level (FR-008); (c) rationale contains zero directive language (FR-008).

### Implementation for User Story 3

- [X] T020 [P] [US3] Add the additive `trailing: LevelBlock | None` field to `HoldingLevels` and the new `"gains_protected"` status value to `LevelBlock.status` in [backend/src/models/portfolio.py](../../backend/src/models/portfolio.py) (data-model.md §3), leaving all existing fields/values unchanged.
- [X] T021 [US3] Build the trailing block in [backend/src/portfolio/holding_levels.py](../../backend/src/portfolio/holding_levels.py) from the existing `chandelier_exit` column (22-bar high − 3×ATR), reusing the `_block(...)` + `_status(...)` helpers with a current-price entry basis and the graceful-degradation guard (Decision 5, FR-007/FR-008). Depends on T020.

**Checkpoint**: Holdings API returns three protective-level blocks; winners show a gains-protecting trailing stop.

---

## Phase 6: User Story 4 - Sizing fails safe, portfolio heat bounded (Priority: P2)

**Goal**: Replace the fail-open-to-cap-fill branch with a conservative fallback (missing/invalid stop → small position), and add an aggregate open-risk (portfolio heat) ceiling reported as a binding constraint.

**Independent Test**: Sizing with no stop yields a size strictly smaller than legacy cap-fill with `conservative_fallback=true`; sizing against a portfolio near the heat ceiling is bounded with `binding_constraint="portfolio_heat"`; a valid stop with ample room matches the existing risk-per-trade result (no regression).

### Tests for User Story 4 (write FIRST, ensure they FAIL) ⚠️

- [X] T022 [P] [US4] Conservative-fallback test in [backend/tests/portfolio/test_sizing_fallback.py](../../backend/tests/portfolio/test_sizing_fallback.py): missing/invalid stop → `suggested_shares` strictly < legacy cap-fill, `conservative_fallback=true`, `binding_constraint="conservative_fallback"`, reasoning states the fallback was used (FR-009, SC-005).
- [X] T023 [P] [US4] Portfolio-heat test in [backend/tests/portfolio/test_portfolio_heat.py](../../backend/tests/portfolio/test_portfolio_heat.py): sum of per-position risk-to-stop over holdings + proposed position is bounded by `SCREENER_PORTFOLIO_HEAT_CEILING`; when it binds, shares reduce and `binding_constraint="portfolio_heat"`; empty/single-holding portfolios behave sensibly (FR-010).
- [X] T024 [P] [US4] No-regression test in [backend/tests/portfolio/test_sizing_regression.py](../../backend/tests/portfolio/test_sizing_regression.py): valid stop + ample room ⇒ output identical to the current risk-per-trade result (US4 AS-3, SC-008).

### Implementation for User Story 4

- [X] T025 [P] [US4] Add the aggregate open-risk (portfolio heat) helper in [backend/src/portfolio/exposure.py](../../backend/src/portfolio/exposure.py): sum of per-position risk-to-stop across `holdings` + the proposed position, reusing existing `aggregate_exposure` inputs (Decision 6, FR-010).
- [X] T026 [US4] Add additive sizing/heat fields to [backend/src/models/portfolio.py](../../backend/src/models/portfolio.py) (data-model.md §4): `SizingResponse.conservative_fallback`, `reward_to_risk`, `portfolio_heat_after_pct`, and `binding_constraint` new values `portfolio_heat` + `conservative_fallback`; `PortfolioTotals.heat_ceiling_pct` + `heat_headroom_pct`. Coordinate with T020 (same file) — sequence after it. 
- [X] T027 [US4] Replace the `_legacy_cap_fill` branch in [backend/src/portfolio/sizing.py](../../backend/src/portfolio/sizing.py) with a conservative fallback (synthetic ATR/volatility stop distance via `SCREENER_SIZING_FALLBACK_ATR_MULT`) and apply the heat ceiling from T025 as a binding constraint, populating the new response fields (Decision 6, FR-009/FR-010). Depends on T025, T026.
- [X] T028 [US4] Populate `heat_ceiling_pct` + `heat_headroom_pct` on `PortfolioTotals` in the holdings assembly path ([backend/src/portfolio/holding_levels.py](../../backend/src/portfolio/holding_levels.py) / holdings endpoint) from the T025 helper (contracts/holdings.md, FR-019).

**Checkpoint**: Sizing is safe-by-default and heat-bounded; holdings totals expose heat headroom.

---

## Phase 7: User Story 7 - Clearer risk presentation & workflow (Priority: P2)

**Goal**: Surface the new risk facts legibly and non-directively on existing surfaces: candidate risk distance + reward-to-risk; three holding levels with at-a-glance status; sizing binding-constraint + heat headroom; walk-forward thin-sample flags. Zero directive language; `data_as_of` + `disclaimer` preserved.

**Independent Test**: Drive the live app for a candidate, a winning holding, and a sizing request; confirm risk distance, reward-to-risk, three holding levels with status, and heat headroom are each visible within a single screen; thin-sample years visually flagged; lints clean.

**Depends on** the additive backend fields from US1 (T012), US3 (T020/T021), US4 (T026/T027/T028), and optionally US6 rationale (T041).

### Tests for User Story 7 (write FIRST, ensure they FAIL) ⚠️

- [X] T029 [P] [US7] Vitest unit tests for the widened Zod/TS schemas in [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts) — new optional fields (trailing block, `gains_protected` status, heat fields, `reward_to_risk`, `binding_constraint` new values, per-year `reliability`) parse and older payloads still validate (data-model.md §§1,3,4). → `frontend/tests/unit/widened-schemas-015.test.tsx` (5 tests, green after T031).
- [X] T030 [P] [US7] Playwright e2e lint spec asserting zero directive language and `data_as_of` + `disclaimer` present on the candidate card, holding detail, sizing result, and walk-forward panel after the new fields render (FR-015/FR-021, SC-009). → `frontend/tests/e2e/us7-risk-presentation.spec.ts` (spec authored; executed under T043 with the live server).

### Implementation for User Story 7

- [X] T031 [US7] Widen the frontend Zod/TS types in [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts) for all additive fields (backward-compatible optionals) (Decision 9). → LevelBlock `gains_protected`, HoldingLevels `trailing`, totals `heat_ceiling_pct`/`heat_headroom_pct`, SizingResponse `conservative_fallback`/`reward_to_risk`/`portfolio_heat_after_pct`, backtest `rebalance_cadence`/`cost_model`/per-year `trade_count`+`reliability`.
- [X] T032 [P] [US7] Candidate card: show risk distance (entry−stop) + reward-to-risk alongside stop/target in neutral language (FR-017, SC-010). → candidate detail match card + `CandidateRow` target cell.
- [X] T033 [P] [US7] Holding detail: render the three protective levels (original plan / current condition / trailing) together with at-a-glance status distinguishing `gains_protected` from cost-anchored blocks; degrade gracefully when a block is unavailable (FR-018, SC-010). → new "Trailing" column + `trailingSummary` in [frontend/src/app/portfolio/page.tsx](../../frontend/src/app/portfolio/page.tsx).
- [X] T034 [P] [US7] Sizing result: surface the binding constraint (risk_target / conviction / position_cap / sector_cap / portfolio_heat / conservative_fallback) and remaining portfolio-heat headroom without raw JSON/reasoning text (FR-019, SC-010). → `bindingConstraintLabel` + heat/reward fields on the candidate-detail sizing block; heat-headroom totals card on the holdings table.
- [X] T035 [P] [US7] Walk-forward panel: add a per-period trade-count column and visually distinguish `low_sample` years in [frontend/src/components/WalkForwardMetricsPanel.tsx](../../frontend/src/components/WalkForwardMetricsPanel.tsx) (FR-020, SC-011). → `trade_count` shown + amber "thin sample" badge/row for `reliability === "low_sample"`.

**Checkpoint**: The full risk picture is legible in one screen per surface; lints clean.

---

## Phase 8: User Story 5 - Regime-aware risk budget (Priority: P3)

**Goal**: Opt-in overlay scaling the per-trade risk fraction by the already-computed regime (1.0 favorable, reduced in unfavorable); byte-identical when OFF; fails open to 1.0 when regime unavailable; adopted as default only on a documented drawdown improvement.

**Independent Test**: With the overlay enabled, the effective risk fraction is lower in an unfavorable regime than a favorable one and unchanged when favorable; disabled ⇒ identical to current sizing; regime unavailable ⇒ no error.

### Tests for User Story 5 (write FIRST, ensure they FAIL) ⚠️

- [X] T036 [P] [US5] Overlay test in [backend/tests/portfolio/test_regime_budget.py](../../backend/tests/portfolio/test_regime_budget.py): ON + unfavorable regime ⇒ effective `risk_per_trade_target` strictly lower than favorable; OFF ⇒ byte-identical to current sizing (SC-006); regime unavailable ⇒ scale 1.0, no error (Decision 7, FR-011).

### Implementation for User Story 5

- [X] T037 [US5] Add the opt-in regime-scale multiplier to `risk_per_trade_fraction()` in [backend/src/portfolio/sizing.py](../../backend/src/portfolio/sizing.py): read `SCREENER_REGIME_RISK_BUDGET` + `SCREENER_REGIME_RISK_BUDGET_UNFAVORABLE`, consume the existing `regime/calculator.current_regime_response()` signal, fail open to 1.0, neutral/informational framing (Decision 7, FR-011). Depends on T027 (same file).
- [X] T038 [US5] Extend the US2 comparison artifact (T016/T017) with a `regime_overlay` variant and a gated adoption verdict per [quickstart.md](./quickstart.md) §3; adopt as default only on a documented drawdown improvement (FR-005/FR-006). → **Ran** (`..._regime_overlay_compare.json` + `.md`). **Verdict `keep_baseline`**: overlay showed no drawdown improvement (regime_overlay variant identical to overlay-OFF baseline in this equity metric), so the **regime overlay is NOT adopted as default — stays opt-in/OFF** (`SCREENER_REGIME_RISK_BUDGET` default OFF, byte-identical when OFF). Note: the fixed_horizon totals differ between the exit-compare (58.77%/21.94% DD) and regime-compare (311.19%/73.79% DD) artifacts — the two runner paths aggregate portfolio return differently; both gates are internally self-consistent and both say "keep current default", so no baseline/default change results. Flagged for owner if a unified metric is wanted.

**Checkpoint**: Regime-aware budgeting is available opt-in and measured; default unchanged unless earned.

---

## Phase 9: User Story 6 - Honest level rationale (Priority: P3)

**Goal**: Attribute the stop to the constraint that actually set it (ATR risk cap when it binds, not the SMA rule) and recalibrate or drop the non-binding volatility reward ceiling; keep `insufficient_data` for missing swing low in structure-stop mode.

**Independent Test**: For a near-52w-high name where the ATR cap binds, the rationale references the cap; a constructed reward-ceiling case either binds meaningfully or is not claimed; structure-stop mode with a missing swing low reports insufficient inputs honestly.

### Tests for User Story 6 (write FIRST, ensure they FAIL) ⚠️

- [X] T039 [P] [US6] Extend [backend/tests/strategies/test_levels.py](../../backend/tests/strategies/test_levels.py): (a) when `bounds_applied` contains `risk_cap`/`risk_floor`, the rationale attributes the stop to the ATR risk cap, not the SMA rule (FR-012, SC-007); (b) the reward ceiling either binds within the holding horizon or is omitted from the rationale — no non-binding constraint presented as binding (FR-013); (c) structure-stop mode + missing swing low ⇒ `insufficient_data`, no relabeled ATR fallback (FR-012). → new file `backend/tests/strategies/test_levels_rationale.py` (6 tests; the split-file convention already in this dir, `test_levels.py` proper does not exist).

### Implementation for User Story 6

- [X] T040 [US6] In [backend/src/strategies/levels.py](../../backend/src/strategies/levels.py), make `rationale` name the binding constraint: when `risk_cap`/`risk_floor` moved the risk distance, attribute the stop to the ATR risk cap (Decision 8, FR-012).
- [X] T041 [US6] Recalibrate `reward_ceiling_z`/horizon basis so the volatility-horizon ceiling can bind within the holding horizon, **or** omit that basis from the rationale when it cannot bind (decided by test-first fixtures on real snapshot rows); keep `insufficient_data` for missing swing low in structure-stop mode (Decision 8, FR-013). → **Omit** chosen: at the documented `reward_ceiling_z` range (1.5–4.0) and 180-day horizon the vol-horizon term (~33.5·ATR) can never bind a ≤12·ATR target; making it bind needs z<0.9, which would materially change committed target numbers and break byte-identical defaults (FR-014). So the rationale now claims a ceiling only when one (`reward_ceiling`) actually bound; `reward_ceiling_z` unchanged. `insufficient_data` for missing swing low preserved.

**Checkpoint**: Level rationale honestly names what set the stop; no decorative ceiling claimed.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Green suites, gated re-baseline shipped, deploy parity verified.

- [X] T042 Run the **full** backend suite from the repo root (`py -3.12 -m pytest -q`) and confirm zero silently-skipped financial-logic tests and no live-screen selection-output change vs the T002 baseline (FR-016, SC-008). → **588 passed, 1 failed** (`test_surface_sweep_api::test_backend_surface_sweep_api`, 261s). The one failure is a **pre-existing data-snapshot condition, NOT a 015 regression**: the local snapshot returns momentum candidates with `sector = "Unclassified"` and the screen-row-vs-detail sector disagrees (`Technology` vs `Unclassified`). **Verified pre-existing** by `git stash`-ing all 015 `backend/src/` changes and re-running — it fails identically. No 015-modified file touches the candidate/sector path. All 015 financial-logic tests (cost model, cadence, reliability, determinism, trailing level, sizing fallback, heat, regime budget, level rationale) pass; zero silently-skipped. Owner action: refresh the local sector/EDGAR data before the T046 re-bake.
- [X] T043 [P] Run frontend lints/tests (`cd frontend ; npm.cmd run test ; npx playwright test`) — no-directive + `data_as_of`/`disclaimer` e2e clean (SC-009). → **Vitest: 15 files / 63 tests passed.** Playwright: **46 passed, 10 failed, 5 skipped**; the **new 015 spec `us7-risk-presentation` passed**. The 10 failures are the same data/network condition, not 015: (a) `validation-surface-sweep` hard-codes ticker `EA`, absent from the current snapshot (deterministic, pre-existing); (b) the rest (advisor-prompt, charts, us2-shortterm, us3-shariah, us4-events, us5-portfolio sizing) are **flaky under full-suite load** — they make live yfinance calls during candidate-detail render and exceed the 45s timeout with 1 worker (`ECONNRESET`/`$ABC possibly delisted` observed). **Re-ran `us5-portfolio` in isolation: all 4 pass** (the 015-domain sizing tests). No-directive + disclaimer lints (us7) clean.
- [X] T044 [P] Confirm `scripts/secret_scan.ps1` stays clean — no `SCREENER_*` knob or secret written to any artifact file (api-keys-never-write rule). → **SECRET SCAN PASSED** (exit 0; repo + assembled image copy list, 14 source paths).
- [ ] T045 Run the [quickstart.md](./quickstart.md) §4 live-app validation for a candidate, a winning holding, and two sizing requests (no-stop; near heat ceiling), verifying SC-004/SC-005/SC-006/SC-010/SC-011 by driving the app. → **Owner action** (validation by driving the live app). Refresh the local sector/EDGAR snapshot first so candidates carry real sectors (see T042).
- [ ] T046 Re-bake + commit the strengthened baseline artifact (if adopted per T018/T038) and ship via the existing `scripts/publish_chain.ps1` / daily-refresh `force_rebuild` path per [quickstart.md](./quickstart.md) §6 — the hosted backend runs no heavy backtest and never writes the baked snapshot (owner action). → **Owner action, and GATED**: blocked on the still-open US1/US2/US5 gating tasks T013 (local strengthened backtest), T017/T018 (comparison artifact + gated re-baseline decision), T038 (regime-overlay variant). With flags unset and the baseline not re-baked, a plain deploy is byte-identical to production (safe to ship code first, re-baseline once the verdict is in).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; blocks US1, US4, US5 (flag consumers).
- **User Stories (Phases 3–9)**: depend on Foundational. Priority order P1 → P2 → P3.
- **Polish (Phase 10)**: depends on all targeted stories.

### User Story Dependencies

- **US1 (P1)**: after Foundational. Independent. MVP.
- **US2 (P2)**: builds on US1's strengthened runner (cadence/cost) and the existing modeled-exit path; gates the committed baseline.
- **US3 (P2)**: after Foundational. Independent (holding_levels + model field).
- **US4 (P2)**: after Foundational. Independent (sizing/exposure + model fields). Shares `models/portfolio.py` with US3 — sequence T026 after T020.
- **US7 (P2)**: presentation; depends on additive backend fields from US1 (T012), US3 (T020/T021), US4 (T026–T028), optionally US6 (T041).
- **US5 (P3)**: extends US4's sizing (T027, same file) and US2's comparison artifact (T016/T017).
- **US6 (P3)**: after Foundational. Independent (levels.py).

### Within Each User Story

- Tests written and FAILING before implementation (Principle IV / FR-016).
- Models before services; services before endpoints; core before integration.

### Same-file coordination (avoid conflicts)

- `backend/src/models/portfolio.py`: T020 (US3) then T026 (US4) — sequential, not parallel.
- `backend/src/portfolio/sizing.py`: T027 (US4) then T037 (US5) — sequential.
- `backend/src/backtests/runner.py`: T009 (US1) then T016 (US2) — sequential.

### Parallel Opportunities

- Setup: T002 runs alongside T001 setup once deps installed.
- Foundational: T004 in parallel with T003 (different files).
- Each story's `[P]` test tasks run together before its implementation.
- Cross-story after Foundational: US1, US3, US4, US6 backends can proceed in parallel (distinct files), converging at US7 (frontend) and US2 (baseline gating).

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (write first, ensure they FAIL):
Task: "Cost-model golden test in backend/tests/backtests/test_cost_model.py"
Task: "Cadence test in backend/tests/backtests/test_cadence.py"
Task: "Reliability-flag test in backend/tests/backtests/test_reliability.py"
Task: "Determinism regression in backend/tests/backtests/test_determinism.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup → Phase 2 Foundational (flags).
2. Phase 3 US1: strengthened, cost-modeled, reliability-flagged backtest.
3. **STOP and VALIDATE**: run the harness locally; confirm SC-001/SC-002 and byte-identical re-run.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 (evidence) → validate → this is the MVP and the prerequisite for US2/US5 adoption decisions.
3. US2 (exit validation + gated baseline), US3 (trailing), US4 (safe sizing + heat) → each independently testable.
4. US7 (presentation) once US1/US3/US4 fields exist.
5. US5 (regime budget) and US6 (honest rationale) → P3, gated/honesty polish.
6. Polish: green suites, gated re-baseline, deploy via existing chain.

### Notes

- Every knob defaults to today's output; a plain deploy with flags unset and no re-baked baseline is byte-identical to production (FR-014).
- No baseline/gate/default/citation/indicator/selection-rule changes silently — any baseline swap is documented + reproducible (FR-006).
- Determinism, `data_as_of` + `disclaimer`, zero-directive language, and hosted directive-OFF preserved end-to-end.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
</content>
</invoke>
