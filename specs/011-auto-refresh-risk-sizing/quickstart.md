# Quickstart: Automated Refresh, Realistic Levels & Smarter Sizing (011)

Builds on the live feature-010 deployment (HF Docker Space backend + Vercel
frontend + `scripts/publish.ps1`). Windows dev: `py -3.12`, `npm.cmd`. Run pytest
from the repo root.

## 1. Enable the daily automation (US1)

1. In GitHub repo **Settings → Secrets and variables → Actions**, add the runtime
   secrets (never committed): provider keys, the GHCR push credential, and the HF
   deploy token (`HF_TOKEN`).
2. Add `.github/workflows/daily-refresh.yml` (cron after US close on weekdays;
   `workflow_dispatch` for manual runs). It runs the **shared publish chain**
   (refactored from `scripts/publish.ps1`):
   new-session guard → **incremental `ingest_daily` only** → integrity (008) →
   secret-scan → build (only if snapshot changed) → push GHCR → HF Factory-rebuild.
3. **Efficiency:** the daily job never runs the heavy Stooq deep-history bundle —
   keep that on its existing quarterly cadence (separate `workflow_dispatch` /
   infrequent schedule). Enable pip + docker layer caching in the workflow.
4. Verify: trigger `workflow_dispatch` once; confirm the Space rebuilds and the
   hosted `data_as_of` advances. On a weekend run, confirm a logged **no-op**.
5. Failure path: temporarily break a step in a test branch and confirm the run
   **aborts before publish**, the last snapshot stays live, and you get a failure
   notification.

## 2. Investigate & choose defaults (US4 — do this BEFORE adopting US2/US3)

```
py -3.12 tools/compare_methods.py --snapshot <frozen-id>
```

Produces the deterministic comparison artifact (per-method realism / robustness /
fair-value coverage + the backtest-baseline delta). Pick the level bounds, R,
reward ceiling, fair-value basis, and risk-per-trade fraction the artifact
justifies. Re-run ⇒ identical bytes (SC-007).

## 3. Land US2 (realistic levels) & US3 (sizing) test-first

- Write the level realism-bound property tests and the sizing risk/fair-value tests
  first (they must fail before the change). If a new intrinsic-value indicator is
  adopted, write its golden-fixture test first (Principle IV).
- Implement `derive_levels` v2, `size_position` v2, and (if adopted)
  `indicators/fair_value.py`. Wire the rationale + fair-value/trust fields through
  the API models and the frontend, keeping copy **zero-directive** and
  `data_as_of` + `disclaimer` present.
- Run full suites from repo root:
  ```
  py -3.12 -m pytest backend
  cd frontend; npm.cmd run test; npm.cmd run test:e2e
  ```

## 4. Gated backtest re-baseline (US4 / FR-020)

**Only if** the comparison artifact shows the level-driven modeled exits are an
improvement:

```
py -3.12 backend/src/backtests/runner.py --strategy midterm_52w_high_momentum --start 2008-01-01 --end 2024-12-31
```

with modeled exits enabled, then commit the regenerated
`backend/data/backtests/*.json` + `backend/backtests/<slug>/*` as a **deliberate,
one-time re-baseline**, with the constitution reproducibility re-check noted in the
commit. Never silent. If the artifact does **not** show an improvement, keep the
old baseline.

## 5. Verify the guarantees

- 100% non-degenerate levels within bounds, 0 over-ceiling targets (SC-003).
- Wider-stop → smaller size; no cap breach (SC-004). Fail-open when no fair value
  (SC-005). Byte-identical recompute (SC-006).
- Hosted directive mode still forced OFF; every response carries `data_as_of` +
  `disclaimer`; no secret in the repo or any artifact (SC-008).
- Full backend + frontend suites green; value tests still pass (SC-008/FR-022).
