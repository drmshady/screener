# Implementation Plan: Portfolio Import, Purchase-Anchored Levels & Risk-Aware Sizing

**Branch**: `013-portfolio-import-sizing` | **Date**: 2026-06-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/013-portfolio-import-sizing/spec.md`

## Summary

Turn the browser-local portfolio into a record of **what the owner actually bought**.
The owner keeps a Google Sheet of buy/sell transactions; the **browser** reads it via the
Google Sheets API using a short-lived, read-only OAuth access token (extending the existing
feature-010 Google sign-in) and POSTs the parsed transaction rows to a new backend
`POST /portfolio/import`. The backend validates every row, aggregates rows into **one
average-cost holding per ticker** (net shares, share-weighted average cost, earliest +
most-recent purchase dates), reports rejected rows, and persists the result into the existing
single-owner portfolio blob. For each open holding the backend then derives **two clearly
labelled level bases** by reusing the feature-011 `derive_bounded_levels` helper — an
**original-plan** stop/target frozen from the purchase price and the volatility *as of the
purchase date* (`build_single_ticker_snapshot(ticker, as_of=earliest_purchase_date)`), and a
**current-condition** stop/target recomputed on the latest snapshot but still anchored to the
purchase price — plus current price, distance-to-level, unrealized P/L, and a **risk-aware
sizing view** (recommended vs actual size + capital-at-risk) reusing the feature-011
`size_position` risk-per-trade backbone. No strategy rule, default, citation, indicator, or
backtest baseline changes — this is portfolio bookkeeping, purchase-date anchoring, and
presentation layered on existing pure logic.

A fourth, independent slice (US4) layers a **watch-until-entry-ready** view on the
existing watchlist: each saved candidate is re-checked against the latest snapshot via
the feature-012 entry-timing classifier (`GET /analyze/{ticker}`), surfaced as
informational status only. It adds no backend financial logic and no strategy change.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 15 + React 19 (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, pandas/numpy (backend); Next.js App Router,
TanStack Query, Zustand, Zod, Google Identity Services (GIS) browser token client + Google
Sheets REST API v4 (frontend). **No new backend dependency** — the backend never talks to
Google; it receives already-parsed rows as JSON.
**Storage**: existing single-owner JSON blob via `data/portfolio_store.py`
(`portfolio_state.json` under `SCREENER_DATA_DIR`); browser `localStorage` (Zustand `persist`)
mirrored to that blob by `PortfolioSync`. No new datastore.
**Testing**: pytest + hypothesis (backend), Vitest (unit) + Playwright (e2e, incl. the
existing no-directive-copy lint) (frontend).
**Target Platform**: same as the live deployment — **backend** is a Docker image built by
the GitHub Actions `daily-refresh.yml`, pushed to GHCR (`ghcr.io/drmshady/screener`) and
deployed to a **Hugging Face Space** (`occlusion2/screener`) carrying the baked read-only
snapshot; **frontend** is **Vercel** (Next.js). Also runs local single-user. (CLAUDE.md's
older "Render" wording predates the HF move — see [[deploy-012-and-code-only-deploys]].)
**Project Type**: web application (backend + frontend).
**Performance Goals**: import of a typical sheet (≤ ~500 transaction rows) validated +
aggregated in p95 ≤ 2 s server-side; per-holding levels/sizing reuse the existing
single-ticker snapshot path (already used by `/portfolio/quotes`). SC-001: full import
round-trip under 2 minutes of owner effort.
**Constraints**: deterministic for a given snapshot + portfolio (SC-006); every response
carries `data_as_of` + `disclaimer` (FR-019); zero directive language (FR-020); Google OAuth
token is short-lived, browser-only, **never written to any file or sent to the server as a
durable secret** (FR-001, consistent with [[api-keys-never-write]]); hosted-mode personal-use
directive stays forced OFF (FR-022).
**Scale/Scope**: one owner, one portfolio; USD only for v1; coverage limited to the existing
universe/snapshot for current price + volatility.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Data Integrity & Provenance (NON-NEGOTIABLE) | PASS | Current price + volatility come only from the existing licensed snapshot path; transaction prices/dates are owner-supplied facts about their own fills (not market data we publish) and are tagged with the import time + sheet identity. Out-of-coverage tickers are shown but marked not-priceable (FR-023). No new external market-data source. |
| II. Strategy Transparency & Peer-Reviewed Foundations | PASS | No strategy added or changed. Levels reuse the documented `derive_bounded_levels` contract; sizing reuses the documented risk-per-trade backbone. The cost-basis aggregation method (average cost) is documented in data-model.md. |
| III. Reproducible Backtesting & Bias Avoidance (NON-NEGOTIABLE) | PASS | No backtest, baseline, or strategy parameter touched (FR-021). Determinism preserved: same snapshot + same portfolio ⇒ byte-identical levels/sizing (SC-006), enforced by an integration test. |
| IV. Test-First for Financial Logic | PASS | New pure logic — transaction→holding aggregation, average-cost basis, capital-at-risk, over-risk flagging, purchase-date level anchoring — ships with fixture-anchored unit tests written first. No indicator math changes. |
| V. User Safety, Risk Disclosure & No-Advice Boundary | PASS | All portfolio surfaces stay descriptive: breach/target/over-risk are informational status, never "buy/sell/recommended" (FR-020), enforced by the existing Playwright no-directive lint extended to the new surfaces. Every response carries `data_as_of` + `disclaimer` (FR-019). Hosted personal-use directive forced OFF and non-waivable (FR-022). Google OAuth token handled client-side, short-lived, never logged or persisted (FR-001). |

**Result**: PASS — no violations, Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/013-portfolio-import-sizing/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── portfolio-import.md
│   └── portfolio-holdings.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── portfolio.py              # + Transaction, ImportRequest/Result,
│   │                                 #   Holding, HoldingLevels, HoldingRisk,
│   │                                 #   PortfolioHoldingsResponse models
│   ├── portfolio/
│   │   ├── transactions.py           # NEW: pure parse/validate rows → accepted/rejected
│   │   ├── aggregation.py            # NEW: pure transactions → average-cost holdings (idempotent)
│   │   ├── holding_levels.py         # NEW: original-plan + current-condition levels per holding
│   │   │                             #   (reuses strategies/levels.derive_bounded_levels)
│   │   ├── holding_risk.py           # NEW: recommended-vs-actual size + capital-at-risk
│   │   │                             #   (reuses portfolio/sizing.size_position backbone)
│   │   ├── sizing.py                 # unchanged (reused)
│   │   └── exposure.py               # unchanged (reused)
│   ├── api/
│   │   └── portfolio.py              # + POST /portfolio/import, POST /portfolio/holdings
│   └── screening/engine.py           # reused: build_single_ticker_snapshot(ticker, as_of=…)
└── tests/
    ├── portfolio/                    # NEW: transactions, aggregation, holding_levels, holding_risk
    ├── api/                          # + import + holdings endpoint contract tests
    └── integration/                  # + determinism + idempotent re-import

frontend/
├── src/
│   ├── lib/
│   │   ├── googleSheets.ts           # NEW: GIS token + Sheets API read → raw rows (browser-only)
│   │   ├── api.ts                    # + import/holdings clients + fetchEntryStatus (US4)
│   │   └── store.ts                  # + Transaction[] + transactions hash, Holding anchoring fields;
│   │                                 #   + last-seen entry-timing per watch entry (US4)
│   ├── components/
│   │   ├── ImportTransactions.tsx    # NEW: connect-sheet + import-summary UI
│   │   └── CandidateRow.tsx          # US4: ensure "Add to watchlist" control is reachable
│   └── app/
│       ├── portfolio/page.tsx        # + purchase-anchored levels + risk view columns/sections
│       └── watchlist/page.tsx        # US4: live watch-until-entry-ready view
└── tests/
    ├── unit/                         # + aggregation/format + import-summary + watchlist entry-readiness rendering
    └── e2e/no-directive-copy.spec.ts # extended to the new portfolio + watchlist surfaces
```

**Structure Decision**: Existing **web application** layout (Option 2). The genuinely new
work is four small pure backend modules under `backend/src/portfolio/` (parse, aggregate,
per-holding levels, per-holding risk) wired through two new routes on the existing
`api/portfolio.py`, plus a browser-only Google Sheets reader and import UI on the frontend.
Everything financial reuses feature-011 helpers unchanged.

## Deployment Compatibility (GitHub Actions + Hugging Face + Vercel)

The feature is designed to drop into the existing pipeline with **no CI, image, or hosting
change** beyond one new public frontend env var. Specifics:

1. **No new backend dependency, no ingest, no image change.** The backend never contacts
   Google — it only receives parsed rows — so `backend/pyproject.toml` and the Dockerfile are
   untouched. `POST /portfolio/import` writes only the small JSON portfolio blob (exactly like
   the existing `PUT /portfolio/state`); `POST /data/refresh` stays the only blocked-in-hosted
   ingest route. The `daily-refresh.yml` build/push/HF-deploy chain is unaffected.
2. **`/portfolio/holdings` reuses the already-deployed single-ticker path.** It calls
   `build_single_ticker_snapshot(...)` — the same function the live `POST /portfolio/quotes`
   already calls on HF — so it inherits whatever works there. Original-plan levels use
   `as_of=earliest_buy_date`, served from the **baked read-only prices snapshot** (the `prices/`
   dir is COPY'd into the image), so purchase-date volatility needs no network. Any incremental
   yfinance fetch/`save_prices` is best-effort cache to the **ephemeral** container fs, never a
   correctness dependency.
3. **Persistence rides the browser, not the HF disk.** The HF container filesystem is ephemeral
   and is rebuilt on every daily deploy, so `portfolio_state.json` (which is **not** baked into
   the image) is wiped on each redeploy. That is fine because the durable copy is the browser:
   imported `transactions[]` live in the Zustand `persist` state (schema_version bumped) and
   `PortfolioSync` re-seeds the server blob from localStorage when the server is empty — the
   same survival mechanism the portfolio already relies on. Holdings/levels/sizing are never
   persisted; they are recomputed deterministically from `transactions[]` + snapshot.
4. **Browser → Google is direct; browser → backend stays behind the BFF.** The owner's
   short-lived Google token is used **only** for the browser→Google Sheets read; the parsed rows
   then go browser → Next BFF (same-origin, which injects `X-Owner-Secret`) → backend, so the
   new routes inherit the feature-010 owner-secret gate and CORS pin with no change. The Google
   token never reaches the backend or any log/file (FR-001).
5. **One new Vercel env var: `NEXT_PUBLIC_GOOGLE_CLIENT_ID`** (a *public* OAuth client id, not a
   secret) reusing the **same Google Cloud OAuth app as feature 010's sign-in**, with the
   incremental `spreadsheets.readonly` scope and the Vercel domain + `localhost` added to the
   authorized JS origins. Because `NEXT_PUBLIC_*` is build-time inlined, the import UI must
   **degrade gracefully when the id (or the GIS script) is absent** — the connect button is
   disabled with a note — so headless prod-build e2e never depends on Google or a build-time
   secret ([[windows-dev-runbook]], [[api-keys-never-write]]).

## Complexity Tracking

> No constitution violations — section intentionally empty.

## Phase 0 — Research

See [research.md](./research.md). All NEEDS CLARIFICATION resolved (import mechanism =
browser OAuth token flow; lot model = aggregated average cost; both confirmed by the owner).

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — Transaction, Holding (with anchoring + derived blocks),
  Portfolio, Import Result entities, validation + aggregation rules.
- [contracts/portfolio-import.md](./contracts/portfolio-import.md) — `POST /portfolio/import`.
- [contracts/portfolio-holdings.md](./contracts/portfolio-holdings.md) — `POST /portfolio/holdings`.
- [quickstart.md](./quickstart.md) — owner runbook: sheet layout, Google sign-in, import,
  reading the two level bases and the risk view.
- Agent context: `CLAUDE.md` SPECKIT block re-pointed to this plan.
- **Claude Project advisor pack re-sync** ([[claude-project-advisor-pack]]): feature 013
  reuses the bounded-levels + risk-per-trade math the pack already documents, but adds the
  *held-position* framing — two purchase-anchored level bases (original-plan vs
  current-condition) and recommended-vs-actual size + capital-at-risk. `04-workflow-and-prompts.md`
  Template C (trim/exit a held position) is upgraded to the feature-013 holdings shape, with a
  short standing note in `00-custom-instructions.md` and a re-sync line in `README.md`. No
  strategy rule/citation changes, so `01`/`02`/`05`/`06` are untouched.
