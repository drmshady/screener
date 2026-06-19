# US Stock Screener MVP

Single-user US equity screener for mid-term and short-term strategies with explicit entry, stop-loss, take-profit, strategy citations, Shariah filtering, events, portfolio sizing, and market regime context.

This is an informational screening tool only. It does not place trades and it does not provide personalized financial, tax, legal, or religious advice.

## Current Shape

- Backend: FastAPI, Python 3.12, pandas/pyarrow local data stores.
- Frontend: Next.js 16, React 19, TypeScript.
- Data: local Stooq deep-history archive, yfinance incremental EOD cache, SEC EDGAR fundamentals/8-K cache, configurable Shariah sources, curated macro calendar.
- Specs and implementation plan: `specs/001-screener-mvp/`.

## Run Locally

Production build for headless/personal-use deployment. `NEXT_PUBLIC_API_URL` is
supplied **at runtime**, never baked into the build; provider keys are inline /
process-local and are **never written to any file**. The full deployment runbook
(prerequisites, data-directory locations, smoke verification, finalization) lives
in `specs/009-release-readiness/quickstart.md`.

```powershell
# Backend
py -3.12 -m pip install -e ".\backend[dev]"

py -3.12 scripts\seed_universe.py
py -3.12 scripts\refresh_stooq_history.py
py -3.12 scripts\ingest_daily.py

py -3.12 -m uvicorn backend.src.api.app:app --host 127.0.0.1 --port 8000
```

In another shell:

```powershell
# Frontend (Next production build)
cd frontend
npm.cmd install
npm.cmd run build
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:8000"   # runtime, NOT baked into the build
npm.cmd run start
```

Open `http://127.0.0.1:3000`.

## Validate

```powershell
py -3.12 -m pytest backend\tests -q
cd frontend
npm.cmd run lint
npm.cmd run build
npx.cmd playwright test
```

See `specs/001-screener-mvp/quickstart.md` for the full setup and smoke-test runbook, and `specs/001-screener-mvp/audit.md` for the honest implementation status and known caveats.
