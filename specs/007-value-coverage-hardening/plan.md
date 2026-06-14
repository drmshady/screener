# Implementation Plan: Value Strategy — Data Coverage & Correctness Hardening

**Branch**: `007-value-coverage-hardening` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-value-coverage-hardening/spec.md`

## Summary

Harden the live `midterm_value_composite` screen along two independent axes that
live operation exposed: (1) **data coverage** — re-fetch the 530 failed-fetch
EDGAR stub files for real US filers, filter genuinely-non-US-GAAP instruments
(preferred/ADR/CEF/ETF) out of the value universe up front, and stop branding
stale-local-feed names as "halted"; and (2) **strategy correctness & disclosure**
— add a hard profitability gate (Piotroski CFO>0 and ROA>0) so loss-makers can't
rank cheap, add a minimum-risk ATR stop floor so degenerate R-multiples can't
print, ship the falling-knife guard ON at −0.20, and surface the cheapness-cut
gate, sub-9 F-Score confidence, within-sector grouping/cap, regime-blind state,
and data-quality flags. Closes with a slim-cache rebuild + value backtest
regeneration and a re-sync of the `claude-project/` advisor pack.

Approach: extend existing modules (no new services). A resumable refresh script
over the EDGAR cache; a small instrument-classifier in the data layer; targeted
edits to `midterm_value_composite.rules`/`derive_levels`/`evaluate`; an engine
staleness-gate refinement; and additive API/Zod/UI fields. Every strategy-logic
change is test-first per Principle IV.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 16 + React 19 (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, pandas/numpy, httpx (SEC fetch); TanStack Query, Zod, Recharts (frontend); pytest + hypothesis, Vitest + Playwright
**Storage**: SQLite + Parquet (prices); per-ticker JSON EDGAR cache (`backend/data/edgar_cache/`); slim cache built by the backtest runner; browser `localStorage` (portfolio/watchlist)
**Testing**: pytest (golden-fixture + integration), Vitest, Playwright (no-directive lint)
**Target Platform**: local single-user web app (backend `127.0.0.1:8000`, frontend dev `:3000`)
**Project Type**: web application (backend + frontend) — Option 2
**Performance Goals**: full-universe EOD screen p95 ≤ 10 s (≤ 2 s cached) per constitution; coverage refresh is an offline batch, not on the screen hot path
**Constraints**: SEC fair-access ≤ 10 req/s with a descriptive User-Agent; point-in-time discipline (no look-ahead); deterministic screen output; no API keys written to disk
**Scale/Scope**: ~4,242 cached EDGAR tickers (530 stubs, 253 partial); ~592 names in a live screened universe; 4 registered strategies (only the value strategy + shared disclosure surfaces are touched)

## Constitution Check

*GATE: evaluated against constitution v1.1.0. Re-checked after Phase 1 design.*

- **I. Data Integrity & Provenance (NON-NEGOTIABLE)** — PASS / strengthens it.
  Re-fetching real-filer stubs and rejecting stale share counts (already done via
  the `dei` + 450-day guard) improves point-in-time fidelity. Non-equity
  filtering is provenance-honest (those instruments have no US-GAAP facts).
  Survivorship bias stays surfaced — the regenerated backtest's failing verdict
  is NOT hidden (FR-008/SC-008). SEC remains the authoritative source; refresh
  respects fair-access limits and writes nothing secret.
- **II. Strategy Transparency** — PASS / strengthens it. The new profitability
  gate is documented in the strategy declaration with its Piotroski (2000)
  citation; the cheapness cut becomes an explicitly-shown gate. All thresholds
  (−0.20 floor, ~1×ATR stop floor, CFO>0/ROA>0) are in code with documented
  defaults/ranges.
- **III. Reproducible Backtesting (NON-NEGOTIABLE)** — PASS. Changes keep screen
  output deterministic; the value backtest is regenerated point-in-time across
  ≥15 years incl. 2008–2009; bias-check stays visible. Refresh is idempotent and
  resumable (deterministic given a cache + SEC snapshot).
- **IV. Test-First for Financial Logic** — PASS (enforced by FR-014). The
  profitability gate, min-risk stop floor, and −0.20 default each get a
  failing-first test before implementation; existing value/Piotroski golden
  fixtures keep passing within tolerance.
- **V. User Safety & No-Advice Boundary** — PASS. New copy passes the directive
  lint (FR-013); `data_as_of`/`disclaimer` preserved; the regime-blind banner and
  data-quality flags *increase* disclosure. Directive framing stays gated behind
  `SCREENER_PERSONAL_USE_DIRECTIVE` (unchanged).

**Gate result: PASS — no violations, Complexity Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/007-value-coverage-hardening/
├── spec.md              # Feature specification (done)
├── plan.md              # This file
├── research.md          # Phase 0 — decisions + rationale
├── data-model.md        # Phase 1 — entities
├── quickstart.md        # Phase 1 — runbook (refresh → re-slim → backtest → verify)
├── contracts/           # Phase 1 — refresh CLI, gate/level, API-field contracts
└── tasks.md             # Phase 2 — created by /speckit-tasks (not here)
```

### Source Code (repository root)

```text
backend/
├── scripts/
│   ├── refresh_edgar_coverage.py     # NEW — classify + re-fetch fixable stubs (FR-001/002)
│   ├── build_edgar_cache.py          # MODIFY — write schema-v3 (dei + value tags), never stub-over-good
│   └── ingest_daily.py               # MODIFY — cover full screened universe, retry failures (FR-004)
├── src/
│   ├── data/
│   │   ├── instruments.py            # NEW — classify common-equity vs preferred/ADR/CEF/ETF (FR-003)
│   │   └── fundamentals.py           # (Piotroski CFO/ROA already extractable; reuse)
│   ├── indicators/
│   │   └── piotroski.py              # reuse profitability signals for the gate
│   ├── strategies/
│   │   └── midterm_value_composite.py # MODIFY — profitability gate, min-risk floor, -0.20 default,
│   │                                  #          cheapness-cut gate line, F-score confidence (FR-005/006/007/008/009)
│   ├── screening/
│   │   └── engine.py                 # MODIFY — non-equity filter, staleness-gate split, sector-group output,
│   │                                  #          regime-blind flag, data-quality flags (FR-003/004/010/011/012)
│   ├── models/
│   │   └── strategy.py               # MODIFY — additive fields (confidence flag, regime_available,
│   │                                  #          sector_group, data_quality_flags, profitability gate)
│   └── backtests/
│       └── runner.py                 # MODIFY — slim rebuild keeps v3 tags; regenerate value artifact (FR-015)
└── tests/
    ├── strategies/test_midterm_value_composite.py  # MODIFY — gate/floor/level tests (test-first)
    ├── data/test_instruments.py                    # NEW — classifier golden cases
    ├── data/test_refresh_edgar_coverage.py         # NEW — idempotent/no-clobber/CIK-skip
    ├── screening/test_value_staleness_split.py     # NEW — local-lag vs delist
    └── screening/test_value_coverage_guard.py      # NEW — min value-metric coverage on fixture (FR-015)

frontend/
├── src/
│   ├── app/screen/[strategy]/page.tsx              # MODIFY — regime-blind banner, sector grouping/cap, value floor default
│   ├── components/StrategyGatesPanel.tsx (+ candidate row) # MODIFY — cheapness-cut line, F-score confidence, data-quality flags
│   └── lib/api.ts                                  # MODIFY — Zod schema additive fields
└── tests/e2e/no-directive-copy.spec.ts             # MODIFY — assert new copy passes the lint

claude-project/
├── 00-custom-instructions.md         # MODIFY (closing task) — momentum floor now default ON, profitability gate
├── 05-value-strategy-rules.md        # MODIFY — profitability gate + min-risk floor + -0.20 floor
└── 06-value-modifications-and-citations.md # MODIFY — Piotroski profitability gate citation
```

**Structure Decision**: Existing Option 2 (web app) layout. No new top-level
projects or services — one new offline script, one small data-layer classifier,
and otherwise targeted edits to the value strategy, engine, models, runner, and
the frontend disclosure surfaces it already owns.

## Complexity Tracking

> Not required — Constitution Check passed with no violations.
