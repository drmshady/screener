# Implementation Plan: Advisor Prompt Export

**Branch**: `004-advisor-prompt-export` | **Date**: 2026-06-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/004-advisor-prompt-export/spec.md`

## Summary

Add a **"Copy advisor prompt"** capability that, for a candidate of the mid-term
52-week-high momentum strategy, assembles a single self-contained text prompt
combining (a) the candidate's already-computed result — gate-by-gate breakdown,
entry/stop/tighter-stop/take-profit, rank, regime — and (b) the strategy's live
declaration (name, George & Hwang 2004 citation, timeframe, holding period,
parameters, the eight modifications each with its own citation) and (c) a
mandatory honesty block driven by the backtest's actual `bias_check` (today:
survivorship FAILS). The user copies it and pastes it into the external Claude
Project advisor.

**Technical approach**: a pure, deterministic **backend builder** is the single
source of truth, so the prompt cannot drift from the implemented rules. It reads
the registry's `Strategy` object and the backtest artifact directly, and reuses
the existing single-ticker gate evaluation in `analyze.py`. It is exposed as a
new read-only endpoint; the frontend is a thin clipboard button with a preview.
Directive (take/pass/size) framing is **gated behind a personal-use flag**
following the existing `SCREENER_*` operator-override pattern; with the flag off
the prompt uses neutral framing and emits zero directive language, preserving
the constitution's no-advice guarantee.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Node 20 (frontend) — unchanged from 001/002
**Primary Dependencies**: FastAPI, Pydantic v2, pandas (backend); Next.js 15 / React 19 / TanStack Query / Zod (frontend); pytest + Vitest + Playwright for tests — all already installed
**Storage**: None new. Reads the existing frozen `backend/data/` snapshot (Parquet prices, SQLite catalog, EDGAR cache) and the committed backtest artifact `backend/data/backtests/midterm_52w_high_momentum.json`
**Testing**: `python -m pytest backend/tests`, `npm run test` (Vitest) + `npx playwright test`; new unit tests for the builder, a contract test for the endpoint, and one frontend e2e
**Target Platform**: Local single-machine (Windows 11), personal-use scope — unchanged
**Project Type**: Web application (FastAPI backend + Next.js frontend) — existing
**Performance Goals**: Prompt build is string assembly over one already-computed candidate; reuses analyze's universe evaluation (already within the p95 ≤ 10s screen budget). No new perf surface.
**Constraints**: Deterministic (same snapshot → byte-identical prompt); no new network/data dependency; the prompt body MUST NOT embed wall-clock time (only the snapshot's `data_as_of`); directive language only under the personal-use flag
**Scale/Scope**: 1 strategy supported (mid-term 52-week-high), 1 new backend module + 1 endpoint, ~1 builder, 3 frontend touch-points (candidate detail, analyze page, screener row — last is secondary)

**No NEEDS CLARIFICATION remain** — the spec's Assumptions resolved scope
(self-contained prompt, single source of truth, personal-use directive gating,
mid-term-only), and all required inputs already exist on the current snapshot.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Data Integrity & Provenance (NON-NEGOTIABLE)**: The prompt carries the
  snapshot's `data_as_of` and every figure originates from the app's computed
  candidate result (FR-002, FR-003, FR-010) — nothing is recomputed by the
  consumer. Provenance is preserved end-to-end. ✅ PASS
- **II. Strategy Transparency & Peer-Reviewed Foundations**: The prompt is
  *built from* the live `Strategy` declaration — name, George & Hwang (2004)
  citation, parameters, and all eight modifications with their own citations
  (FR-006, FR-012). This actively propagates transparency rather than risking
  it. A drift test makes it impossible to add a modification the prompt omits. ✅ PASS
- **III. Reproducible Backtesting & Bias Avoidance (NON-NEGOTIABLE)**: The
  prompt is deterministic on a frozen snapshot (FR-011, SC-004) and its honesty
  block is generated from the artifact's real `bias_check` — it *surfaces* the
  failing survivorship check in plain language (FR-007, SC-003) rather than
  hiding it. No look-ahead is introduced; it only reads existing results. ✅ PASS
- **IV. Test-First for Financial Logic**: Builder + endpoint ship with tests
  written first — gate completeness, mandatory-caveat presence, determinism,
  and declaration-drift (FR-004, FR-007, FR-011, FR-012). No indicator math is
  added. ✅ PASS
- **V. User Safety, Risk Disclosure & No-Advice Boundary**: ✅ **PASS (amendment
  landed).** Every prompt carries the disclaimer + as-of + citation (FR-009).
  With the personal-use flag **off** (the safe default), the prompt uses neutral
  framing and emits zero directive language, and the feature's own UI introduces
  no directive copy (FR-013, FR-014, SC-006). The flag-**on** directive mode is
  now expressly sanctioned by the **Personal-use directive exception added in
  constitution v1.1.0** (2026-06-13): single-user, non-redistributed, flag-gated
  (OFF by default), auto-reverting to neutral for any shared/hosted instance,
  with disclosure obligations preserved. The earlier CONDITIONAL status is
  resolved; the flag may legitimately be enabled for personal use.

**One conditional gate (Principle V).** See Complexity Tracking. No other
violations: the feature adds no new project, no new data source, no new
persistence.

## Project Structure

### Documentation (this feature)

```text
specs/004-advisor-prompt-export/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 — build-vs-client, flag mechanism, caveat sourcing
├── data-model.md        # Phase 1 — AdvisorPrompt + section entities
├── quickstart.md        # Phase 1 — how to generate and verify a prompt
├── contracts/
│   ├── advisor-prompt.schema.md     # required prompt sections + ordering
│   └── advisor-prompt-endpoint.md   # the read-only endpoint contract
├── checklists/
│   └── requirements.md  # spec quality checklist (done)
└── tasks.md             # Phase 2 — /speckit-tasks (NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── agent/                        # NEW — prompt assembly (no LLM call; build only)
│   │   ├── __init__.py
│   │   └── advisor_prompt.py         # build_advisor_prompt(...) pure builder
│   ├── api/
│   │   └── analyze.py                # EXTEND — add GET /analyze/{ticker}/advisor-prompt
│   ├── strategies/
│   │   └── midterm_52w_high_momentum.py  # (read) declaration + bias artifact loader
│   ├── lib/
│   │   ├── disclaimer.py             # (read) DISCLAIMER_TEXT
│   │   └── flags.py                  # NEW (or extend) — personal_use_directive() flag
│   └── models/strategy.py            # (read) Candidate / AnalyzeResponse / Strategy
└── tests/
    └── agent/                        # NEW
        ├── test_advisor_prompt_builder.py   # FR-004/006/007/008/011/012 + SC-002/003/004
        ├── test_advisor_prompt_flag.py      # FR-013/014 + SC-006 directive gating
        └── test_advisor_prompt_endpoint.py  # endpoint contract + disclaimer/as-of

frontend/
├── src/
│   ├── lib/
│   │   └── advisorPrompt.ts          # NEW — fetch + clipboard helper (no rules logic)
│   ├── components/
│   │   └── CopyAdvisorPrompt.tsx     # NEW — button + collapsible preview
│   └── app/
│       ├── candidate/[ticker]/page.tsx  # EXTEND — mount button on each match card
│       └── analyze/page.tsx             # EXTEND — mount button on the analyzed ticker
└── tests/e2e/
    ├── advisor-prompt-copy.spec.ts   # NEW — button copies a complete, non-empty prompt
    └── no-directive-copy.spec.ts     # EXTEND — scoped exemption for the personal-use preview
```

**Structure Decision**: Web-application layout (existing). The backend builder is
the single source of truth (Constitution II/III); the frontend holds no strategy
knowledge. The feature is additive — one new backend package (`agent/`), one new
endpoint on the existing `analyze` router, one new frontend component, and tests.
No new top-level project, data source, or persistence.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Principle V relaxation: directive framing under personal-use flag | The user explicitly wants directive, personalized guidance from the external advisor for their own single-user, non-redistributed use; "expert advisor" is the feature's purpose | A strictly neutral prompt would not meet the user's stated need. The relaxation is bounded: it is **off by default**, **flag-gated**, and **reverts to neutral automatically** when off or shared/hosted. **Resolved**: constitution **v1.1.0** (2026-06-13) added the Personal-use directive exception to Principle V scoping exactly this; the relaxation is no longer an unjustified violation. A blanket directive mode (no flag, no amendment) was rejected because it would silently violate a NON-NEGOTIABLE principle and break the no-directive-copy guarantee for any future shared/hosted use. |
