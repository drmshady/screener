# Implementation Plan: AI Sentiment & Narrative Intelligence (+ three bug fixes)

**Branch**: `014-ai-sentiment-narrative` | **Date**: 2026-07-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/014-ai-sentiment-narrative/spec.md`

## Summary

Add an **on-request, informational-only** sentiment & narrative report over stocks the
owner selects (from screener results, portfolio holdings, or a typed ticker), sourced
from free/low-budget feeds, and hardened for the constitution's determinism + no-advice
rules by **capturing every generated artifact into a durable store and serving it back
byte-identically** (the coarse label/score comes from a finance-domain classifier —
**FinBERT (ONNX), captured** — with a transparent Loughran-McDonald lexicon fallback; the
optional plain-language narrative is generated once by a cheap, provider-swappable LLM —
free-tier **Gemini** default, Claude Haiku alternative — and never regenerated per view).
A hard **~$5/month spend cap** degrades the report to a deterministic, source-only template
when reached — never silently exceeding budget. Bundled with it are **three standalone bug
fixes** that ship first and independently:

- **Bug A (US1)** — parity + confirmation for "Add to watchlist" across every candidate
  surface (results table *and* the candidate detail page).
- **Bug B (US2)** — the SPY 200-day-SMA market-regime input must show a concrete
  close/SMA/verdict + source + as-of (never a bare "Unknown"), including hosted + live-feed-down.
- **Bug C** — the Market-Events (FOMC/CPI/NFP/PCE/PPI) panel shows "Stale events data" and
  empties out because the curated econ calendar is a finite static YAML whose `source_as_of`
  never advances on the daily reseed.

No strategy rule, default, citation, indicator, or backtest baseline changes (SC-008): the
overlay is presentation-only, mirroring the existing events/news badge layer.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 15 + React 19 (frontend) — unchanged.
**Primary Dependencies**: FastAPI, Pydantic v2, pandas/numpy (backend); Next.js App Router,
Zustand, TanStack Query, Zod (frontend). **New (scoring):** FinBERT (ProsusAI, via
`transformers`+`torch`, or `onnxruntime` quantized for the hosted-light path) run **locally/offline,
free, captured**, with a vendored Loughran-McDonald lexicon as the zero-dep fallback. **New
(optional prose):** provider-swappable LLM for the plain-language narrative only —
default **Gemini** Flash-tier (`google-genai`, owner-supplied key, free tier ⇒ $0), alternative
**Claude Haiku 4.5** (`anthropic`); absent ⇒ deterministic `template` narrative. News: `yfinance`
(`Ticker.news`, no key) baseline with **Finnhub + Alpha Vantage** backups (owner-supplied keys) +
the existing EDGAR/8-K pipeline; analyst opinion via `yfinance`/Finnhub (free). No new *required*
provider key (baseline runs key-free); all keys are runtime-env-only backups/upgrades.
**Storage**: existing single-owner blob + SQLite `events.db` + Parquet snapshot. **New**: a
captured-report store + monthly spend ledger under **`backend/data/cache/`** (`reports.sqlite`,
`spend.json`) — a **runtime-writable, non-baked** dir (already `.dockerignore`d + gitignored) so it
never touches the read-only atomic-swapped snapshot; keyed by report fingerprint. The baked FinBERT
ONNX model lives read-only under `backend/data/finbert_onnx/` (produced by a publish-chain step, not
committed). Browser store (Zustand) unchanged except Bug A's already-supported paths.
**Testing**: pytest + hypothesis (backend), Vitest + Playwright (frontend). Determinism,
no-directive-copy, and disclaimer-everywhere lints already exist and are extended to the new surfaces.
**Target Platform**: Local single-user + hosted (Render/HF backend, Vercel BFF frontend) — unchanged.
**Project Type**: Web application (backend + frontend), single owner.
**Performance Goals**: Regime panel ≤ 3 s (unchanged SLA); sentiment report is owner-triggered
and async — each selected ticker's report returns within a few seconds on a cache hit, bounded
by the free-feed + one cheap LLM call on a cache miss; a source/model outage fails soft per-name.
**Constraints**: Determinism (same snapshot + same ticker → byte-identical label & narrative,
SC-004); zero directive language (SC-003); `data_as_of` + `disclaimer` on every response;
hosted directive-OFF forced; **hard ~$5/month spend cap** enforced before every paid call (SC-007);
0 calls for non-selected stocks / 0 auto-generation (SC-009).
**Scale/Scope**: One owner. Sentiment run on a handful of hand-picked tickers per request.

## Constitution Check

*GATE: must pass before Phase 0 research; re-checked after Phase 1 design.*

| Principle | Assessment |
|-----------|------------|
| **I. Data Integrity & Provenance (NON-NEGOTIABLE)** | PASS. Every sentiment/narrative claim is attributable to a listed, dated **Source Item** (FR-S2); unsourced assertions are forbidden. Sources are drawn only from an explicitly bounded, owner-disclosed set (free news headlines, existing EDGAR/8-K, free analyst opinion; social/retail omitted until a free, licensing-permissible source exists — FR-S10/S11). Each Source Item carries a source tag + as-of date; stale sources are labeled stale, never shown current. No third-party content is redistributed beyond what the single owner is licensed to view. |
| **II. Strategy Transparency** | PASS (not touched). No strategy rule/parameter/threshold changes. Principle II's "black-box models / undisclosed ML weights are PROHIBITED" clause governs **shipped screens/strategies** — FinBERT is **not** a strategy: it is a presentation-layer sentiment *tagger* (like the existing news/events badges) that never feeds a gate, rank, level, sizing, or regime (FR-S3, SC-008), so the clause does not attach. Its output is a **disclosed, inspectable score** (`P(positive) − P(negative)` from the openly-published ProsusAI FinBERT, pinned by revision) and is **captured** for reproducibility; a fully-transparent Loughran-McDonald lexicon is the documented fallback. The optional LLM narrative is *descriptive prose only*, never a screening/ranking input. |
| **III. Reproducible Backtesting & Bias Avoidance (NON-NEGOTIABLE)** | PASS. No backtest, snapshot, or baseline change (SC-008). Determinism is preserved end-to-end: the deterministic label is pure; the non-deterministic LLM narrative is **captured once into a durable store and served verbatim thereafter** (FR-S5) so the served result is stable and re-inspectable — mirroring the constitution's "seeded or recorded" requirement for non-determinism. |
| **IV. Test-First for Financial Logic** | PASS. Bug B (regime source selection / SMA availability), the sentiment **scorer** (FinBERT against golden examples + the lexicon fallback), and the **narrative-risk** signal rules get fixture-anchored unit tests before implementation. The narrative builder is a pure, deterministic assembler given its captured inputs (tested like the advisor-prompt builder). No indicator numeric output changes. |
| **V. User Safety, Risk Disclosure & No-Advice Boundary** | PASS. The report is informational-only and carries **zero directive language** (FR-S4, SC-003) — enforced by the existing copy lint extended to the new surfaces. `data_as_of` + `disclaimer` ride every response (FR-S8). Hosted mode keeps `personal_use_directive()` forced OFF and owner-secret gated. The report never changes any gate result, rank, level, sizing, or regime (FR-S3). |

**Data-source note (Principle I / hosted clause):** the narrative LLM is a *transform over already-licensed, owner-viewable source text*, not a new market-data provider; it introduces no price/fundamental/corporate-action datapoint into any screen. Social/retail sentiment is **omitted by default** precisely because a free, licensing-permissible, deterministic-capturable source is not yet identified — added later only under the same bounded-source rule.

**Result: PASS — no Complexity Tracking entries required.**

## Project Structure

### Documentation (this feature)

```text
specs/014-ai-sentiment-narrative/
├── plan.md              # This file
├── research.md          # Phase 0 — provider/model/determinism decisions
├── data-model.md        # Phase 1 — entities
├── quickstart.md        # Phase 1 — local + hosted runbook, cap config, verification
├── contracts/
│   ├── sentiment.md     # POST /sentiment/report contract
│   └── bugfixes.md      # Regime (Bug B) + market-events (Bug C) response deltas
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/src/
├── api/
│   ├── regime.py            # Bug B: harden source selection + explicit unavailable reason (no bare Unknown)
│   ├── events.py            # Bug C: market-events staleness fix surfaces
│   └── sentiment.py         # NEW: POST /sentiment/report (owner-selected tickers only)
├── regime/
│   └── calculator.py        # Bug B: prefer the SPY source with ≥ sma_length history; emit reason note
├── screening/
│   └── regime.py            # Bug B: _load_spy no longer lets a short/partial yfinance frame win over the baked series
├── data/
│   └── econ_calendar.py     # Bug C: reseed stamps a real refresh time + rolling curated window (real dates only)
├── sentiment/               # NEW package
│   ├── sources.py           # bounded, labeled collectors: yfinance news + Finnhub/AlphaVantage backups, EDGAR/8-K reuse, analyst opinion
│   ├── scorer.py            # FinBERT (ONNX) score/label, captured; Loughran-McDonald lexicon fallback (golden-fixture tested)
│   ├── composite.py         # 24h/7d/30d/90d recency-weighted composite (presentation-only)
│   ├── narrative_risk.py    # rules-based narrative_risk 0-100 (feasible signals) + NEUTRAL non-directive labels
│   ├── narrative.py         # pure template assembler + optional provider-swappable LLM (Gemini/Claude); capture-once
│   ├── store.py             # captured-report store (fingerprint-keyed) + monthly spend ledger  → backend/data/cache/
│   └── budget.py            # hard ~$5/month cap enforcement + graceful degrade

├── ...                      # (baked, read-only) backend/data/finbert_onnx/  ← ONNX INT8 model + tokenizer
├── models/
│   └── sentiment.py         # NEW Pydantic models (report, source item, request/selection)
└── lib/
    └── flags.py             # NEW flags: sentiment enable, model id, monthly cap, source toggles

frontend/src/
├── components/
│   ├── CandidateRow.tsx        # Bug A: add-to-watchlist confirmation feedback
│   ├── RegimePanel.tsx         # Bug B: render numeric SMA/verdict/source/as-of or explicit reason
│   ├── MarketEventsPanel.tsx   # Bug C: honest freshness (only truly-stale shows the badge)
│   ├── AddToWatchlist.tsx      # NEW: shared control used by table + detail page (parity, FR-A1/A2/A4)
│   └── SentimentReport.tsx     # NEW: selection + on-request report render (label, narrative, sources)
├── app/
│   ├── candidate/[ticker]/page.tsx  # Bug A: add-to-watchlist control on detail page
│   ├── portfolio/page.tsx           # US4: select holdings → run report
│   └── sentiment/page.tsx           # NEW: manual-ticker + cross-surface selection entry point
└── lib/
    └── api.ts                  # NEW client + Zod schemas for /sentiment/report

scripts/
├── ingest_daily.py          # Bug C: reseed econ calendar with a real refresh timestamp (already calls seed_econ_calendar)
├── export_finbert_onnx.py   # NEW: one-time FinBERT→ONNX(INT8) export into backend/data/finbert_onnx/ (uses the export extra)
└── publish_chain.ps1        # add the export step before docker build (mirrors seed_universe); Dockerfile gains a scoped COPY

# backend/Dockerfile: + COPY backend/data/finbert_onnx /app/backend/data/finbert_onnx  (baked read-only, offline)
# .github/workflows/daily-refresh.yml: add HF Space runtime secrets note; keys stay env-only
```

**Structure Decision**: Existing two-tier web app. Bug fixes are localized edits to the
already-identified files above. The sentiment feature is a self-contained `backend/src/sentiment/`
package + one router + one frontend surface, reusing the events pipeline, single-owner envelope,
owner-secret gate, and disclaimer/no-directive lints. No new top-level project.

## Phase 0 — Research (see research.md)

Resolved unknowns: (1) free/low-budget **data sources** — yfinance-news baseline + Finnhub/Alpha
Vantage backups + EDGAR/8-K + free analyst opinion; transcripts + social omitted-by-default; (2)
**scorer** = FinBERT (ONNX INT8, captured) with a Loughran-McDonald lexicon fallback — the LLM never
does the label; (3) **narrative prose** = optional, provider-swappable (free-tier Gemini default,
Claude Haiku alternative, else `template`), cap-gated + captured; (4) **determinism mechanism** =
capture-once + fingerprint-keyed durable store (no re-invocation for an existing fingerprint); (5)
**budget enforcement** = pre-call spend projection (at the active provider's rates; $0 on Gemini free
tier) against a persisted monthly ledger, degrade to source-only deterministic template on cap; (6)
**hosted-mode / deploy** posture — baked ONNX model, runtime-writable cache, HF Space runtime secrets
(see contracts/deploy-finbert.md); (7) **narrative-intelligence** module — feasible signals only +
neutral non-directive labels; (8) Bug B root cause (short/partial yfinance frame beats the baked SPY
series → Unknown), Bug C root cause (static YAML `source_as_of` never advances on reseed → derived-
stale + finite events expire).

## Phase 1 — Design & Contracts (see data-model.md, contracts/, quickstart.md)

Entities: Sentiment/Narrative Report, Report Request/Selection, Source Item, plus the reused
Watchlist Entry (Bug A) and Market Regime (Bug B). Contracts: `POST /sentiment/report`
(owner-selected tickers only, per-name fail-soft, captured-and-served) and the Bug B / Bug C
response deltas. Agent context updated (CLAUDE.md SPECKIT block → this plan).

## Complexity Tracking

No constitution violations — table intentionally empty.
