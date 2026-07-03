# Quickstart: Momentum Risk & Validation Hardening (015)

Local dev + gated re-baseline + deploy runbook. Windows PowerShell 5.1 primary; use
`py -3.12` and `npm.cmd` (see the project Windows dev runbook). Every new knob defaults to
**today's** output — a plain build with flags unset is byte-identical to production now.

## 0. Environment

```powershell
# from repo root
py -3.12 -m venv .venv ; .\.venv\Scripts\Activate.ps1
py -3.12 -m pip install -r backend/requirements.txt
```

## 1. Test-first (Principle IV / FR-016) — before any logic lands

Add/extend golden + regression tests, confirm they fail, then implement:

```powershell
# backtests: cost model, cadence, per-period reliability flag
py -3.12 -m pytest backend/tests/backtests -q
# levels: honest stop attribution + reward-ceiling recalibration/omission (US6)
py -3.12 -m pytest backend/tests/strategies/test_levels.py -q
# portfolio: trailing block (US3), conservative fallback + heat (US4)
py -3.12 -m pytest backend/tests/portfolio -q
```

Run the **full** backend suite from the **repo root** (not backend/) so imports resolve
(deploy-010 gotcha), with zero silently-skipped financial-logic tests (FR-016):

```powershell
py -3.12 -m pytest -q
```

## 2. Strengthened backtest — run LOCALLY, then compare (US1, US2)

The committed baseline is `backend/data/backtests/midterm_52w_high_momentum.json`, **baked
into the image** and served read-only. Regenerate it locally — never in the hosted backend.

```powershell
# fixed-horizon, finer cadence + cost (US1)
$env:SCREENER_BACKTEST_REBALANCE = "Q"
$env:SCREENER_BACKTEST_COST_BPS  = "10"
py -3.12 -m backend.src.backtests.runner --strategy midterm_52w_high_momentum --start 2008-01-01 --end 2024-12-31

# modeled exits (same stop/target the live screen shows) for the comparison (US2)
py -3.12 -m backend.src.backtests.runner --strategy midterm_52w_high_momentum --modeled-exits
```

Expected (SC-001/002): trade count materially larger than ~80, entries across multiple
rebalance dates per year, `cost_model.applied = true`, and the `costs` bias-check line reads
"modeled: 10 bps/side".

## 3. Gated re-baseline (US2/US5 — FR-006, "test, don't trust")

Produce the fixed-horizon vs modeled-exit (and, for US5, with/without regime overlay)
comparison artifact and record a verdict. **Only** overwrite the committed baseline JSON if
the artifact documents an improvement; retain the artifact either way.

```powershell
# regime-aware risk budget overlay is opt-in; measure its drawdown effect (US5)
$env:SCREENER_REGIME_RISK_BUDGET = "1"
# ... re-run comparison, diff drawdown, write verdict ...
```

Do **not** flip a default (cadence, exit model, regime overlay) into the served baseline
without the documented improvement (Constitution Principle III governance).

## 4. Drive the live app (owner validation — US3, US4, US7)

```powershell
# backend
py -3.12 -m uvicorn backend.src.main:app --reload
# frontend (prod build for headless parity)
cd frontend ; npm.cmd run build ; npm.cmd run start
```

Verify:
- **Candidate card**: risk distance (entry−stop) + reward-to-risk visible, neutral language.
- **Winning holding**: three protective levels (original plan / current condition / trailing)
  with at-a-glance status; the trailing stop sits **above** average cost (SC-004).
- **Sizing with no stop**: conservative size < legacy cap-fill; reasoning says so (SC-005).
- **Sizing near heat ceiling**: reduced, `binding_constraint = portfolio_heat`, headroom shown.
- **Regime overlay ON in an unfavorable regime**: lower effective risk fraction (SC-006).
- **Walk-forward panel**: thin-sample years visually flagged (SC-011).
- Every affected surface: `data_as_of` + `disclaimer` present, **zero** directive language.

## 5. Lints (SC-009)

```powershell
cd frontend ; npm.cmd run test ; npx playwright test   # no-directive + disclaimer e2e lints
```

## 6. Deploy (unchanged path — 010/011/012)

Regenerate the baseline locally (step 2), commit the artifact + code, then ship through the
**existing** chain. The hosted backend runs no heavy backtest and never writes the baked
snapshot.

```powershell
# local owner publish (bakes backend/data + code into the GHCR image, factory-rebuilds HF)
powershell -ExecutionPolicy Bypass -File scripts\publish_chain.ps1 -Deploy
# OR code-only: push branch (Vercel) + Daily-Refresh with force_rebuild=true for the HF image
```

Notes:
- All `SCREENER_*` knobs are process-local env / hosted Space secrets — **never** written to
  any artifact file (api-keys-never-write rule; secret_scan.ps1 stays clean).
- With flags unset and the baseline not re-baked, the deploy is byte-identical to today —
  safe to ship the code changes first and re-baseline separately once the verdict is in.
- Green-build discipline: full backend + frontend suites pass from a clean checkout before
  publish.
