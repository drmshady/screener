# Contract: Findings Report Structure

**Feature**: 002-app-strategy-validation

This is the required structure of `specs/002-app-strategy-validation/findings-report.md`,
the primary deliverable produced when the validation pass is executed
(during `/speckit-implement`). The report is the human-readable serialization
of the `ValidationRun` entity ([data-model.md](../data-model.md)). A report
missing any REQUIRED section is itself a process defect.

---

## Required sections (in order)

### 1. Run Header (REQUIRED)

- `run_date`, `snapshot_as_of`, `snapshot_id`
- **Overall verdict**: `pass` | `pass_with_defects` | `fail`
- Defect counts by severity (blocker / major / minor); data-tier-limitation
  count; pass count.

### 2. Surface Sweep (REQUIRED) — satisfies FR-001/002/003, SC-001/002/003

A table with one row per primary surface (all eight MUST appear):

| Surface | Status | data_as_of | Disclaimer | Directive lang | Evidence |
|---------|--------|-----------|------------|----------------|----------|
| midterm_screen | pass/fail | ✓/✗ | ✓/✗ | none/FOUND | ref |
| … (candidate_detail, single_ticker_analysis, backtest_view, market_regime, shariah_filter, events_overlay, portfolio_sizing) | | | | | |

### 3. Mid-Term Strategy Deep Check (REQUIRED) — satisfies FR-004/005/006/006a/007, SC-004/005

- **Declaration**: confirm NAME, CITATION (George & Hwang 2004), TIMEFRAME,
  PARAMETERS, REGIME_FAVORABILITY, MODIFICATIONS (with per-item citations),
  `rules()` present; and that the registry rejects an incomplete stub.
- **Gate funnel**: ordered table `gate → survivors`, gate order MUST match the
  declared sequence (liquidity → proximity → trend → volume → quality →
  gross_profitability → asset_growth).
- **Reference-ticker oracle**: table `ticker | expected | actual | expected_gate
  | actual_gate | match` (≥4 tickers spanning proximity, quality, asset-growth).
- **Modification effects**: table `modification | citation | has_effect`.
- **Determinism**: statement that two runs produced byte-identical output.

### 4. Short-Term Smoke Check (REQUIRED) — satisfies US2b

- One line per short-term strategy: loaded ✓, declaration complete ✓, ran
  without error ✓ (candidates or explained empty state).

### 5. Backtest Check (REQUIRED) — satisfies FR-009, SC-006

- `window_years` (≥15), `covers_2008_2009` (✓), `per_year_metrics_present`,
  `reproducible`, `bias_caveat_visible`, and the enabled-by-default override
  note.

### 6. Automated Suite Results (REQUIRED) — satisfies FR-015, SC-008

- One row per suite (backend_pytest, frontend_vitest, frontend_playwright):
  command, passed, failed. Each failure cross-referenced to a Finding.

### 7. Findings (REQUIRED) — satisfies FR-013, SC-007

A table of every non-pass observation:

| ID | Summary | Classification | Severity | Justification | Where |
|----|---------|----------------|----------|---------------|-------|
| F-001 | … | defect / data_tier_limitation | blocker/major/minor/— | one line | surface/gate |

Every `defect` row MUST have a severity; every non-`pass` row MUST have a
justification.

### 8. Verdict & Recommended Actions (REQUIRED)

- The go/no-go sentence and an ordered must-fix list (defects only), each
  pointing at the file/gate to change.

---

## Acceptance of the report

The report is **accepted** when:
- All eight surfaces are present in §2.
- The mid-term §3 oracle has ≥4 tickers and 100% match (or every mismatch is a
  logged defect).
- §5 confirms ≥15-yr / 2008–2009 window.
- §7 has zero unclassified findings.
- The verdict in §1 is consistent with the defect counts.
