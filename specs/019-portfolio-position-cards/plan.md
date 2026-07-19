# Implementation Plan: Portfolio Position Cards & Transaction Separation

**Branch**: `019-portfolio-position-cards` | **Date**: 2026-07-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/019-portfolio-position-cards/spec.md`

## Summary

Turn the Portfolio page from a spreadsheet-style holdings table into an at-a-glance
**decision surface**: one **position card** per open holding showing status/stage, current
stop-loss + target, recent news/events (each source + as-of), an auto-loaded AI
sentiment/narrative, and a deterministic **Hold / Trim / Sell** call. All buy/sell entry,
Sheet import, and the raw transaction ledger move to a dedicated **Transactions** page; a
fully-sold holding drops off the Portfolio page while its transactions stay auditable on
Transactions. The Portfolio page keeps a **realized win/loss summary** (counts, win rate,
total realized P&L).

This is **pure synthesis + reorganization over existing outputs** — **no** new screening rule,
gate, indicator, sizing model, or backtest baseline (FR-013). The only new backend logic is a
small **pure, deterministic instruction mapper** (`portfolio/instruction.py`) over signals the
app already computes — stop/target status, portfolio heat, and lifecycle stage — surfaced as an
additive per-holding field on the existing `POST /portfolio/holdings` response; it never factors
in the AI sentiment score (FR-007). The Hold/Trim/Sell **verbs** ride the **single-owner
directive carve-out** already established for feature 018 (personal-use flag ON **and**
owner-secret set **and** not multi-user); otherwise the card shows neutral, non-directive status
language (FR-008). Determinism, `data_as_of` + disclaimer on every card and the summary (FR-012),
and the zero-directive neutral default are preserved end-to-end.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript, React 19, Next.js 15 App Router (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2 (backend); TanStack Query, Zod, Tailwind (frontend)
**Storage**: Existing single-owner server blob (retained transactions) + browser `localStorage`. **No new store, entity, or persisted field.**
**Testing**: pytest + hypothesis (backend golden-fixture + determinism); Vitest + Playwright (frontend render + no-directive lint)
**Target Platform**: Feature-010 hosted deployment (Render backend + Vercel BFF-proxy frontend, single-owner allowlist) and local dev — byte-identical compute paths
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Portfolio shell (cards, levels, status, instruction) renders without blocking on sentiment/news fetches (SC-005); per-card sentiment + news load lazily in the background
**Constraints**: Same-inputs-same-output determinism (FR-007); `data_as_of`/staleness + disclaimer on every card and the summary (FR-012); zero directive language unless the single-owner carve-out holds (FR-008); reuse feature 014's ~$5/month sentiment spend cap + deterministic-template degrade (FR-006)
**Scale/Scope**: One owner, a typical personal portfolio (tens of holdings). New: 1 backend pure module + 1 additive response field; 1 new frontend route (`/transactions`), 1 restructured route (`/portfolio`), 1 `PositionCard` component + a realized-summary block. No new endpoint.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.2.0. This feature is presentation/synthesis + page reorganization (FR-013).

- **I. Data Integrity & Provenance (NON-NEGOTIABLE)** — PASS. No new datapoint is fetched.
  Cards render prices, levels, P&L, news/events, and sentiment from existing sourced pipelines;
  each news/event line already carries its source + as-of (FR-005), and cards degrade to an
  explicit "nothing new"/"no data" statement rather than a bare/"Unknown" state.
- **II. Strategy Transparency & Peer-Reviewed Foundations** — PASS (N/A). No screen or strategy
  is added or changed. The instruction mapper introduces **no** ranking or selection rule; it is
  a deterministic presentation mapping over already-computed status facts, with its thresholds
  documented in code.
- **III. Reproducible Backtesting & Bias Avoidance (NON-NEGOTIABLE)** — PASS (N/A). No backtest
  baseline, cost model, or window changes.
- **IV. Test-First for Financial Logic** — PASS. `derive_instruction()` ships with golden-fixture
  unit tests (breach → Sell, near-stop/heat-breach/deteriorating → Trim, healthy → Hold, and the
  insufficient-data path) written before the implementation and a determinism test; it changes no
  indicator numerics.
- **V. User Safety, Risk Disclosure & No-Advice Boundary** — PASS under the **single-owner
  directive carve-out** (v1.2.0). Hold/Trim/Sell verbs are gated behind the same mechanism as
  feature 018 (`SCREENER_PERSONAL_USE_DIRECTIVE=1` **and** an enforced owner-secret access gate
  **and** not multi-user); the default is neutral, non-directive status language (FR-008), and the
  recommendation/instruction is never dropped. Every card and the summary carry the strategy
  citation context, `data_as_of`, and the non-advice disclaimer (FR-012). The AI sentiment score
  is shown as context only and is **excluded** from the instruction (FR-007), so directive output
  stays rule-based and auditable. Owner records acceptance of the carve-out for this feature (per
  the v1.2.0 single-operator amendment note).

**Result**: PASS. No violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/019-portfolio-position-cards/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── holdings-instruction.md      # Additive /portfolio/holdings response fields
│   ├── directive-carveout.md        # Card-instruction single-owner directive gate
│   └── portfolio-cards-ui.md        # Portfolio/Transactions page + PositionCard contract
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── portfolio/
│   │   ├── instruction.py        # NEW — pure derive_instruction(): facts → Hold/Trim/Sell + neutral status
│   │   ├── aggregation.py        # (reused) net-quantity aggregation → open vs closed
│   │   ├── holding_levels.py     # (reused) stop/target/trailing per holding
│   │   ├── holding_risk.py       # (reused) capital-at-risk + heat inputs
│   │   └── pnl.py                # (reused) realized (FIFO win/loss) + unrealized P&L
│   ├── api/
│   │   └── portfolio.py          # EDIT — add per-holding `instruction` + top-level `directive_enabled` to /holdings
│   ├── models/
│   │   └── portfolio.py          # EDIT — additive InstructionBlock + response fields (optional/back-compatible)
│   └── lib/
│       └── flags.py              # EDIT — card-instruction directive gate (reuses the 018 single-owner carve-out)
└── tests/
    ├── portfolio/                # NEW — golden-fixture + determinism tests for derive_instruction
    └── api/                      # EDIT — /holdings additive-field + neutral-default contract tests

frontend/
├── src/
│   ├── app/
│   │   ├── portfolio/page.tsx    # EDIT — becomes the card view + realized summary; transaction UI removed
│   │   └── transactions/page.tsx # NEW — relocated ledger + record/import/delete controls
│   ├── components/
│   │   ├── PositionCard.tsx      # NEW — status/levels/news/sentiment/instruction card
│   │   ├── RealizedSummary.tsx   # NEW — win/loss counts, win rate, total realized P&L (+ empty state)
│   │   ├── AppShell.tsx          # EDIT — add Transactions nav link
│   │   ├── ImportTransactions.tsx / SentimentReport.tsx / EventsBadge.tsx / cockpit/PipelineStageBadge.tsx  # (reused)
│   └── lib/api.ts                # EDIT — extend holdings schema (optional instruction + directive_enabled)
└── tests/                        # EDIT — Vitest card render/degrade; Playwright page split + no-directive lint
```

**Structure Decision**: Existing feature-001 web-app layout (`backend/` + `frontend/`). The
change is overwhelmingly frontend reorganization plus one small pure backend module and an
additive, back-compatible response extension — no new endpoint, store, or entity.

## Complexity Tracking

> No Constitution Check violations — section intentionally empty.
