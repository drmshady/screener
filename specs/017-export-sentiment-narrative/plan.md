# Implementation Plan: Sentiment & Narrative in Exported Advisor Prompts (+ Watchlist Export)

**Branch**: `017-export-sentiment-narrative` | **Date**: 2026-07-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/017-export-sentiment-narrative/spec.md`

## Summary

Weave feature 014's **already-captured** sentiment & narrative report into the three
copy-ready advisor-prompt surfaces so a single paste carries both the screener's hard
numbers and the market's story for the same names:

1. **Screener-results** export (`POST /strategies/{slug}/advisor-prompt`) — embed a sentiment
   section inside each candidate block.
2. **Portfolio-report** export (`POST /portfolio/holdings/advisor-prompt`) — embed a sentiment
   section inside each holding block.
3. **New watchlist** export (`POST /portfolio/watchlist/advisor-prompt`) — a net-new prompt
   built in the **same format** as the screener export, over the owner-scoped watchlist.

**Technical approach**: The export path performs **no** fresh source collection, scoring, or
narrative generation. Instead the API layer resolves, per ticker, the most-recently **captured**
`SentimentReport` via a new **ticker-indexed lookup** on `CapturedReportStore`
(`latest_for_ticker`), and passes an optional `sentiment_by_ticker: dict[str, SentimentReport]`
mapping into the pure prompt builders. A single pure renderer
(`_sentiment_section(report)`) turns one captured report into a labeled, non-directive,
clearly-separated block, reused by the candidate, holding, and watchlist block builders. Because
the renderer consumes only the content-addressed `SentimentReport` fields (never `captured_at`
or any wall-clock), determinism (FR-007) and byte-identical fallback when absent (FR-008) hold.
Reusing captured reports (never regenerating) preserves the ~$5/month budget cap under any
export volume (FR-009). The watchlist export reuses `compute_candidate_result` per watched
ticker and the existing `_candidate_summary_block` / `_strategy_context` / honesty-block
machinery in a new `build_watchlist_advisor_prompt`.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 15 + React 19 (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2 (backend); TanStack Query, Zustand store (frontend). No new dependencies.
**Storage**: Existing `backend/data/cache/reports.sqlite` captured-report store (feature 014); existing single-owner portfolio/watchlist blob (`portfolio_store.py`). No new store.
**Testing**: pytest + hypothesis (backend); Vitest + Playwright (frontend, incl. the existing no-directive copy lint).
**Target Platform**: Local personal-use + Render (backend) / Vercel (frontend) hosted mode.
**Project Type**: Web application (backend + frontend).
**Performance Goals**: Export stays within existing advisor-prompt latency; the added per-ticker store lookup is a single indexed SQLite read (no network).
**Constraints**: Byte-identical determinism for fixed snapshot + fixed captured sentiment; zero new paid calls at export; zero directive language; `data_as_of` + `disclaimer` on every response; hosted-mode owner-only + forced directive-OFF.
**Scale/Scope**: Single owner; a screen/watchlist of ≤ ~50 names; sentiment captured for a handful of names at a time.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Notes |
|-----------|---------|-------|
| I. Data Integrity & Provenance (NON-NEGOTIABLE) | PASS | Embedded sentiment carries the captured report's dated sources; no new source, no hindsight, no data mutation. |
| II. Strategy Transparency & Peer-Reviewed Foundations | PASS | No strategy rule, parameter, default, or citation change (FR-017). Strategy declaration already present in each prompt. |
| III. Reproducible Backtesting & Bias Avoidance (NON-NEGOTIABLE) | PASS | Renderer uses only content-addressed `SentimentReport` fields — no wall-clock, no `captured_at` — so re-export is byte-identical (FR-007). No backtest baseline change (FR-017). |
| IV. Test-First for Financial Logic | PASS | No new indicator/strategy. New render + store-lookup + watchlist-builder logic ships with fixture + determinism + no-directive tests written first. |
| V. User Safety, Risk Disclosure & No-Advice Boundary | PASS | Embedded sentiment is non-directive external context (existing prompt copy-lint); task instruction states it MUST NOT overwrite computed gate/rank/level/size. Directive framing stays confined to the task instruction and is forced OFF hosted (FR-006, FR-016). |
| Data/Compliance (disclosure envelope) | PASS | Every enriched/new response keeps `data_as_of` + `disclaimer` (FR-015). |

No violations → **Complexity Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/017-export-sentiment-narrative/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (watchlist-export endpoint + enriched-export deltas)
├── checklists/          # (pre-existing)
└── spec.md              # Feature specification
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── agent/
│   │   └── advisor_prompt.py        # ADD _sentiment_section() renderer; thread
│   │                                #   sentiment_by_ticker through build_screen_advisor_prompt,
│   │                                #   build_portfolio_advisor_prompt, _candidate_summary_block,
│   │                                #   _holding_block; ADD build_watchlist_advisor_prompt()
│   ├── sentiment/
│   │   └── store.py                 # ADD ticker column + latest_for_ticker(ticker) lookup
│   └── api/
│       ├── strategies.py            # screen_advisor_prompt: resolve + inject captured sentiment
│       └── portfolio.py             # holdings/advisor-prompt: inject; ADD watchlist/advisor-prompt
└── tests/
    ├── agent/                       # renderer + determinism + no-directive + byte-identical-absent
    ├── sentiment/                   # store latest_for_ticker lookup + migration
    └── api/                         # enriched screen/portfolio export + new watchlist export

frontend/
├── src/
│   ├── app/watchlist/page.tsx       # ADD "Copy watchlist advisor prompt" action
│   ├── components/
│   │   └── CopyWatchlistAdvisorPrompt.tsx   # NEW (mirrors CopyScreenAdvisorPrompt)
│   └── lib/
│       ├── api.ts                   # ADD watchlist-export client call
│       └── advisorPrompt.ts         # (reuse copy plumbing)
└── tests/                           # Playwright: watchlist export + no-directive lint on all three
```

**Structure Decision**: Existing web-application layout. All backend changes are additive and
concentrated in three files (`advisor_prompt.py`, `sentiment/store.py`, and the two export API
modules); frontend adds one export component + one action button on the existing watchlist page.
No new module tree, no new store, no new dependency.

## Phase 0 — Research

See [research.md](./research.md). Resolves the one genuine unknown (how the export finds a
captured report by ticker without triggering fresh source collection) and records the
determinism, budget, fail-soft, and watchlist-format decisions.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md): the reused `SentimentReport` fields, the new
  `sentiment_by_ticker` mapping passed to builders, the store's added `ticker` index, and the
  watchlist-export request/response shapes.
- [contracts/](./contracts/): the new `POST /portfolio/watchlist/advisor-prompt` contract plus
  the additive response deltas for the two enriched exports.
- [quickstart.md](./quickstart.md): how to capture sentiment, then export each of the three
  prompts and verify embedding, determinism, absent-fallback, and no-directive.

## Complexity Tracking

No constitution violations; section intentionally empty.
