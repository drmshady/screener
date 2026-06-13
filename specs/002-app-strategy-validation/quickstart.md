# Quickstart: Running the App & Strategy Validation

**Feature**: 002-app-strategy-validation
**Audience**: The operator running the validation pass and reading the verdict.

This runbook takes you from a running app to a completed `findings-report.md`.
It assumes 001 is already set up (universe seeded, Stooq history pulled, daily
ingest run — see [001 quickstart](../001-screener-mvp/quickstart.md)).

---

## 0. Freeze the snapshot (reproducibility)

The validation runs read-only against the current `backend/data/`. Record its
`data_as_of` so the run is reproducible:

```powershell
# Note the snapshot freshness the app reports (the /meta staleness panel)
# and copy it into the report header. Do NOT run a fresh ingest mid-validation.
```

Pin the snapshot id (path or hash) in the report header. If you must re-ingest
later, that starts a *new* ValidationRun.

---

## 1. Start the app

```powershell
# Backend (terminal 1)
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.src.api.app:app --port 8000

# Frontend (terminal 2)
cd frontend
npm run dev
```

---

## 2. Run the regression floor (existing suites) — FR-015

```powershell
# Backend: pytest incl. indicators golden fixtures, contract, determinism, window floor
python -m pytest backend/tests -q

# Frontend unit + e2e
cd frontend
npm run test          # Vitest
npx playwright test   # includes disclaimer-everywhere + no-directive-copy lints
cd ..
```

Record passed/failed per suite in report §6. Every failure becomes a Finding.

---

## 3. Run the mid-term deep validation — FR-004/005/006/006a/007

```powershell
python -m pytest backend/tests/validation -q
```

This module (added by `/speckit-implement`) asserts, against the frozen
snapshot and per [contracts/midterm-gate-expectations.md](contracts/midterm-gate-expectations.md):
- declaration completeness + registry rejection of an incomplete stub,
- the declared gate order and the gate funnel,
- the reference-ticker oracle (WYY → asset_growth fail; EA/BELFB/ASYS/AMAT/ROST
  → candidates; proximity + quality fails),
- each modification has an observable effect,
- run-to-run determinism for the mid-term path.

---

## 4. Surface sweep — FR-001/002/003

```powershell
cd frontend
npx playwright test validation-surface-sweep.spec.ts
cd ..
```

Walks all eight surfaces (midterm screen, candidate detail, single-ticker
analysis, backtest view, regime, Shariah filter, events overlay, portfolio
sizing), capturing evidence and asserting `data_as_of` + disclaimer presence
and zero directive language on each. Fill report §2.

---

## 5. Backtest check — FR-009

```powershell
# Confirm the mid-term backtest window + per-year metrics + reproducibility
python -m pytest backend/tests/integration/test_backtest_window_floor.py -q
```

Also open the backtest view in the UI and confirm the survivorship-bias caveat
is still visible (see `backend/backtests/midterm_52w_high_momentum/bias_check.md`).
Fill report §5.

---

## 6. Classify findings and write the report — FR-013

Using [contracts/findings-report.schema.md](contracts/findings-report.schema.md),
write `findings-report.md`:
- Classify each non-pass as **defect** or **data-tier limitation** per
  [research.md](research.md) Decision 6 (e.g. stale-price tickers, banks-no-FCF,
  Saudi asset-growth skip, survivorship → limitations; wrong gate / missing
  disclaimer / non-determinism → defects).
- Set the overall verdict and the ordered must-fix list.

---

## 7. (If defects) fix and re-run

For each defect, fix the production code, re-run the relevant existing test +
the validation module, and update the report. A blocker defect makes the
verdict `fail` until resolved.

---

## Done

You have a reproducible `findings-report.md` answering "does the app work and
does the mid-term strategy work as intended" with evidence, classified
findings, and a go/no-go verdict.
