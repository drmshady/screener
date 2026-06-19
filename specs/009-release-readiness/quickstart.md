# Quickstart & Deployment Runbook: Release Readiness (009)

This is both the **release verification runbook** (US3/US4) and the **deployment
runbook** (US5, FR-020). It targets the personal-use, single-machine, Windows
scope. Production deployment = a local Next production build against the local
FastAPI backend; there is no hosted/multi-user target in v1.

Conventions (from the project's Windows dev runbook): `py -3.12`, `npm.cmd`,
**Next production build for headless**, and **no env var baked into the build**
(`NEXT_PUBLIC_API_URL` is supplied at runtime). Provider keys are inline /
process-local and are **never written to any file**.

---

## A. Deployment runbook (clean environment → running production build)

### 1. Prerequisites

```powershell
py -3.12 --version        # 3.12.x
node --version            # Node 20+
```

Confirm the data directories exist (created by the seed/ingest steps below):
`backend/data/` (prices store, `manifest.json`, EDGAR slim cache, calendars).

### 2. Backend

```powershell
py -3.12 -m pip install -e ".\backend[dev]"

# Seed + incremental data (first run pulls history; subsequent runs are incremental)
py -3.12 scripts\seed_universe.py
py -3.12 scripts\refresh_stooq_history.py
py -3.12 scripts\ingest_daily.py

# Start the API (production: no --reload)
py -3.12 -m uvicorn backend.src.api.app:app --host 127.0.0.1 --port 8000
```

### 3. Frontend (production build)

```powershell
cd frontend
npm.cmd install
npm.cmd run build
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:8000"   # runtime, NOT baked into build
npm.cmd run start
```

Open `http://127.0.0.1:3000`.

### 4. Optional provider keys (process-local only)

```powershell
# Example: independent-quote cross-check (harness only). Inline, never written to a file.
$env:SCREENER_INDEPENDENT_QUOTE_API_KEY = "..."
```

If a key is absent, the optional paid/cross-check path stays disabled and the
free-tier path remains the default and functional.

### 5. Smoke verification (primary flows)

1. **Startup freshness** — on first load, if data is stale the app prompts
   *Refresh now / Proceed on cached data*; if current, it shows data as current
   and does not refresh.
2. **Screen** — run `midterm_52w_high_momentum`; candidates render with levels,
   gates, and per-source freshness; an empty result shows an explicit empty-state.
3. **Candidate detail** — open a candidate; integrity warning (if any) is shown.
4. **Advisor prompt** — copy the prompt; confirm it is self-contained, lists
   per-input freshness, carries any integrity warning verbatim, and ends with the
   honesty block. Confirm zero directive language.
5. **Portfolio** — open portfolio; holdings + disclaimer render.

### 6. Finalization

```powershell
git status                 # working tree intended changes only
# run the suites (section B) — must be green
git add -A
git commit                 # on 009-release-readiness, suite-green
```

---

## B. Release verification (suites must be green)

### Backend

```powershell
py -3.12 -m pytest
```

Expectations (FR-011, SC-006): 100% pass; **0 silently skipped financial-logic
tests** (no `skip`/`xfail` on indicator or strategy tests); the seeded-defect
integrity suite (feature 008 CI gate) passes.

### Frontend

```powershell
cd frontend
npm.cmd run test           # Vitest unit
npm.cmd run test:e2e       # Playwright e2e (incl. no-directive lint + data_as_of/disclaimer presence)
```

Expectations (FR-012, SC-005): 100% pass; the directive-language lint and the
`data_as_of`/`disclaimer` presence checks pass on every page.

### Determinism check (SC-010)

Run the same screen twice on an unchanged snapshot and confirm identical
candidate order, regime, sizing, and event output; export the advisor prompt
twice and confirm byte-identical output.

---

## C. New-this-feature verification

- **`GET /data/freshness`** — returns per-source records + `any_stale`, completes
  well under 3 s, performs no mutation, and succeeds with the network disabled.
- **Startup gate** — stale → prompt; current → silent + "data is current";
  source unreachable → app fully usable on cached data with a staleness notice
  (never blocks the operator out).
- **Bug-scan log** — `bug-scan-log.md` has 0 open must-fix
  (correctness/integrity/crash-hang) findings; every fix has a regression test;
  deferrals carry a rationale.
