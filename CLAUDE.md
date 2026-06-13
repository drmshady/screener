<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/002-app-strategy-validation/plan.md` (active feature 002), which builds
on the 001 MVP described below.

## Active feature: 002-app-strategy-validation

Validate that the built screener works end-to-end and that the **mid-term
strategy** (`midterm_52w_high_momentum`) behaves as its declared rules,
modifications, and George & Hwang (2004) citation promise. Reproducible
validation harness on a frozen snapshot → classified `findings-report.md`.
Plan: `specs/002-app-strategy-validation/plan.md`. Short-term strategies are
smoke-checked only.

## Prior feature: 001-screener-mvp

US Stock Screener MVP — single-user, no-auth web app screening US-listed
common equities with short-term + mid-term peer-reviewed strategies, plus
Shariah filter, news/events overlay, market regime, and portfolio +
capital-aware position sizing.

**Stack** (per `specs/001-screener-mvp/plan.md` and `research.md`):

- Backend: Python 3.12, FastAPI, Pydantic v2, pandas/numpy, SQLite + Parquet,
  pytest + hypothesis. Data sources (personal-use scope, all free): SEC EDGAR
  (filings, 8-Ks, company catalog), yfinance (current EOD), Stooq daily-bar
  bundles (deep history + delisted tickers — required for honest backtests
  covering 2008-2009), SPUS ETF holdings (default external Shariah source).
  The Shariah lookup is a **composite** — SPUS plus user-curated inclusion
  and exclusion lists (browser-local) — because SPUS tracks FTSE USA Shariah
  and therefore excludes many smaller compliant names. Optional paid
  upgrade per strategy: EOD Historical Data ($19.99/mo) if Stooq coverage
  proves insufficient.
- Frontend: Next.js 15 (App Router), React 19, TypeScript, Tailwind,
  TanStack Query, Recharts, Zod. Vitest + Playwright. Portfolio/watchlist
  persisted in browser `localStorage`.

**Authoritative documents** (read in this order before coding):

1. `.specify/memory/constitution.md` — non-negotiable rules (data integrity,
   strategy transparency, reproducible backtesting, test-first for financial
   logic, no-advice boundary).
2. `specs/001-screener-mvp/spec.md` — user stories US1–US6, 33 FRs, 15 SCs.
3. `specs/001-screener-mvp/plan.md` — technical context, constitution check,
   structure decision.
4. `specs/001-screener-mvp/research.md` — decisions + rationale + rejected
   alternatives for every tech choice.
5. `specs/001-screener-mvp/data-model.md` — entity schemas.
6. `specs/001-screener-mvp/contracts/openapi.yaml` — API contract.
7. `specs/001-screener-mvp/quickstart.md` — local dev runbook.

**Non-negotiables specific to this codebase**:

- Every API response that exposes user-visible data carries `data_as_of` and
  `disclaimer` fields. The frontend layout shell renders both unconditionally.
- Zero directive trading language in UI copy ("Buy", "Sell", "Recommended",
  "Strong buy") — Playwright lints this on every page.
- Every indicator in `backend/src/indicators/` has a golden-fixture test
  under `backend/tests/indicators/` BEFORE any strategy depends on it.
- Every strategy in `backend/src/strategies/<slug>.py` declares NAME,
  CITATION, TIMEFRAME, PARAMETERS, REGIME_FAVORABILITY, MODIFICATIONS (each
  with its own citation), and a pure-function `rules()` callable. The
  registry refuses to load strategies missing any of these.
- v1 strategy slate (research.md Decision 8): three fully-gated strategies —
  `midterm_52w_high_momentum` (with Barroso–Santa-Clara vol scaling +
  sector-relative ranking + QMJ-style quality screen),
  `shortterm_minervini_vcp` (with ADR-ratio contraction test + volume
  confirmation), `shortterm_atr_breakout` (with 200-day trend-of-trend filter
  default ON + Chandelier Exit trailing stop). A CAN SLIM-style strategy is
  intentionally deferred — do not ship a "lite" version under O'Neil's
  citation; build it properly when the Form 4 and analyst-revision data
  pipelines exist.
- Universe-wide liquidity gate (research.md Decision 14, FR-034) applies
  before any strategy runs: ADV ≥ $1M (20d), price ≥ $5. User-configurable.
- Backtest-window discipline (research.md Decision 15, FR-035, SC-017):
  every strategy enabled by default at launch is backtested across ≥ 15
  years including 2008-2009. Walk-forward per-year metrics are exposed to
  users via `GET /strategies/{slug}/backtest`.
- Personal-use scope is explicit: one user, one machine, no redistribution.
  Hosted/multi-user deployment is not in v1 and re-attaches the constitution's
  "licensed/permissive provider" data-source rule automatically through the
  `PriceProvider` interface.
- Same data snapshot → same screen, regime, sizing, event-badge output. No
  hidden randomness.

<!-- SPECKIT END -->
