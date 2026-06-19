# Bug Scan Log: Release Readiness (009)

## Severity Legend

- `correctness`: must-fix before release.
- `integrity`: must-fix before release.
- `crash-hang`: must-fix before release.
- `minor`: deferrable with a one-line rationale.

## Findings

| id | location | description | severity | resolution |
|----|----------|-------------|----------|------------|
| BUG-001 | `POST /data/refresh` | Provider fetch exceptions could bubble out of manual refresh, crashing the operator-initiated stale-data recovery flow instead of returning cached state with a non-blocking notice. Reproduced and covered by `backend/tests/api/test_data_refresh.py::test_post_data_refresh_returns_cached_state_when_source_unreachable`. | crash-hang | fixed in working tree by catching refresh-source exceptions, preserving cached `latest_bar`, and returning `notices`. |
| BUG-002 | `backend/tests/validation/test_midterm_reference_tickers.py` + `conftest.py` | The mid-term correctness-floor oracle hand-coded a pass/fail verdict per named ticker (`EA/BELFB/ASYS/AMAT/ROST` pass, `WYY`/probes fail). Because it is evaluated against the live, git-ignored yfinance EOD store, benign price drift broke it: ASYS slipped to ~5.3% below its 52-week high (`dist_to_high` 0.0531 > the 0.05 proximity band), so the strategy correctly rejected it at the proximity gate and the hardcoded `ASYS=pass` assertion failed. No strategy rule/default/citation/baseline changed (proximity_pct stays 0.05); the oracle was stale. | correctness | fixed by replacing the per-ticker oracle with ticker-agnostic, data-driven gate invariants over the whole prepared universe (`test_every_candidate_clears_every_hard_gate`, `…_is_within_the_proximity_band`, `…_are_a_subset_of_hard_gate_survivors`, `…proximity_and_quality_gates_actually_reject`); removed the hardcoded `reference_tickers` fixture and its now-unused `Any` import. Suite green. |
| BUG-003 | backend test suite cwd-sensitivity | Several validation tests read fixtures via the relative path `backend/data/...` (e.g. `test_midterm_backtest.py`, `test_surface_sweep_api.py`), so they only pass when pytest runs from the repo root (`E:\screener`), not from `backend/`. From `backend/` they error `FileNotFoundError`. | minor | deferred-with-rationale: the documented run command is repo-root `py -3.12 -m pytest backend` (quickstart/runbook), under which all tests pass; hardening to `Path(__file__)`-relative is a non-blocking polish item, no correctness/integrity/crash impact. |
| BUG-004 | `frontend/tests/e2e/integrity-badge.spec.ts` | The e2e mock drifted from current schemas: the `/backtest` mock omitted most required `BacktestResponseSchema` fields and both `/run` candidates omitted the required `recent_8k_count_30d`, so `*.parse` threw and the screen page (which gates its whole render on a parsed backtest) stuck on "Loading…", never showing "Run Screen" or the integrity badge. | minor | fixed: completed the `/backtest`, `/backtest/equity-curve`, and candidate mocks; the test (the regression check itself) now passes. Test-only; no product code touched. |
| BUG-005 | `frontend/tests/e2e/phase12-charts-help.spec.ts` | The "home and portfolio" e2e seeded holdings via `localStorage` but did not isolate the shared backend `portfolio_state.json`, so `PortfolioSync` clobbered the seed with state a parallel test persisted (snapshot showed `$2,799.19` instead of the seeded values) → "Sector cap 25.0%" never appeared. Determinism/isolation defect (test-only). | minor | fixed: added `isolatePortfolioState(page)` (the established `_state.ts` pattern); test passes. |
| BUG-006 | `frontend/src/app/screen/[strategy]/page.tsx` | The screen page hard-gates its entire render on a successfully-parsed backtest (`if (!strategy || !backtest)`), and the backtest fetch (useEffect) has **no `.catch`** (unlike the equity-curve fetch beside it). If the real `GET /strategies/{slug}/backtest` fails or times out, the page hangs on "Loading strategy…" indefinitely — a graceful-degradation gap in a primary flow. | crash-hang | fixed in T030: `fetchApi` now throws retryable `ApiError`s with backend detail text, the screen page catches backtest/run failures, renders a human-readable warning/error, and keeps strategy controls navigable. Regression coverage: `frontend/tests/unit/error-states.test.tsx`; Playwright 45/45 passed. |
| BUG-007 | `backend/src/api/strategies.py` (`POST /strategies/{slug}/run` and `POST /strategies/{slug}/advisor-prompt`) | Both endpoints catch `KeyError`→404 but not `ValueError`. A request whose explicit `parameters.tickers` resolve to no OHLCV data raises `ValueError: No OHLCV data available …` uncaught → HTTP 500 with a stack trace, instead of the graceful 404 the analyze/candidate paths already give for the same condition (`compute_candidate_result` converts `ValueError`→404). Crash on a public primary-flow endpoint. | crash-hang | fixed in T023: catch `ValueError`→400 with the message in both endpoints; regression test in `backend/tests/api/test_robustness_run.py`. |
| BUG-008 | `backend/src/strategies/midterm_52w_high_momentum.py` `OUTPUT_CONTRACT` (momentum) | A candidate whose price is **pinned under a pending all-cash acquisition / cash tender** ranks at the top as if it were clean low-vol momentum, and trips **zero** contract invariants. Reproduced on the 2026-06-17 run with **EA** (#1 of 18, score 0.6549): under a $210 all-cash take-private, price pinned at 203.02 (0.9% below its 52w high) → trailing realized vol collapsed to **6.0% annualized** → the Barroso–Santa-Clara `vol_scalar` saturated at its **2.0 cap** → score inflated. The 33.1% `return_12_1` is the one-time Sept-2025 deal premium (a step), not George–Hwang drift, and the 214.75 target sits above the $210 cash ceiling. The existing invariants miss it because the data is *correct* (seam-consistent, max session move 16.7% < the 40% jump threshold) and 33% is inside the `[-95%, +900%]` return band. | integrity | fixed: new strategy-agnostic invariant `value_domain.realized_vol_floor` (`backend/src/screening/integrity/invariants.py`) flags a candidate whose trailing realized vol (read from the same `daily_returns` window the scaler uses; fallback = a `vol_scalar` saturated at its cap) is below an 8% annualized floor — **detect + per-candidate DATA INTEGRITY WARNING + demote below all clean names**, no strategy rule/default/citation/backtest-baseline change (008 detect-don't-exclude philosophy; deterministic, no network). Wired into the momentum `OUTPUT_CONTRACT`; added the `pinned_price` class to the seeded-defect regression gate (`harness.py`, family `value_domain`). Regression coverage: `tests/integrity/test_invariants.py`, `tests/integrity/test_seeded_defects.py`, `tests/strategies/test_pinned_price_contract.py` (direct EA reproduction). |
| BUG-009 | `midterm_52w_high_momentum` momentum screen — **BELFB** (`return_12_1` +191.1%) | Reported as an unadjusted price-series break (live ~$184 vs snapshot ~$300). **Not reproduced.** Pulling the 2026-06-17 series shows a smooth, gradual climb (~$78 Sep-2024 → ~$300 Jun-2026, with real pullbacks to $65 in Apr-2025 and $197 in Mar-2026) that **two independent sources agree on** (the Stooq deep archive *and* the yfinance warm store both ~$280 in early June 2026); `seam_factor=1.0`, `seam_consistent=True`, max session move 16.5%, `adj_close == close` throughout (no split), and realized vol ~51% (a genuinely volatile name). The +191% is a real (extreme) move in our data, not a stitching artifact. **The reporter's ~$184 is NOT explained by Class A**: BELFA exists and trades at a discount (~$245 on 2026-06-09 in our Stooq data, confirming a real class split) but is **not** $184 — an earlier draft of this entry over-attributed $184 to BELFA and that is retracted. **Operator confirmed the real price is ~$299 (2026-06-18)** — so our snapshot ($299.84) is correct and the reported ~$184 was the erroneous/stale figure, not our data. Tightening the hard return-plausibility band to catch +191% would flag legitimate big winners (the point of a 52w-high momentum screen). On the live recheck screen BELFB carries no data-integrity warning. | minor | **resolved — no defect** (operator confirmed real price ~$299, 2026-06-18): no contract change. Our cross-source-consistent snapshot was correct; the reported $184 was wrong. |

## Baseline

Captured on 2026-06-17 on branch `009-release-readiness`.

| command | result | inventory |
|---------|--------|-----------|
| `py -3.12 -m pytest` | FAIL | 283 collected: 281 passed, 2 failed, 0 skipped, 0 xfailed, 33 warnings. Failures: `backend/tests/integration/test_perf.py::test_candidate_and_home_dashboard_perf_budgets` (`_p95(candidate_samples)` was 1.710s, budget 1.5s); `backend/tests/validation/test_midterm_reference_tickers.py::test_reference_ticker_pass_fail_outcomes_match` (`ASYS` expected pass, actual fail at `proximity`). |
| `npm.cmd run test` from `frontend/` | PASS | 2 test files passed, 5 tests passed. |
| `npm.cmd run test:e2e` from `frontend/` | FAIL | Missing npm script: `test:e2e`. Available scripts are `dev`, `build`, `start`, `lint`, and `test`. |
| `npx.cmd playwright test` from `frontend/` | FAIL | Supplemental e2e inventory because Playwright tests/config exist despite the missing npm script: 43 tests run with retries: 38 passed, 4 failed, 1 flaky. Failed: `advisor-prompt-copy.spec.ts` copy advisor prompt; `integrity-badge.spec.ts` data integrity badge and momentum sign; `phase12-charts-help.spec.ts` home and portfolio visuals; `us5-portfolio.spec.ts` portfolio CRUD/exposure test. Flaky then passed on retry: `us3-shariah-filter.spec.ts` user inclusion. |

Financial-logic skip/xfail audit: `rg -n "pytest\.mark\.(skip|skipif|xfail)|@pytest\.mark\.(skip|skipif|xfail)|\bskip\(|\bxfail\(" backend\tests\indicators backend\tests\strategies backend\tests\screening backend\tests\validation` returned no matches, so no skip/xfail markers were found in indicator, strategy, screening, or validation tests.

## T020 outcome (backend suite green)

Re-run on 2026-06-17 from repo root (`py -3.12 -m pytest backend`): **294 passed, 0 failed, 0 skipped, 0 xfailed**, 33 warnings, ~56 s. The baseline's `test_perf` failure no longer reproduces (the candidate p95 is back within budget after the US1/US2 work landed). The only remaining failure — the ASYS reference-ticker oracle — is resolved as BUG-002 (correctness, fixed: stale per-ticker oracle replaced with ticker-agnostic gate invariants; no strategy change). 0 silently skipped/xfail financial-logic tests (SC-006). The `backend/data/backtests/...` `FileNotFoundError` seen mid-investigation was a cwd artifact (running from `backend/` instead of repo root), logged as BUG-003 (minor, deferred).

## T021 outcome (frontend suites green)

Re-run on 2026-06-17 from `frontend/`:
- `npm.cmd run test` (Vitest unit): **3 files, 9 tests passed** (includes the new `StartupFreshnessGate` unit test).
- `npm.cmd run test:e2e` (Playwright): **45 passed** — including `no-directive-copy.spec.ts` (zero directive-language lint across pages) and `disclaimer-everywhere.spec.ts` (`data_as_of` + `disclaimer` presence). Added the missing `test:e2e` → `playwright test` script to `frontend/package.json` (the baseline flagged it absent).

Baseline had 4 e2e failures + 1 flaky; the advisor-prompt-copy failure cleared once the US2 work landed. The remaining three (integrity-badge, phase12 home/portfolio, us5-portfolio) were resolved via BUG-004/BUG-005 (test mock drift + missing portfolio-state isolation); us5-portfolio was a parallel-state flake fixed by the same isolation discipline. The bug scan surfaced one genuine product robustness gap (BUG-006).

## T022 outcome (bounded bug scan)

Probed the real runtime surfaces via the FastAPI `TestClient` against the documented failure modes (source-down / empty-result / missing-fundamentals / timeout):

| surface | edge probed | result |
|---------|-------------|--------|
| `POST /strategies/{slug}/run` | impossible liquidity floor → 0 candidates | 200, explicit empty result + envelope (graceful) |
| `POST /strategies/{slug}/run` | `tickers=[unknown]` (no data) | **500 uncaught `ValueError`** → BUG-007 |
| `POST /strategies/{slug}/advisor-prompt` | empty screen / `tickers=[unknown]` | empty: 200 graceful; unknown: **500** (same root, BUG-007) |
| `POST /strategies/midterm-compare` (+ `/advisor-prompt`) | default run | 200, envelope ok |
| `GET /analyze/{t}`, `/candidates/{t}`, `/candidates/{t}/history` | unknown ticker | 404 graceful (`ValueError`→404 already) |
| `GET /strategies/{slug}` + `/backtest` | unknown slug | 404 graceful |
| `GET /shariah/status/{t}`, `/events/ticker/{t}` | unknown ticker | 200 graceful |
| `GET /candidate/{t}/verify` | unknown ticker | 404 graceful |
| `POST /sizing` | zero capital | 422 validation error (graceful) |
| `POST /portfolio/quotes` | empty holdings | 200 graceful |
| `GET /meta`, `/regime`, `/data/freshness`, `/healthz` | nominal | 200, envelope ok |
| frontend screen page | `/backtest` fetch fails/times out | hangs on "Loading…" → BUG-006 |

Must-fix found: BUG-006 (frontend hang, → US4/T030), BUG-007 (backend 500, fixed T023). All other probed paths degrade gracefully (explicit empty state, 404, or validation error) — no further crash/integrity defects in the bounded scope.

## T024 outcome (dead-code removal)

Used `ruff check backend/src --select F401,F811,F841` to identify dead code safely. Removed 15 unused imports (`os`/`yfinance` in `backtests/runner.py`, `sqlite3` in `data/db.py`, `typing.Any` in `data/filings_8k.py`, `pydantic.ConfigDict` in `models/catalog.py`, `datetime.timedelta` in `regime/calculator.py`, five unused indicator imports + `pandas`/`ScreenResult`/`Strategy` in `screening/engine.py` & `screening/midterm_matrix.py`, `typing.Iterable` in `screening/integrity/harness.py`) and one dead local (`cik` in `data/fundamentals.py`, a pure no-side-effect assignment). Confirmed no re-export of the engine indicator imports before removal. **Preserved** the three intentional side-effect strategy-registry imports (`from .. import strategies as _strategies`) by relocating their `# noqa: F401` onto the import line. No strategy rule/default/citation/baseline touched. `ruff … → All checks passed`; backend suite **297 passed** afterward (FR-014/FR-015).

## T025 outcome (determinism, SC-010)

Ran the momentum screen twice on the unchanged snapshot via `TestClient` and exported the screen advisor prompt twice:

| check | result |
|-------|--------|
| candidate order identical (n=24) | ✅ |
| regime identical (`Trending up`) | ✅ |
| full per-candidate payload identical (levels, sizing inputs, event badges, integrity flags) | ✅ |
| screen advisor prompt byte-identical (23,915 chars) | ✅ |
| `GET /regime` identical (ex-`data_as_of`) | ✅ |

Same snapshot → identical screen / regime / sizing / event output and byte-identical advisor prompt. No hidden randomness.

## Phase 6 outcome (US4 graceful degradation)

Implemented T026-T031 on 2026-06-18:

| task | evidence |
|------|----------|
| T026 | Added `backend/tests/api/test_robustness.py`: zero-candidate screens return 200 with explicit notes/envelope; missing material inputs are stated and do not abort the run. |
| T027 | Added `frontend/tests/unit/error-states.test.tsx`: empty screener table renders explicit empty state; backend 503 detail becomes retryable human-readable `ApiError`. |
| T028 | `frontend/src/components/ScreenerTable.tsx` and `frontend/src/app/screen/[strategy]/page.tsx` render empty-state copy instead of a blank/empty table. |
| T029 | `backend/src/strategies/midterm_52w_high_momentum.py` now names missing fundamentals in skipped gate notes, preserving deterministic exclusion/pass-through behavior. |
| T030 | Closed BUG-006 by making screen-page backtest/run failures non-blocking and visible; `frontend/src/lib/api.ts` now exposes retryable `ApiError`. |
| T031 | Verified unconditional shell `data_as_of` + disclaimer coverage via full Playwright (`45 passed`) including `disclaimer-everywhere.spec.ts` and `validation-surface-sweep.spec.ts`. |

Validation:

| command | result |
|---------|--------|
| `py -3.12 -m pytest backend\tests\api\test_robustness.py backend\tests\api\test_robustness_run.py` | 5 passed |
| `npm.cmd run test -- error-states.test.tsx StartupFreshnessGate.test.tsx` | 6 passed |
| `npm.cmd run test` | 4 files / 11 tests passed |
| `py -3.12 -m pytest backend` | 299 passed, 33 warnings |
| `npm.cmd run test:e2e` | 45 passed |

## Phase 7 outcome (US5 deployment runbook)

Implemented T032-T034 on 2026-06-18:

- **T032 (runbook verified):** confirmed every `quickstart.md` §A step against the real repo: the three seed scripts (`seed_universe.py`, `refresh_stooq_history.py`, `ingest_daily.py`) exist and run bare (only optional args); `backend[dev]` editable install + `[project.optional-dependencies].dev` exist; uvicorn entrypoint `backend.src.api.app:app` is correct; data dirs under `backend/data/` documented; provider-key example is inline/process-local with the explicit "never written to a file" statement (FR-022). No corrections needed.
- **T033 (README mirror):** rewrote `README.md` "Run Locally" to the Next **production** build path (`npm.cmd run build` → runtime `$env:NEXT_PUBLIC_API_URL` → `npm.cmd run start`), consistent with the runbook and the no-env-baked-into-build convention; points to `quickstart.md` for the full runbook.
- **T034 (first-time-follow validation):** `npm.cmd run build` compiled clean (TypeScript OK, 9 routes). Started uvicorn:8000 + the **production** frontend (`npm start`) on :3000 and exercised the primary flows end-to-end against the production build:

| flow | result |
|------|--------|
| all 9 frontend production routes (`/`, `/analyze`, `/portfolio`, `/help`, `/settings`, `/watchlist`, `/screen/[strategy]`, `/candidate/[ticker]`) | 200 |
| startup freshness (`GET /data/freshness`) | `any_stale=true`, `latest_session=2026-06-17` → gate would prompt (US1 verified in prod) |
| screen `midterm_52w_high_momentum` | 24 candidates, first=EA |
| candidate detail (EA) | 200 |
| advisor prompt export | self-contained, 24,010 chars, `personal_use_directive=false` (zero-directive) |
| portfolio quotes | 200 (TestClient probe); the prod-curl 422 was a shell JSON-escaping artifact, not a defect |

Production parity confirmed (same 24-candidate screen + advisor-prompt structure the suites validate); **0 missing/incorrect runbook steps** (SC-009, FR-021).

## T037 closeout (Phase 8 — SC-007)

Verified on 2026-06-18 that the findings table is fully triaged:

| severity class | findings | status |
|----------------|----------|--------|
| must-fix (`correctness`/`integrity`/`crash-hang`) | BUG-001, BUG-002, BUG-006, BUG-007 | all `fixed`, each with a regression test (`test_data_refresh.py`, `test_midterm_reference_tickers.py`, `error-states.test.tsx`, `test_robustness_run.py`) |
| `minor` (deferrable) | BUG-003 (cwd-sensitivity), BUG-004 (e2e mock drift), BUG-005 (portfolio-state isolation) | BUG-004/BUG-005 fixed; BUG-003 deferred with a one-line rationale (documented run command is repo-root; no correctness/integrity/crash impact) |

**0 untriaged findings, 0 open must-fix findings; the single deferral (BUG-003) carries a rationale.** SC-007 satisfied.

## T038 closeout (Phase 8 — New-this-feature verification, quickstart §C)

Re-ran the new-this-feature verification suites on 2026-06-18:

| target | tests | result |
|--------|-------|--------|
| `GET /data/freshness` < 3 s + no-mutation + network-disabled | `backend/tests/api/test_data_freshness.py` (+ `test_data_refresh.py`, `test_freshness.py`, `test_market_calendar.py`) | 10 passed |
| advisor prompt self-contained + per-input freshness | `backend/tests/agent/test_advisor_prompt.py`, `test_advisor_prompt_completeness.py` | passed (within the 10) |
| startup gate stale / current / unreachable | `frontend/tests/unit/StartupFreshnessGate.test.tsx` | 4 passed |

All §C behaviors verified green.
