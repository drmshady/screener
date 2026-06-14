# Implementation Plan: Mid-Term Side-by-Side Variant Comparison

**Branch**: `006-midterm-sidebyside-compare` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-midterm-sidebyside-compare/spec.md`

> **Reconstruction note**: this plan.md was regenerated on 2026-06-14 from the
> surviving spec.md, research.md, data-model.md, and contracts/ after the
> original (untracked) plan.md was overwritten by the `/speckit-plan` setup
> script. Content is derived from those documents and the CLAUDE.md feature
> summary; the design decisions themselves are unchanged.

## Summary

Let the single user run the mid-term band as one **side-by-side matrix of four
variants** against a single shared universe snapshot, and export all four in
**one** advisor prompt. The four variants toggle the one A/B parameter each
strategy already exposes: momentum sector gate ON/OFF
(`sector_strength_top_fraction` 0.5 vs 1.0) and value momentum floor ON/OFF
(`min_momentum_12_1` -0.20 vs -1.0). This is **orchestration + presentation
only** — it changes no strategy rule, default, or backtest baseline (FR-008). The
new work: a shared-snapshot matrix runner (build the universe once, evaluate four
`rules()` over copies), two endpoints, a combined four-variant advisor-prompt
builder reusing the feature-004 section helpers, and a `/compare/midterm`
frontend surface reusing the 003 presentation idiom. Distinct from feature 003,
which is a *backtest* bake-off, not a live screen.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 16 + React 19 (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, pandas/numpy (backend); TanStack Query, Zod, Recharts (frontend); pytest, Vitest, Playwright
**Storage**: existing frozen `backend/data/` snapshot (SQLite + Parquet, per-ticker EDGAR cache); browser `localStorage` (portfolio/watchlist) — no new persisted schema
**Testing**: pytest (orchestration/prompt/API), Vitest, Playwright (no-directive lint)
**Target Platform**: local single-user web app (backend `127.0.0.1:8000`, frontend dev `:3000`)
**Project Type**: web application (backend + frontend) — Option 2
**Performance Goals**: the four-variant run reuses one universe snapshot and one regime, staying within the constitution's full-universe screen budget (p95 ≤ 10 s; ≤ 2 s cached)
**Constraints**: deterministic output (same snapshot ⇒ byte-identical results and prompt); no directive copy unless the personal-use flag is on; `data_as_of`/`disclaimer` on every surface
**Scale/Scope**: fixed 4-variant matrix over the two mid-term strategies; ~592-name live universe; reuses existing level/regime/gate machinery

## Constitution Check

*GATE: evaluated against constitution v1.1.0. Re-checked after Phase 1 design.*

- **I. Data Integrity (NON-NEGOTIABLE)** — PASS. Reuses the existing point-in-time
  snapshot and sources; adds no new data path.
- **II. Strategy Transparency** — PASS / reinforces it. Each variant surfaces the
  full strategy declaration (citations, parameters incl. the toggled value,
  modifications); the toggled-OFF gate is reported as intentionally disabled, not
  silently dropped (FR-006). No rule/default/parameter is altered (FR-008).
- **III. Reproducible Backtesting (NON-NEGOTIABLE)** — PASS. No backtest is
  rerun; each strategy's existing bias-check verdict (survivorship still FAILS on
  free Stooq) travels with both of its variants and is never hidden (FR-015,
  Decision 6). The live comparison is deterministic on the frozen snapshot
  (FR-007/FR-013).
- **IV. Test-First for Financial Logic** — PASS (no new financial logic; this is
  orchestration). New orchestration/prompt/API behaviour still lands test-first
  per the quickstart (matrix, prompt, API tests written to fail first).
- **V. User Safety & No-Advice Boundary** — PASS. New copy passes the directive
  lint (FR-010); directive framing stays gated behind
  `SCREENER_PERSONAL_USE_DIRECTIVE`, OFF by default (FR-014); `data_as_of` +
  `disclaimer` on every variant (FR-009).

**Gate result: PASS — no violations; Complexity Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/006-midterm-sidebyside-compare/
├── spec.md
├── plan.md              # This file (reconstructed)
├── research.md          # 6 decisions (fixed matrix, shared-snapshot runner, …)
├── data-model.md        # VariantSpec, VariantResult, MidtermComparisonResponse, prompt structure
├── quickstart.md        # TDD-first runbook
├── contracts/           # compare-api.md, advisor-prompt.schema.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── screening/
│   │   └── engine.py            # MODIFY — factor "build snapshot once" + "apply attrs → rules() → assemble"
│   │                            #          so single-strategy and matrix paths share them (Decision 2)
│   ├── screening/
│   │   └── midterm_matrix.py     # NEW — shared-snapshot matrix runner over the 4 VariantSpecs
│   ├── agent/
│   │   └── advisor_prompt.py     # MODIFY — add build_midterm_matrix_advisor_prompt() reusing
│   │                            #          _strategy_context/_run_config_block/_candidate_summary_block (Decision 4)
│   ├── api/
│   │   └── strategies.py         # MODIFY — POST /strategies/midterm-compare + …/advisor-prompt (Decision 5)
│   └── models/
│       └── strategy.py           # MODIFY — additive VariantResult / MidtermComparisonResponse / prompt-response models
└── tests/
    ├── screening/test_midterm_matrix.py        # NEW — 4 variants, shared snapshot, determinism, empty variant
    ├── agent/test_midterm_matrix_prompt.py     # NEW — one combined prompt, 4 delimited sections, per-strategy bias-check, byte-identical
    └── api/test_midterm_compare_api.py         # NEW — endpoint contract + directive-flag behaviour

frontend/
├── src/
│   ├── app/compare/midterm/page.tsx            # NEW — 4-variant side-by-side surface (reuses 003 idiom)
│   ├── components/                             # MODIFY/NEW — variant columns, toggle-state labels, combined copy button
│   └── lib/api.ts                              # MODIFY — Zod schemas for the compare + prompt responses
└── tests/e2e/no-directive-copy.spec.ts         # MODIFY — assert the new compare surface passes the lint
```

**Structure Decision**: Existing Option 2 (web app) layout. No new services. The
core seam is factoring `engine.py` so the universe snapshot is built once and the
"apply toggle attrs → call `rules()` → assemble candidates" step is shared by
both the single-strategy run and the new matrix runner (research Decision 2). The
advisor prompt extends the feature-004 builder rather than concatenating four
single-strategy prompts (Decision 4).

## Complexity Tracking

> Not required — Constitution Check passed with no violations.
