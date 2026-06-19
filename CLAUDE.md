<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/010-online-deployment/plan.md` (active feature 010), which builds on the
009 release-readiness, 008 momentum data-integrity, 006 side-by-side compare, 005
value strategy, 004 advisor export, 003 comparison, 002 validation, and 001 MVP
below.

## Active feature: 009-release-readiness

A stabilization / release-readiness pass over the assembled screener — **no new
strategy and no strategy rule, default, citation, or backtest baseline change**.
Four workstreams: (1) **refresh-on-start** — a read-only, no-mutation startup
staleness check (`GET /data/freshness`, ≤ 3 s, latest-completed-trading-session
basis) that prompts the operator to refresh now (reusing the existing incremental
`POST /data/refresh`) or proceed on cached data — never silent/automatic;
(2) **advisor-prompt completeness** — make the export self-contained by adding
per-material-input freshness, keeping integrity warnings verbatim and the honesty
block driven by the real backtest bias check (builder stays pure/deterministic);
(3) **correctness, bug scan, cleanup & robustness** — full backend + frontend
suites green on a clean checkout (0 silently skipped financial-logic tests), a
bounded bug scan (`bug-scan-log.md`) with block-on-correctness/integrity/crash
fixes, dead-code removal, and graceful empty/missing/timeout paths — all
determinism-preserving; (4) **deployment readiness** — a reproducible production
runbook (`quickstart.md`) with documented data dirs + process-local keys, ending
in a suite-green commit. Momentum is primary; value is postponed (feature 007 not
merged) but its existing tests must still pass. Plan:
`specs/009-release-readiness/plan.md`.

## Prior feature: 008-momentum-data-integrity

Make the screener **detect when its own strategy output is wrong** via a
strategy-agnostic, invariant/contract-based detector (each strategy declares a
machine-checkable output contract; a shared engine validates every candidate).
Enforced from one definition in two places: a deterministic, no-network check on
**every live screen** (flagged candidates get a loud per-candidate
data-integrity warning and are **demoted below all clean candidates**, never
excluded) and an **offline harness** (seeded-defect regression as a blocking CI
gate + an independent free-tier-vendor cross-check, on-demand, non-blocking).
Momentum is the pilot. Alongside detection, the known momentum data defects are
remediated: `return_12_1`/`52w_high` compute from a split+dividend-adjusted
series (displayed entry stays the latest raw close), the cross-source seam stops
dropping `adj_close` and is back-adjusted onto one basis via the existing 5-day
overlap (flag where it can't be guaranteed), and price/fundamentals never cross
share classes. No strategy rule, default, citation, or backtest baseline
changes — detection, data correctness, and presentation only. Plan:
`specs/008-momentum-data-integrity/plan.md`.

## Prior feature: 006-midterm-sidebyside-compare

Add a **live-screen, four-variant side-by-side run** for the mid-term band plus a
**single four-variant advisor-prompt export**. In one action it runs both
mid-term strategies twice against one shared universe snapshot, toggling the one
A/B parameter each: momentum sector gate ON/OFF (`sector_strength_top_fraction`
0.5 vs 1.0) and value momentum floor ON/OFF (`min_momentum_12_1` -0.20 vs -1.0).
Orchestration + presentation only — **no strategy rule, default, or backtest
baseline changes**. Both toggles already thread through `run_strategy(parameters)`
→ `universe.attrs`. New work: a shared-snapshot matrix runner (build universe
once, evaluate four `rules()`), two endpoints (`POST /strategies/midterm-compare`
and `…/advisor-prompt`), a `build_midterm_matrix_advisor_prompt` reusing the
existing per-screen section builders, and a `/compare/midterm` frontend surface.
Distinct from 003 (which is a *backtest* bake-off, not a live screen). Each
strategy's failing survivorship bias-check is surfaced honestly per variant. Plan:
`specs/006-midterm-sidebyside-compare/plan.md`.

## Prior feature: 005-value-midterm-strategy

Add a second fully-gated **mid-term strategy** based on value:
`midterm_value_composite`. It ranks the liquid universe by a multi-metric value
composite (book/market, earnings, cash-flow, sales **yields**), gates value
traps with a Piotroski (2000) F-Score, and ranks the composite **within sector**
so financials/REITs aren't spuriously ranked. The genuinely new work is data +
indicators: a point-in-time `value_metrics_as_of` EDGAR extension and two
test-first indicator modules (`indicators/valuation.py`,
`indicators/piotroski.py`). It reuses the momentum strategy's engine,
reference-threshold cache, gate-accounting, level derivation, and backtest
runner, and plugs into the 003 comparison + 004 advisor export. Ships disabled
by default (Stooq survivorship still FAILS, surfaced honestly). Plan:
`specs/005-value-midterm-strategy/plan.md`.

## Prior feature: 004-advisor-prompt-export

Add a "Copy advisor prompt" capability: for a mid-term candidate, assemble a
self-contained, deterministic prompt (candidate gate results + price levels +
regime + the live strategy declaration with citations + a mandatory honesty
block driven by the backtest's real `bias_check`) that the user pastes into an
external AI advisor. A backend builder is the single source of truth; directive
framing is gated behind a personal-use flag (default off) and the Principle V
amendment (constitution v1.1.0). Plan:
`specs/004-advisor-prompt-export/plan.md`.

## Prior feature: 002-app-strategy-validation

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
  pipelines exist. Feature 005 adds a fourth, value-based mid-term strategy
  `midterm_value_composite` (multi-metric value composite — book/market,
  earnings, cash-flow, sales yields — gated by a Piotroski (2000) F-Score and
  ranked within sector). Like momentum it ships disabled-by-default while the
  free Stooq archive's survivorship check fails (override:
  `SCREENER_VALUE_TREAT_AS_VALID=1`). New point-in-time inputs come from
  `FundamentalsLoader.value_metrics_as_of`; its indicators live in
  `indicators/valuation.py` + `indicators/piotroski.py` (golden-fixture tested).
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
