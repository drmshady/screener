# Implementation Plan: US Stock Screener MVP

**Branch**: `001-screener-mvp` | **Date**: 2026-06-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-screener-mvp/spec.md`

## Summary

Build a single-user, no-auth web app that screens the US-listed common-equity universe with peer-reviewed short-term and mid-term strategies, surfaces entry / stop-loss / take-profit levels per candidate, manages a user-entered portfolio with sector and capital-aware sizing, decorates candidates with earnings and material-news event badges, evaluates the broad-market regime, and optionally restricts the universe to Shariah-compliant tickers (default source: SPUS ETF holdings, matching the related Muhallib project). The product is read-only / advisory: it does not place trades and does not provide personalized advice.

Technical approach: a Python (FastAPI) backend hosts the screening engine, indicator library, data ingestion, and Shariah/events overlays; a Next.js + TypeScript frontend renders the dashboard, screen results, candidate detail, portfolio, and watchlist; the user's portfolio + settings persist client-side in `localStorage`. Market and fundamentals data live in a local SQLite + Parquet store on the backend, refreshed daily by a scheduled ingest job; all data layers stamp source name + as-of date per the constitution.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x on Node.js 20 LTS (frontend)
**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, pandas, numpy, SQLAlchemy (Core), httpx, pandas-ta (or talipp) for indicators, yfinance (current EOD), Stooq deep-history CSV bundles (delisted-ticker coverage for backtests), sec-edgar-downloader for filings. Optional paid upgrade (per-strategy quality call, not v1-blocking): EOD Historical Data $19.99/mo.
- Frontend: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, TanStack Query, Recharts (or visx) for charts, Zod for response validation.
**Storage**:
- Backend: SQLite for catalog/reference data (tickers, sector map, Shariah source, events); Parquet (pyarrow) for OHLCV time series; a `data/` folder per data source.
- Frontend (client): browser `localStorage` for portfolio, watchlist, settings — confirmed by spec assumption.
**Testing**: pytest + hypothesis (backend, with golden-fixture indicator tests per Constitution IV); Vitest + React Testing Library (frontend unit); Playwright (end-to-end on the running app).
**Target Platform**: Linux/macOS/Windows for local dev; Docker container as the deployable unit; modern desktop browsers (latest two versions of Chrome, Edge, Safari, Firefox) for the frontend.
**Project Type**: Web application (backend + frontend).
**Performance Goals**:
- Full-universe screen execution p95 ≤ 10 s cold, ≤ 2 s warm (per spec SC-002 and constitution).
- Single-ticker candidate detail p95 ≤ 1.5 s.
- Home dashboard (regime + events panel) p95 ≤ 1 s on returning user (per SC-015).
- Indicator unit tests: < 5 ms per indicator per test row.
**Constraints**:
- Determinism: same snapshot → identical screen, regime, sizing, event-badge output (Constitution III; spec SC-008, SC-014, FR-018).
- No directive trading language anywhere in UI copy (Constitution V; spec FR-007, SC-010).
- Every screen / detail / portfolio / export view MUST carry data as-of date + non-advice disclaimer (Constitution I+V; spec FR-005, FR-006).
- No personalized advice and no broker integration in v1 (spec assumption).
- Single-user, no-auth, browser-local persistence (spec assumption).
**Scale/Scope**:
- Universe: ~6,000 US-listed common equities post-filter (NYSE, NASDAQ, NYSE American).
- ~5 years of daily OHLCV at v1 launch (~7.5M rows compressed Parquet, ~150 MB).
- ~200 peer-reviewed Shariah-compliant tickers via SPUS at v1.
- v1 ships ≥ 1 short-term + ≥ 1 mid-term strategy enabled by default; v1 launch target ≥ 4 strategies.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The five constitutional principles and how this design satisfies them:

**I. Data Integrity & Provenance (NON-NEGOTIABLE)**
- Every data-layer module (prices, fundamentals, sector map, Shariah list, earnings calendar, 8-K feed, economic calendar) exposes records tagged with `source_name`, `source_as_of`, and a `provenance` field.
- The backend persists raw vendor responses to `data/<source>/raw/` before any normalization, so audits can re-derive cached values.
- Point-in-time: prices stored as adjusted + unadjusted; fundamentals stamped with the filing date they came from, never restated retroactively.
- Survivorship: delisted tickers are retained in the catalog with a `delisted_at` field and remain in historical backtest universes.
- **Pass** — design encodes provenance at every layer.

**II. Strategy Transparency & Peer-Reviewed Foundations**
- Every strategy lives in `backend/src/strategies/<slug>.py` and declares: `NAME`, `CITATION` (URL or full reference), `TIMEFRAME` (Short-term | Mid-term), `HOLDING_PERIOD`, `PARAMETERS` (with defaults and permitted ranges), `REGIME_FAVORABILITY`, and pure-function `rules(universe_df) -> candidates_df`.
- No ML / opaque weights in v1; all strategies are inspectable rule sets.
- A registry module enumerates strategies so the frontend can list them with their citations.
- **Pass** — structure forces explicit citation + rules per strategy.

**III. Reproducible Backtesting & Bias Avoidance (NON-NEGOTIABLE)**
- Backtests live under `backend/backtests/<strategy>/` with the data snapshot ID they used, deterministic results, and a bias-check checklist.
- The data layer exposes a `point_in_time(as_of)` slice so backtests never see future revisions.
- Delisted tickers are first-class in the universe loader.
- A random-seed harness (numpy and any RNG-touching code) is fixed per backtest run.
- **Pass** — backtest harness designed for reproducibility.

**IV. Test-First for Financial Logic**
- `backend/tests/indicators/test_<indicator>.py` ships golden fixtures (hand-calculated or vendor-published) for every indicator (RSI, SMA, EMA, ATR, MACD, 52-week-high, etc.) before any strategy uses it.
- CI runs `pytest backend/tests/indicators/ -q` on every commit touching `backend/src/indicators/` or `backend/src/strategies/`.
- Strategy rule tests use frozen mini-universes with known expected candidates.
- **Pass** — directory + CI gating enforces this.

**V. User Safety, Risk Disclosure & No-Advice Boundary**
- The backend's screen / candidate / portfolio responses include a `disclaimer` field and an `as_of` field; the frontend's layout shell unconditionally renders both on every page.
- A lint rule (or a simple grep in CI) rejects forbidden directive words ("Buy", "Sell", "Recommended", "Strong buy") anywhere in `frontend/`.
- No PII or credentials are collected, stored, or transmitted in v1 (no auth, no broker).
- **Pass** — disclaimer is a server-supplied field, copy lint enforces neutral framing.

**Data & Performance Standards** (from the constitution's standards section)
- Universe matches: US-listed common equities (NYSE, NASDAQ, NYSE American). ETFs excluded from screens; ETFs (SPY, QQQ, SPUS) used only as data feeds for regime + Shariah.
- Data sources allowed (personal-use scope): SEC EDGAR (free, public), `yfinance` for current EOD, Stooq for deep history + delisted-ticker coverage. The constitution's "licensed/permissive provider" clause is about redistribution; under personal-use scope (one user, single machine, no re-serving of vendor data) the yfinance/Stooq pair satisfies the spirit of the rule. The constraint is reinstated at any hosted/multi-user deployment; the `PriceProvider` interface keeps that swap local.
- Freshness SLAs encoded: EOD ≤ 1 trading day stale; fundamentals refresh within 2 business days; events sources have explicit per-source refresh intervals (FR-032, FR-033).
- Performance budgets translated into perf tests (see Phase 1 contracts).
- **Pass** — with the one prototype-data caveat tracked in research and the user's roadmap.

**Initial Constitution Check Result**: ✅ PASS. The earlier draft flagged `yfinance`'s no-redistribution TOS as a Principle I gap; under the now-explicit **personal-use scope** (one user, single machine, no re-serving of vendor data) that gap is resolved. The constraint is reinstated automatically at any hosted/multi-user deployment because the `PriceProvider` interface isolates the source — the swap is a one-file change.

**Post-Design Constitution Check Re-evaluation**: ✅ PASS. After Phase 1 (data-model.md + contracts/openapi.yaml + quickstart.md):

- **I. Data Integrity**: Every persisted entity in `data-model.md` carries `source_name` + `source_as_of`; the `/meta` endpoint surfaces per-source provenance to the UI; the daily ingest job records per-source success/failure in a manifest.
- **II. Strategy Transparency**: The `Strategy` entity in data-model.md mandates `citation`; the OpenAPI `Strategy` schema requires it. The four shipped strategies are named with their published methodologies in research.md (Decision 8).
- **III. Reproducible Backtesting**: `ScreenResult.id` is a deterministic hash of `(strategy, as_of_date, parameters, filters)`; backtests directory + bias-check checklist documented in quickstart §11; `point_in_time(as_of)` data-layer discipline recorded in data-model.md; backtest window for every enabled-by-default strategy MUST be ≥ 15 years including 2008-2009 (research.md Decision 15); walk-forward per-year metrics are exposed to users via `GET /strategies/{slug}/backtest` (research.md Decision 16), satisfying the "evidence visible to the user, not just to the developer" reading of Principle III.
- **IV. Test-First**: Quickstart §10 runs `pytest backend/tests/indicators` first; the directory is in the plan structure; `tests/indicators/` is non-optional in the task plan.
- **V. User Safety**: Every OpenAPI response schema with user-visible data has `disclaimer` and `data_as_of`; the Playwright "no directive copy" check is wired into the test plan; PII/credentials are absent by design (no auth, no broker, client-side state).

Complexity Tracking updated: the earlier "yfinance is a prototype price feed" item is **removed** — under personal-use scope it is not a deviation. No other constitutional deviations remain.

## Project Structure

### Documentation (this feature)

```text
specs/001-screener-mvp/
├── plan.md              # This file
├── research.md          # Phase 0 output — data source, indicators, Shariah, events decisions
├── data-model.md        # Phase 1 output — entity schemas
├── quickstart.md        # Phase 1 output — local dev runbook
├── contracts/           # Phase 1 output — OpenAPI for the backend
│   └── openapi.yaml
├── checklists/
│   └── requirements.md  # Spec quality checklist (already exists)
└── tasks.md             # Phase 2 output — created by /speckit.tasks, NOT here
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/                     # FastAPI routers
│   │   ├── strategies.py        # GET /strategies, POST /strategies/{id}/run
│   │   ├── candidates.py        # GET /candidates/{ticker}
│   │   ├── backtest.py          # GET /strategies/{slug}/backtest — walk-forward metrics
│   │   ├── regime.py            # GET /regime
│   │   ├── events.py            # GET /events/market, GET /events/ticker/{ticker}
│   │   ├── sizing.py            # POST /sizing
│   │   ├── shariah.py           # GET /shariah/status/{ticker}
│   │   └── meta.py              # GET /healthz, GET /meta (sources + as-of)
│   ├── models/                  # Pydantic schemas (response/request DTOs)
│   ├── data/                    # Source-tagged data loaders + caches
│   │   ├── universe.py          # NYSE/NASDAQ/AMEX listed tickers + delisted history; universe-wide liquidity gate (Decision 14)
│   │   ├── prices.py            # PriceProvider interface; yfinance for current EOD, Stooq for deep history + delisted
│   │   ├── stooq_history.py     # Quarterly Stooq bulk-CSV ingest (delisted-ticker coverage for backtests)
│   │   ├── fundamentals.py      # SEC EDGAR pull (XBRL → normalized)
│   │   ├── sectors.py           # SIC-based sector taxonomy
│   │   ├── shariah_spus.py      # SPUS ETF holdings loader
│   │   ├── earnings_calendar.py # Earnings dates loader
│   │   ├── filings_8k.py        # EDGAR 8-K feed
│   │   └── econ_calendar.py     # FOMC/CPI/NFP/PCE/PPI calendar
│   ├── indicators/              # Pure functions, golden-fixture tested
│   │   ├── moving_averages.py   # SMA, EMA
│   │   ├── momentum.py          # RSI, MACD, ROC
│   │   ├── volatility.py        # ATR, Bollinger
│   │   └── price_action.py      # 52w-high, breakouts
│   ├── strategies/              # One file per strategy; declarative metadata
│   │   ├── _registry.py
│   │   ├── midterm_52w_high_momentum.py   # with vol-scaling + sector-relative ranking + quality screen (research.md Decision 8)
│   │   ├── shortterm_minervini_vcp.py     # with ADR-ratio test + volume confirmation
│   │   └── shortterm_atr_breakout.py      # with trend-of-trend filter + Chandelier Exit (CAN SLIM deferred to v1.x)
│   ├── screening/               # Engine: universe → strategy.rules → ScreenResult
│   ├── backtests/               # Backtest runner + per-year walk-forward metrics (Decision 15, 16)
│   │   ├── runner.py            # Point-in-time backtest harness; consumes Stooq deep history
│   │   └── metrics.py           # Per-year hit rate, max drawdown, win/loss → exposed via /strategies/{slug}/backtest
│   ├── portfolio/               # Sizing, sector aggregation, cap enforcement
│   ├── regime/                  # Market regime calculator (SP500 vs 200-SMA + breadth)
│   ├── events/                  # Per-ticker + market event aggregation
│   ├── shariah/                 # Filter + per-ticker status lookup
│   └── lib/                     # disclaimer text, source provenance helpers
├── tests/
│   ├── indicators/              # Golden-fixture indicator tests (Constitution IV)
│   ├── strategies/              # Strategy rule tests against frozen mini-universes
│   ├── integration/             # Engine + data + API round trips
│   └── contract/                # Schema/contract tests against /contracts/openapi.yaml
├── backtests/                   # Per-strategy reproducible backtests (Constitution III)
└── data/                        # Raw + normalized snapshots (gitignored bulk; manifest tracked)

frontend/
├── app/                         # Next.js App Router pages
│   ├── page.tsx                 # Home dashboard (regime + market events panel)
│   ├── screen/[strategy]/page.tsx
│   ├── candidate/[ticker]/page.tsx
│   ├── portfolio/page.tsx
│   ├── watchlist/page.tsx
│   └── settings/page.tsx
├── src/
│   ├── components/              # Disclaimer, AsOfBadge, EventsBadge, ShariahBadge, etc.
│   ├── lib/
│   │   ├── api.ts               # Typed API client (Zod schemas mirror backend)
│   │   ├── store.ts             # localStorage portfolio/watchlist/settings store
│   │   └── copy.ts              # Centralized UI copy (linted for forbidden directives)
│   └── styles/
└── tests/
    ├── unit/                    # Vitest + RTL component tests
    └── e2e/                     # Playwright end-to-end specs

scripts/
├── ingest_daily.py              # Cron-style daily refresh of prices + 8-Ks + calendars
└── seed_universe.py             # First-time universe + sector seed
```

**Structure Decision**: Web app (backend + frontend) split. Backend is Python (FastAPI) because the screening engine is data-heavy and Python's pandas/numpy ecosystem aligns with the financial-indicator implementations and the constitution's "test against golden fixtures" requirement. Frontend is Next.js + TypeScript because the spec mandates browser-local persistence (matching the Muhallib v1 pattern) and a rich interactive dashboard; SSR also helps the dashboard render under 1 s (SC-015). The two halves communicate over a documented REST surface (`contracts/openapi.yaml`); the frontend never talks directly to any vendor.

## Complexity Tracking

> Filled only when Constitution Check has violations that must be justified.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _None at v1 launch._ The earlier yfinance redistribution caveat is resolved by the explicit personal-use scope (single user, single machine, no re-serving of vendor data). The `PriceProvider` abstraction means the constraint re-attaches automatically at any hosted/multi-user deployment. | — | — |
