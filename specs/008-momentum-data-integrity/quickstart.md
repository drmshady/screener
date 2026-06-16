# Quickstart: Strategy Defect Detection & Output Integrity (Momentum Pilot)

**Feature**: 008-momentum-data-integrity

Local runbook to exercise + verify the feature on real data (the operator's "drive the live app, don't trust a report" practice). Windows dev: use `py -3.12` and `npm.cmd`.

## 0. Prerequisites

- Backend deps installed in `backend/.venv`; warm price store + Stooq archive + EDGAR cache present (existing).
- For the harness independent cross-check only: set a free-tier quote key **process-local** (never write it to a file):
  ```powershell
  $env:SCREENER_INDEPENDENT_QUOTE_API_KEY = "<your-finnhub-free-key>"
  ```

## 1. Run the unit + invariant + seeded-defect suites (CI gate)

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/indicators tests/integrity tests/screening tests/strategies tests/agent -q
```

Expect: golden tests for the seam-adjustment helper pass; every invariant unit test passes; the **seeded-defect suite detects 100%** of injected classes (SC-001) with **zero false positives** on the control (SC-002); demote-ordering and determinism-with-warnings tests pass. The full backtest baseline tests remain green (SC-010).

## 2. Run the live momentum screen and inspect BELFB

```powershell
# backend
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --reload
```

Hit the momentum screen (frontend `/screen/midterm_52w_high_momentum` or `POST /strategies/midterm_52w_high_momentum/screen` with `as_of_date: "2026-06-12"`). Verify:

- **BELFB** either reconciles to a sane price with a non-spurious `return_12_1` (seam fixed, Decision 2) **or** carries a `data_integrity_warning` and is **demoted below all clean candidates** (FR-018, SC-003) — never a clean, unflagged top-rank on a ~35%-wrong price.
- Clean names (JBHT, CW) carry **no** data-integrity warning (SC-002).
- Each candidate shows its **12-1 momentum with sign** (IOSP visibly −9.8%, still listed — rank-only, FR-021/US5).
- `data_notes` records how many names were flagged/corrected (US4-AC4).
- Re-run the same `as_of_date`: identical figures **and** identical warning set (FR-024).

## 3. Verify the advisor-prompt propagation

Generate the screen advisor prompt for the same run. A flagged candidate's data-integrity warning appears **verbatim** in its candidate block and in the honesty footer (FR-019/SC-008). Directive flag behaviour unchanged (still OFF by default).

## 4. Run the offline harness (on demand — not a CI gate)

```powershell
cd backend
..\.venv\Scripts\python.exe ..\scripts\run_integrity_harness.py --as-of 2026-06-12 --out specs/008-momentum-data-integrity/harness-report.md
```

Open the report and confirm against `contracts/harness-report.schema.md`:

- §2 seeded defects: 100% detected, no control false positive.
- §3 cross-check: **zero `DIVERGES_UNFLAGGED`**; BELFB → `DIVERGES_AND_FLAGGED`; JBHT/CW → `AGREES`; missing source → `UNVERIFIED` (no crash); genuine staleness → `STALE`.
- §4 determinism confirmed (only `independent_fetch_at` varies between runs).

## 5. Frontend checks

```powershell
cd frontend
npm.cmd run build; npm.cmd run start   # prod build for headless
npm.cmd run test:e2e                    # Playwright, incl. no-directive-language lint
```

Verify the data-integrity badge is prominent and distinct from the soft-gate badge, 12-1 momentum + sign render, and no directive language was introduced.

## Done-when

All of SC-001…SC-011 hold: 100% seeded detection, 0 false positives, BELFB safe, 0 `DIVERGES_UNFLAGGED`, deterministic <5% overhead, warnings propagate + demote, value backstop re-expressed with no engine code, backtest baselines unchanged, 12-1 sign visible.
