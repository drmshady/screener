# Quickstart — Value Coverage & Correctness Hardening (007)

Local runbook (Windows, per the dev runbook: `py -3.12`, `npm.cmd`, backend binds
`127.0.0.1`). Order matters: coverage → correctness → disclosure → rebuild.

## 0. Baseline measurement (before any change)

```bash
py -3.12 -m backend.scripts.refresh_edgar_coverage --scope screened --dry-run --report e:/tmp/coverage_before.json
```
Records the `counts_before` (expected ≈ 530 stubs, 253 partial) — the numbers to beat (SC-001).

## 1. Coverage refresh (FR-001..FR-004)

```bash
# Re-fetch the fixable stubs/partials (real US filers); throttled, resumable.
py -3.12 -m backend.scripts.refresh_edgar_coverage --scope screened --report e:/tmp/coverage_after.json
# Bring the price warm store current for the full screened universe (fixes false "halted").
py -3.12 backend/scripts/ingest_daily.py
```
Verify: `coverage_after.json` shows `refetched > 0`, the residual `value_yield_missing` collapses toward the non-equity floor, and AMWD/CTRA/EXAS/HOLX no longer appear as "halted/suspended".

## 2. Strategy correctness (test-first — FR-005/006/007/014)

```bash
# Write the failing tests FIRST, confirm they fail:
py -3.12 -m pytest backend/tests/strategies/test_midterm_value_composite.py -q   # profitability gate, min-risk floor, -0.20 default
# Implement, then confirm green:
py -3.12 -m pytest backend/tests/strategies backend/tests/indicators -q
```
Checks: no candidate has negative earnings (CFO≤0/ROA≤0) in hard mode (SC-003); every candidate's `risk_per_share ≥ 1·ATR` (SC-004); defaults exclude 12-1 momentum < −0.20 (SC-005).

## 3. Disclosure fields + UI (FR-008..FR-012)

```bash
py -3.12 -m pytest backend/tests/api backend/tests/screening -q
cd frontend && npm.cmd run test && npx.cmd playwright test no-directive-copy.spec.ts
```
Checks: cheapness-cut + profitability gates render; sub-9 F-Score shows the low-confidence badge; sector grouping/cap visible; regime-blind banner on a regime-unavailable run; directive lint passes (SC-006/007/008).

## 4. Rebuild slim cache + regenerate the value backtest (FR-015)

```bash
SCREENER_VALUE_TREAT_AS_VALID=1 py -3.12 -m backend.src.backtests.runner \
    --strategy midterm_value_composite --start 2008-01-01 --end 2024-12-31
```
The slim cache rebuilds at schema v3 (dei + value tags). Confirm the artifact's `bias_check.survivorship_bias.passed` is still **false** and visible (SC-008) — coverage work must not hide it.

## 5. Re-sync the advisor pack (closing task)

Update `claude-project/00-custom-instructions.md`, `05-value-strategy-rules.md`,
`06-value-modifications-and-citations.md`: momentum floor is now **default ON at
−0.20**, the **profitability gate** (Piotroski CFO>0/ROA>0) is added, and the
**minimum-risk stop floor** is documented. Per the dev memory, re-sync whenever
the strategy code changes.

## 6. Live verification

```bash
SCREENER_VALUE_TREAT_AS_VALID=1 py -3.12 -m uvicorn backend.src.api.app:app --host 127.0.0.1 --port 8000
cd frontend && npm.cmd run dev
```
Open `/screen/midterm_value_composite`, run it, and confirm: the data-notes counts dropped, OIS-type loss-makers are gone, no degenerate stops, the regime banner and sector groups show, and the falling-knife toggle is on by default.
