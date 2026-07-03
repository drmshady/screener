# Implementation Plan: Momentum Cockpit — Candidate Lifecycle Pipeline + Portfolio-Aware Fit

**Branch**: `016-momentum-cockpit` | **Date**: 2026-07-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/016-momentum-cockpit/spec.md`

## Summary

Add the **connective layer** the app has been missing: a momentum-only candidate
**lifecycle pipeline** (watch → ready → staged → owned → managing → exited) and a
portfolio- and regime-aware **fit/suitability** view, surfaced as a **cockpit that replaces
the static home page**. Nothing here changes a screening rule, gate threshold, indicator
definition, citation, or backtest baseline — the genuinely new synthesis (`score_fit`) is a
pure, deterministic function over numbers the app already produces (entry-timing from feature
012, sizing from 011/015, exposure/heat from 015, regime). Six user-visible slices plus the
guardrail work:

1. **Ready-and-fit synthesis (P1)** — a batch `POST /pipeline/board` (momentum-hardwired)
   amortizes one universe snapshot + one `aggregate_exposure`, runs each watched ticker
   through `compute_candidate_result` → `size_position` → `score_fit`, and returns a
   fit-ranked board. The cockpit shows the ranked list with inline sizing, a cumulative-heat
   preview, and a sector-clustering flag.
2. **Cash-first capital model (P1)** — the owner enters **available cash**; total capital
   derives = cash + market value of holdings; `size_position` gains an optional
   `available_cash` hard limit reported as `binding_constraint = "available_cash"`. Absent ⇒
   byte-identical to today (no flag, additive optional field).
3. **Readiness alerts + stage visibility (P2)** — "newly ready" badges, a "ready for N days"
   counter, a holdings-needing-attention list, and a `PipelineStageBadge` on every surface a
   ticker appears.
4. **In-app buy/sell transaction recording (P2)** — `POST /portfolio/transactions` +
   `DELETE /portfolio/transactions/{id}` reuse the existing import validator +
   `_assemble_holdings`; raw transactions are retained in the owner blob; the Google-Sheet
   import stays as a secondary bulk path.
5. **Portfolio win/loss (P2)** — a new pure `portfolio/pnl.py` computes realized P&L (FIFO
   over the transaction history, win/loss + win rate) and unrealized mark-to-market;
   additive/optional response fields ⇒ byte-identical when there are no closed lots;
   informational only.
6. **Momentum-only UI + optional directive framing (P2/P3)** — value + short-term are removed
   from every in-app entry point (home cards, nav, screen/compare links) while their code,
   registry entries, and tests stay in place and green (reversible). The optional directive
   label rides the existing `personal_use_directive()` flag (forced OFF hosted).

**Technical approach**: one new backend package `backend/src/pipeline/` (pure `fit.py` +
`api/pipeline.py` batch endpoint) and one new pure `backend/src/portfolio/pnl.py`; extend
`size_position` and `api/portfolio.py` in place; a new frontend `lib/pipeline.ts` selector +
`components/cockpit/*` and a reworked `app/page.tsx` (cockpit home) and `app/portfolio/page.tsx`
(cash-first inputs, record-transaction form, P&L card). Everything rides existing idioms: a
master `pipeline_enabled()` flag (default OFF → board 404s, home degrades to today's panels),
a frontend-owned `pipeline` key in the persisted store (backend never parses it), and the
existing owner-secret + BFF proxy + `data_as_of`/`disclaimer` envelope. No new external data
source, no new auth surface, no build-time env flag.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 15 App Router + React 19 (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, pandas/numpy, pytest + hypothesis (backend); TanStack Query, Zod, Vitest, Playwright (frontend)
**Storage**: Baked read-only Parquet/JSON snapshot under `backend/data/`; single-owner `portfolio_state.json` blob (now additionally retaining a raw `transactions` list); browser `localStorage` (Zustand persist) for portfolio/watchlist/pipeline/settings
**Testing**: pytest golden-fixture + contract + regression (financial logic test-first per Principle IV); Vitest unit + Playwright e2e (no-directive + `data_as_of`/`disclaimer` lints)
**Target Platform**: Hosted = HF backend Space (GHCR Docker image, factory-rebuild) + Vercel BFF frontend; local = `py -3.12` backend + Next prod build
**Project Type**: Web application (FastAPI backend + Next.js BFF frontend)
**Performance Goals**: Live-screen p95 ≤ 10 s (≤ 2 s cached), single-ticker page p95 ≤ 1.5 s (constitution). The board is a batch of single-ticker computations over a watchlist (tens of tickers, not the full universe); the shared-snapshot refactor keeps it within the single-ticker budget × N by building the universe once per request.
**Constraints**: Determinism (same snapshot + same portfolio → byte-identical board); `data_as_of` + `disclaimer` on every new response; zero directive language in the neutral/hosted path (Playwright-linted); hosted-mode `personal_use_directive()` forced OFF; owner state blob opaque to backend; no build-time env flag (Next prod build); secrets runtime-env only
**Scale/Scope**: Single owner/operator; board serves a watchlist of tens of momentum tickers; momentum is the only fully-served strategy for this feature (value/short-term retained but UI-removed)

**Deployment-compatibility notes** (compatible with the 010 hosted-mode architecture):
- New behavior is gated by `pipeline_enabled()` (default OFF). With it off, `/pipeline/board`
  404s and the frontend renders today's home — byte-identical to feature 015. No new
  in-host compute, no baked-snapshot change, no new external data source.
- New response fields (`available_cash`, `binding_constraint = "available_cash"`, `realized_pnl`
  / `unrealized_pnl` / `total_pnl` / `win_rate`, `PipelineBoardResponse`) are additive/optional
  on the same-origin BFF proxy; frontend Zod schemas widen without breaking older payloads.
- One new router (`api/pipeline.py`) and two new portfolio routes (`/portfolio/transactions`
  [POST], `/portfolio/transactions/{id}` [DELETE]) register behind the existing owner-secret
  dependency and CORS pin — no new auth surface.
- Pipeline lifecycle state is a **frontend-owned** key synced via the existing debounced
  `PUT /portfolio/state`; the backend passes it through untouched (blob stays opaque).

**NEEDS CLARIFICATION**: none. All product decisions are settled in the spec (Assumptions):
momentum-only, UI-only strategy removal, FIFO cost basis, Sheet import kept secondary,
realized+unrealized P&L, cash-first sizing additive/optional, fixed documented fit weights.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| **I. Data Integrity & Provenance** (NON-NEGOTIABLE) | ✅ PASS | No new data source. The board reuses the existing point-in-time universe snapshot, EDGAR overlay, and quotes; P&L reads owner-recorded transactions + existing quotes. Every new response carries source-tagged `data_as_of`. Unrealized P&L degrades (flags "quote unavailable") rather than fabricating a mark. |
| **II. Strategy Transparency & Peer-Reviewed Foundations** | ✅ PASS | Zero change to any `rules()`, gate, threshold, ranking, or citation. `score_fit` is a *presentation/synthesis* layer over existing outputs, not a screen; its facts + weights are documented constants in `fit.py`. Momentum-only is honest — entry-timing readiness (012) is only defined for momentum. Value/short-term strategy code + registry entries are untouched (UI-removed only). |
| **III. Reproducible Backtesting & Bias Avoidance** (NON-NEGOTIABLE) | ✅ PASS | No backtest baseline, window, cost model, or re-baseline touched. FIFO realized P&L is a deterministic accounting of the owner's own trades, not a strategy backtest — it never feeds sizing/levels/ranking. |
| **IV. Test-First for Financial Logic** | ✅ PASS | `score_fit`, the `available_cash` sizing constraint, and `compute_realized_pnl` (FIFO) each land golden-fixture/regression tests before the logic (phases 0, 1, 6). Existing suites stay green with zero silent skips (phase 8 asserts value/short-term suites unchanged). |
| **V. User Safety, Risk Disclosure & No-Advice Boundary** | ✅ PASS | Neutral path is zero-directive (Playwright-linted on the new home). The directive `directive_label` is a *separate optional field* populated only when `personal_use_directive()` AND not hosted, with a test asserting it is never present hosted. "Buy"/"Sell" transaction sides record *past owner fills* (like the existing import), not advice. P&L uses neutral labels ("Realized gain/loss", "Win rate"). Every new surface carries `data_as_of` + `disclaimer`. |

**Result**: No violations. Complexity Tracking below is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/016-momentum-cockpit/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output — decisions + rationale
├── data-model.md        # Phase 1 output — new/extended entities
├── quickstart.md        # Phase 1 output — local runbook + manual verification + deploy
├── contracts/           # Phase 1 output — API contracts
│   ├── pipeline-board.md
│   ├── portfolio-transactions.md
│   ├── sizing-available-cash.md
│   └── portfolio-pnl.md
├── checklists/
│   └── requirements.md  # (pre-existing, from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

New: one backend pipeline package + one pure P&L module + frontend cockpit surface. Extends
existing files in place otherwise. No new subsystem beyond the pipeline package, no new data
source, no new auth surface.

```text
backend/
├── src/
│   ├── lib/
│   │   └── flags.py                     # + pipeline_enabled() (default OFF), fit_reward_to_risk_floor() (1.5); reuse personal_use_directive()
│   ├── pipeline/                        # NEW package
│   │   └── fit.py                       # pure score_fit(facts) → FitResult; documented constant weights; neutral + gated directive vocab
│   ├── models/
│   │   ├── pipeline.py                  # NEW — FitFacts, FitResult, PipelineBoardResponse/Item
│   │   └── portfolio.py                 # + optional realized/unrealized/total P&L + win_rate; Transaction retained; available_cash
│   ├── portfolio/
│   │   ├── sizing.py                    # size_position gains optional available_cash hard limit + "available_cash" binding constraint
│   │   ├── exposure.py                  # aggregate_exposure reused (one call per board request)
│   │   └── pnl.py                       # NEW pure — compute_realized_pnl (FIFO) + unrealized mark-to-market helpers
│   └── api/
│       ├── pipeline.py                  # NEW router — POST /pipeline/board (momentum-only; 404 flag-off; 422 other slug; per-ticker fail-soft)
│       ├── analyze.py                   # compute_candidate_result refactor: accept one prebuilt universe snapshot per batch
│       ├── portfolio.py                 # + POST /portfolio/transactions, DELETE /portfolio/transactions/{id}; retain raw txns; P&L in totals
│       └── app.py                       # register pipeline router
└── tests/
    ├── pipeline/    portfolio/    contract/   # test-first: fit table, available-cash sizing, FIFO P&L, board + transactions contracts

frontend/
└── src/
    ├── lib/
    │   ├── pipeline.ts                  # NEW — pure derivePipelineStage selector (precedence) + cumulative-heat helper
    │   ├── store.ts                     # persist v6→7: + pipeline key, + Portfolio.available_cash (seed from dormant cash_balance_override); derived total capital
    │   └── api.ts                       # + fetchPipelineBoard, transaction mutations; widen Zod for available_cash / P&L / directive_label
    ├── components/
    │   ├── cockpit/                     # NEW — HeatGauge, ReadyFitList, WatchingList, AttentionList, PipelineStageBadge, TransitionAlert
    │   ├── PortfolioSync.tsx            # include pipeline key in sync payload + change-detection guard
    │   ├── AppShell.tsx                 # strip nav links to value/short-term/compare (momentum-only)
    │   └── CandidateRow.tsx             # render PipelineStageBadge
    └── app/
        ├── page.tsx                     # REWORK → cockpit home (status strip, regime, heat gauge, ready&fit, watching, attention); graceful 404 fallback; remove non-momentum cards
        └── portfolio/page.tsx           # cash-first inputs (Available cash → derived Total capital), record-transaction form + editable list, P&L summary card + realized-trades table
```

**Structure Decision**: Web application (existing `backend/` + `frontend/` split). One new
backend package (`pipeline/`) plus one pure module (`portfolio/pnl.py`); everything else is an
in-place extension. The cockpit is the home page in place (no `/cockpit` route). The deploy
surface (baked snapshot + BFF proxy + owner-secret + env flags) is exactly as 010/011/015
established it, extended only additively.

## Complexity Tracking

> No Constitution Check violations. No entries required.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
