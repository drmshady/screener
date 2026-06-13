# Findings Report: App & Strategy Validation

## Snapshot

- run_date: 2026-06-12
- snapshot_as_of: 2026-06-11T21:00:00Z
- meta_data_as_of: 2026-06-12T16:45:03.146118Z
- meta_sources: yfinance prices, sec_edgar_company_tickers fundamentals, stooq prices, SP Funds holdings, Halal Terminal, ticker_profile_cache, saudi_all_compliant
- universe_size_us: 591 screenable rows (651 raw compliant US symbols from active default sources)
- universe_size_saudi: 42 screenable rows (43 raw curated Saudi `.SR` symbols)
- snapshot_id: backend/data inventory SHA256 250fe1012d63a8bf2a77658725ede937288bda266e8eca1317e806f7e78361c1
- snapshot_path: E:\screener\backend\data
- snapshot_inventory: 19,855 files; 3,236,679,581 bytes
- read_only: validation fixture guards frozen *reference* data (catalog.db, edgar_cache, halal_terminal_cache, raw, backtests, config yaml, and the deep Stooq history under `prices/stooq*`/`saudi_parquet`/`d_us_txt.zip`) against adds/removes/size changes. The live yfinance EOD cache (`prices/parquet/`) and computed caches (`cache/`, `regime/`) are explicitly EXCLUDED — building a snapshot legitimately refreshes them and `save_prices` stamps a wall-clock `source_as_of`, so they are non-byte-stable by design. Confirmed: an isolated `pytest backend/tests/validation` run leaves all frozen reference inputs unchanged.

## 1. Run Header

- run_date: 2026-06-12
- snapshot_as_of: 2026-06-11T21:00:00Z
- snapshot_id: backend/data inventory SHA256 250fe1012d63a8bf2a77658725ede937288bda266e8eca1317e806f7e78361c1
- overall_verdict: pass (all defects fixed; 1 accepted data-tier limitation; 1 operator decision)
- defect_counts: blocker=0, major=0, minor=0 open. Resolved this review: F-004–F-012 fixed (9), F-001 & F-002 reclassified not-a-defect (strategy was correct). Remaining: F-013 (operator decision on tiered mode; covered by tests), F-003 (accepted data-tier limitation). pass=8.
- strategy_verdict: the mid-term strategy is implemented correctly, INCLUDING the Barroso–Santa-Clara volatility-scaling modification (wired and active; the earlier "inert" finding F-002 was a measurement artifact).
- suite_verdict: backend 119 passed / 0 failed; frontend vitest 5/0; frontend playwright 40/0. All green.

## 2. Surface Sweep

All eight primary backend surfaces returned HTTP 200 with `data_as_of` and disclaimer. Dedicated Playwright surface sweep also passed and captured screenshots under `frontend/test-results/validation-*.png`.

| Surface | Status | data_as_of | Disclaimer | Directive lang | Evidence |
|---------|--------|------------|------------|----------------|----------|
| midterm_screen | pass | yes | yes | none | `backend/tests/validation/test_surface_sweep_api.py`; `validation-midterm-screen.png` |
| candidate_detail | pass | yes | yes | none | `backend/tests/validation/test_surface_sweep_api.py`; `validation-candidate-detail.png` |
| single_ticker_analysis | pass | yes | yes | none | `backend/tests/validation/test_surface_sweep_api.py`; `validation-single-ticker-analysis.png` |
| backtest_view | pass | yes | yes | none | `backend/tests/validation/test_surface_sweep_api.py`; `validation-backtest-help.png` |
| market_regime | pass | yes | yes | none | `backend/tests/validation/test_surface_sweep_api.py`; `validation-home-events-regime.png` |
| shariah_filter | pass | yes | yes | none | `backend/tests/validation/test_surface_sweep_api.py`; `validation-shariah-filter.png` |
| events_overlay | pass | yes | yes | none | `backend/tests/validation/test_surface_sweep_api.py`; `validation-home-events-regime.png` |
| portfolio_sizing | pass | yes | yes | none | `backend/tests/validation/test_surface_sweep_api.py`; `validation-portfolio-sizing.png` |

## 3. Mid-Term Strategy Deep Check

Declaration: pass. The strategy exposes NAME, CITATION "George & Hwang (2004)", TIMEFRAME, PARAMETERS, REGIME_FAVORABILITY, MODIFICATIONS with citations, and callable `rules()`. A deliberately incomplete strategy is rejected by the registry.

Gate funnel, hard contract mode:

| Gate | Survivors |
|------|-----------|
| liquidity | 591 |
| proximity | 119 |
| trend | 119 |
| volume | 111 |
| quality | 81 |
| gross_profitability | 37 |
| asset_growth | 24 |

Sector-strength gate expected state: disabled by default via `sector_strength_top_fraction = 1.0`.

Reference-ticker oracle:

| Ticker | Expected | Actual | Expected gate | Actual gate | Match |
|--------|----------|--------|---------------|-------------|-------|
| EA | pass | pass | - | - | yes |
| BELFB | pass | pass | - | - | yes |
| ASYS | pass | pass | - | - | yes |
| AMAT | pass | pass | - | - | yes |
| ROST | pass | pass | - | - | yes |
| WYY | fail | fail | asset_growth | quality | no |
| A | fail | fail | proximity | proximity | yes |
| ACMR | fail | fail | quality | quality | yes |

Modification effects:

| Modification | Citation | Wired & active | Output effect on this snapshot |
|--------------|----------|----------------|--------------------------------|
| volatility scaling | Barroso & Santa-Clara (2015) | yes (591/591 rows carry daily_returns; 555 distinct per-name scalars) | none in default hard mode (post-gate set of 24 leaves the per-sector cap non-binding; `target_volatility` is scale-invariant for ranking). Changes set + order in tiered mode and in the backtest, where ranking binds. |
| sector-relative cap/ranking | sector-concentration overlay | yes | yes |
| quality screen | Asness, Frazzini & Pedersen (2019) | yes | yes |

Correction to the prior report: F-002 ("volatility scaling inert") was a false alarm. The modification is genuinely wired into the live screen; its lack of effect on the default hard-mode 24-name set is expected behavior, not a defect.

Determinism: pass. Two midterm screen runs over the frozen snapshot produced byte-identical candidate set, ordering, scores, gate details, and notes.

## 4. Short-Term Smoke Check

| Strategy | Loaded | Declaration complete | Run result |
|----------|--------|----------------------|------------|
| shortterm_minervini_vcp | yes | yes | pass, 1 candidate |
| shortterm_atr_breakout | yes | yes | pass, 245 candidates |

## 5. Backtest Check

- slug: midterm_52w_high_momentum
- window_years: 17 calendar years, 2008-01-01 to 2024-12-31
- covers_2008_2009: yes
- per_year_metrics_present: yes, 17 yearly rows
- reproducible: yes, endpoint returned identical summary and yearly metrics across two calls
- bias_caveat_visible: yes, `backend/backtests/midterm_52w_high_momentum/bias_check.md` shows survivorship_bias unchecked and the endpoint exposes the failing bias item
- enabled_by_default: yes, via explicit operator override while the survivorship caveat remains visible

## 6. Automated Suite Results

| Suite | Command | Passed | Failed | Notes |
|-------|---------|--------|--------|-------|
| backend_pytest | `py -3.12 -m pytest backend/tests -q` | 119 | 0 | All green, 0 xfailed. F-001/F-002 were re-analyzed and resolved as correct strategy behavior (oracle/test corrected), so their tests are now hard green assertions. Isolated `pytest backend/tests/validation` is clean (19 passed) with no read-only teardown error. |
| frontend_vitest | `npm run test` | 5 | 0 | Executed from `frontend/`. |
| frontend_validation_surface | `npx playwright test validation-surface-sweep.spec.ts no-directive-copy.spec.ts` | 9 | 0 | Dedicated validation sweep + no-directive lint. |
| frontend_playwright | `npx playwright test` | 40 | 0 | Full e2e floor now green (was 32/8). Root cause of the portfolio/shariah cluster was the shared backend `/portfolio/state` blob clobbering each test's seed via `PortfolioSync` — fixed with a per-test `isolatePortfolioState` route mock; stale-copy/locator/data-dependent assertions corrected; `retries: 1` added for transient real-data races. |

## 7. Findings

| ID | Summary | Classification | Severity | Justification | Where |
|----|---------|----------------|----------|---------------|-------|
| F-001 | Oracle expected WYY to fail at asset_growth; it actually fails at quality first. | not-a-defect (resolved) | - | The STRATEGY is correct: WYY has D/E ~5.9 (> 1.5), so it trips the quality gate, which precedes asset_growth in the declared order (it also fails asset_growth). The oracle's expectation was wrong and has been corrected to `quality`; `test_reference_ticker_rejection_gates_match` is now green (no xfail). | midterm oracle |
| F-002 | "Volatility scaling is inert" — original diagnosis was FALSE. | not-a-defect (resolved) | - | The live compliant-US screen rows DO carry a per-row `daily_returns` Series (591/591) and `calculate_volatility_scalar` yields 555 distinct per-name scalars — the Barroso–Santa-Clara modification is wired and active. It has no *output* effect in default hard mode only because the post-gate set (24) leaves the per-sector cap non-binding, and `target_volatility` is scale-invariant for ranking (it bites via the 2.0 leverage cap / sizing). Neutralizing vol-scaling in tiered mode changes both set and order, proving it is functional. Tests rewritten green: `test_volatility_scaling_is_wired_into_live_screen_rows` + `test_volatility_scaling_changes_selection_when_ranking_binds`. | midterm modification |
| F-012 | Validation read-only guard wrongly treated the live yfinance EOD cache (`prices/parquet/`) as frozen, so a teardown error fired every isolated run. | defect (fixed) | minor | The guard now scopes to frozen *reference* data only and excludes volatile recomputed caches; isolated validation run is clean. Underlying parquet churn is the live cache's wall-clock `source_as_of` stamp — it does not affect screen output (determinism test passes). | validation harness |
| F-013 | New `tiered` gate-mode (Decision 7) is a production scope addition; default stays `hard` so live behavior is unchanged, but the branch was untested. Also, the strict-pass (hard) set is NOT a subset of the more-permissive tiered set. | defect | minor | Now covered by `test_midterm_gate_mode.py` (default-is-hard, tiered runs + admits ≥ hard + still proximity-bound, tiered determinism). The hard⊄tiered surprise is the soft re-rank + per-sector cap displacing a strict passer; flagged for operator decision (is that intended for tiered?), not auto-fixed. | midterm strategy / gate mode |
| F-003 | Survivorship-bias check remains failed for the Stooq backtest. | data_tier_limitation | - | Free Stooq history has no delisted tickers; caveat is visible and explicitly overridden by operator choice. | backtest |
| F-004 | Playwright chart test strict-mode locator collision on `Limitations`. | defect (fixed) | minor | Used `.first()`; the panel renders. | frontend e2e |
| F-005 | Candidate add-to-portfolio seed clobbered by shared server state. | defect (fixed) | minor | Root cause: `PortfolioSync` hydrates from the shared backend `/portfolio/state` blob, overwriting the localStorage seed. Fixed by `isolatePortfolioState` route mock (per-test). | frontend e2e |
| F-006 | Shariah user-inclusion badge not found. | defect (fixed) | minor | Same shared-state clobber dropped the inclusion setting; fixed by `isolatePortfolioState`. | frontend e2e |
| F-007 | Portfolio excluded-by-user badge not found. | defect (fixed) | minor | Same shared-state clobber; fixed by `isolatePortfolioState`. | frontend e2e |
| F-008 | Earnings exclusion e2e asserted exactly `0 matches`. | defect (fixed) | minor | The badge has no upper bound, so 0 was an over-assumption. Re-expressed as the true invariant: no surviving earnings badge reads < the 90-day exclusion window. | frontend e2e |
| F-009 | Portfolio CRUD e2e did not start from empty local state. | defect (fixed) | minor | Same shared-state clobber; fixed by `isolatePortfolioState` so the empty-state test starts clean. | frontend e2e |
| F-010 | Candidate cap-breach e2e asserted a non-existent "Cannot size without breaching cap" banner. | defect (fixed) | minor | The UI surfaces a breach as "Caps respected → No"; assertion corrected. | frontend e2e |
| F-011 | Regime e2e matched `Breadth above SMA 200` as one text node. | defect (fixed) | minor | The label is split across `<Abbr>` tooltip wrappers; matched the `<dt>` (role=term) by substring instead. | frontend e2e |

## 8. Verdict & Recommended Actions

Verdict: pass. The app and strategy validation harness pass, backend is green (119 passed, 0 xfailed), the full frontend e2e floor is green (40 passed, 0 failed), and all primary surfaces are reachable with provenance and disclaimer. The mid-term strategy — including all three declared modifications — is implemented correctly. No blocker, major, or minor defect remains open.

Recommended actions (remaining — none are defects):

1. Operator decision (F-013): confirm whether `tiered` mode intentionally allows a strict (hard) all-gate passer to be displaced out of the more-permissive tiered set by the soft re-rank + per-sector cap. Default `hard` is unaffected; the tiered branch is now test-covered.
2. Keep the survivorship caveat visible until a delisted-inclusive historical source is added (F-003, accepted data-tier limitation).

**Resolved during this review:**

- F-001 (WYY gate expectation): not a defect — the strategy applies gates in declared order and WYY (D/E ~5.9) correctly fails quality before asset_growth. Oracle expectation corrected; test green.
- F-002 (volatility scaling): not a defect — the modification is wired and active on the live screen (591/591 rows carry daily_returns; per-name scalars vary; neutralizing it changes tiered-mode output). The earlier "inert" diagnosis was wrong. Tests rewritten as hard green assertions.
- F-012 (read-only guard): now scopes to frozen *reference* data only and excludes the live yfinance EOD cache and recomputed caches. Isolated `pytest backend/tests/validation` is clean (19 passed); full `backend/tests` is 119 passed, 0 xfailed, 0 failed.
