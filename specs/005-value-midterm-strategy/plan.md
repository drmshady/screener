# Implementation Plan: Value-Based Mid-Term Strategy

**Branch**: `005-value-midterm-strategy` | **Date**: 2026-06-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/005-value-midterm-strategy/spec.md`

## Summary

Add a second fully-gated **mid-term strategy** whose selection thesis is
*cheapness* rather than *trend*: `midterm_value_composite`. It ranks the liquid
US-equity universe by a **multi-metric value composite** (book/market, earnings
yield, operating-cash-flow yield, sales yield), gates out likely value traps
with a **Piotroski (2000) F-Score** financial-health screen, and treats sectors
whose valuation measures are structurally distorted (financials, REITs) by
ranking the composite **within sector**. It plugs into every existing
strategy-generic surface — the registry, the screen/candidate/analyze pages, the
003 comparison view, and the 004 advisor-prompt export — and ships with a
walk-forward backtest spanning 2008–2024 on point-in-time EDGAR fundamentals.

**Technical approach**: follow the exact pattern the momentum strategy
(`midterm_52w_high_momentum`) already establishes, so the new strategy reuses
the universe snapshot, reference-threshold caching, gate-accounting, tiered/hard
gate mode, level derivation, and backtest runner with minimal new surface.
The genuinely new work is **data + indicators**:

1. **Fundamentals**: extend `FundamentalsLoader.quality_metrics_as_of` (and the
   runner's `NEEDED_TAGS` slim cache) to emit, point-in-time, the value-composite
   inputs and the nine Piotroski signals from EDGAR concepts already filed
   (StockholdersEquity, NetIncomeLoss, Revenues, operating cash flow, Assets,
   current assets/liabilities, long-term debt, shares outstanding, gross profit).
2. **Indicators (test-first, Principle IV)**: two new pure modules —
   `indicators/valuation.py` (the four yields + composite) and
   `indicators/piotroski.py` (F-Score) — each with golden-fixture tests written
   **before** the strategy consumes them.
3. **Strategy**: `strategies/midterm_value_composite.py` declaring NAME,
   CITATION, TIMEFRAME, PARAMETERS, REGIME_FAVORABILITY, MODIFICATIONS (each
   cited), and a pure `rules()`; registered in the registry.
4. **Backtest**: add a value branch to `backtests/runner.py` and produce
   `backend/data/backtests/midterm_value_composite.json`.

Everything is deterministic on the frozen snapshot. The strategy ships
**disabled by default** (its bias-check survivorship still FAILS on the free
Stooq archive, exactly like momentum) and is honestly surfaced; an explicit
operator override mirrors the momentum precedent if the user wants it live.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Node 20 (frontend) — unchanged from 001–004
**Primary Dependencies**: FastAPI, Pydantic v2, pandas/numpy (backend); Next.js 15 / React 19 / TanStack Query / Zod (frontend); pytest + hypothesis + Vitest + Playwright — all already installed
**Storage**: No new store. Reads the existing frozen `backend/data/` snapshot (Stooq Parquet deep history, EDGAR slim cache, yfinance warm profiles) and writes one new committed backtest artifact `backend/data/backtests/midterm_value_composite.json` (+ `backend/backtests/midterm_value_composite/`)
**Testing**: `python -m pytest backend/tests` (new: indicator golden fixtures for valuation + F-Score, strategy rules unit tests, registry/load test, runner branch test); `npm run test` (Vitest) + `npx playwright test` (no-directive lint + comparison/analyze surfaces)
**Target Platform**: Local single-machine (Windows 11), personal-use scope — unchanged
**Project Type**: Web application (FastAPI backend + Next.js frontend) — existing
**Performance Goals**: Full-universe screen stays within the constitution's p95 ≤ 10 s EOD budget; the value composite + F-Score are vectorized cross-sectional computations over the already-built snapshot (no new per-name network calls at screen time — fundamentals are read from the EDGAR slim cache / warm profiles)
**Constraints**: Deterministic (same snapshot → identical candidates, ranking, levels); point-in-time fundamentals with no look-ahead (reuse `_latest_as_of`); no directive UI copy; no new data source or paid tier
**Scale/Scope**: 1 new strategy, 2 new indicator modules (+ their golden tests), 1 fundamentals-loader extension, 1 runner branch, optional value-diagnostic fields on `Candidate`/`AnalyzeResponse` and the advisor-prompt builder; frontend is largely data-driven (new strategy auto-appears)

**No NEEDS CLARIFICATION remain.** The spec's Q1 resolved the value definition
(composite value + Piotroski F-Score); all required inputs are derivable from
EDGAR concepts the slim cache already fetches or can fetch with a documented
`NEEDED_TAGS` extension. The one structural limitation (SEC XBRL fundamentals are
sparse before ~2011, so the 2008–2010 crisis years contribute few/no trades for
any fundamentals-dependent strategy) is **inherited and already surfaced** by the
runner's `coverage_notes`; it is documented honestly in research.md rather than
hidden.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Data Integrity & Provenance (NON-NEGOTIABLE)**: All new fundamentals are
  read point-in-time via `_latest_as_of` (filings filed on/before the as-of date
  — no restated-figure look-ahead), tagged `sec_edgar_companyfacts`, and carry
  the snapshot `data_as_of`. The strategy adds **no** new data source. The free
  Stooq archive's lack of delisted names is the same known survivorship gap the
  momentum strategy carries — it is **detected and reported honestly**, never
  papered over. ✅ PASS (with the documented, surfaced survivorship caveat).
- **II. Strategy Transparency & Peer-Reviewed Foundations**: Core thesis cites
  Fama & French (1992) and Lakonishok, Shleifer & Vishny (1994); the health gate
  cites Piotroski (2000); each modification carries its own citation (FR-002).
  Rules are deterministic, all parameters have documented defaults/ranges. No
  black box. ✅ PASS.
- **III. Reproducible Backtesting & Bias Avoidance (NON-NEGOTIABLE)**: Backtest
  spans 2008-01-01→2024-12-31 (≥15y incl. 2008–2009), walk-forward per-year, on
  point-in-time data, deterministic re-run. The honest `bias_check` (survivorship
  FAILS on Stooq; XBRL pre-2011 sparsity noted in `coverage_notes`) is surfaced,
  and the strategy is **not** enabled by default until the check passes — exactly
  the registry rule already enforced (`_window_meets_floor` + `enabled_by_default`
  gating). ✅ PASS.
- **IV. Test-First for Financial Logic**: The valuation multiples and the nine
  F-Score components are *indicators*; per Principle IV (which names "F-Score
  components, valuation multiples" explicitly) they ship with golden-fixture
  tests under `backend/tests/indicators/` **written before** the strategy depends
  on them, plus rules-level unit tests for each gate. ✅ PASS (planned, enforced
  by task ordering in tasks.md).
- **V. User Safety, Risk Disclosure & No-Advice Boundary**: Every value-strategy
  response inherits `data_as_of` + `disclaimer`; the new strategy introduces
  **zero** directive copy (FR-013) and the no-directive Playwright lint must pass.
  Advisor-prompt directive framing for this strategy stays behind the existing
  `SCREENER_PERSONAL_USE_DIRECTIVE` flag (OFF by default), already sanctioned by
  the v1.1.0 Personal-use directive exception. ✅ PASS.

**No violations requiring Complexity Tracking.** The feature is additive: no new
project, no new data source, no new persistence beyond one committed backtest
artifact, no relaxation of any principle.

## Project Structure

### Documentation (this feature)

```text
specs/005-value-midterm-strategy/
├── plan.md              # This file
├── spec.md              # Feature spec (with resolved Q1)
├── research.md          # Phase 0 — value composite, F-Score, sector handling, data-coverage limits
├── data-model.md        # Phase 1 — strategy declaration, valuation inputs, F-Score signals, candidate fields
├── quickstart.md        # Phase 1 — build fundamentals, run the screen, run the backtest, verify determinism
├── contracts/
│   ├── strategy-declaration.md   # required declaration fields + value-specific gate list
│   ├── indicators.md             # valuation multiples + Piotroski F-Score signatures & fixtures
│   └── api-fields.md             # additive Candidate / AnalyzeResponse value fields (back-compatible)
├── checklists/
│   └── requirements.md  # spec quality checklist (done)
└── tasks.md             # Phase 2 — /speckit-tasks (NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── indicators/
│   │   ├── valuation.py                 # NEW — book/market, earnings/cf/sales yields, composite (pure)
│   │   └── piotroski.py                 # NEW — 9 F-Score signals + total (pure)
│   ├── data/
│   │   └── fundamentals.py              # EXTEND — value_metrics_as_of(): composite inputs + F-Score signals, point-in-time
│   ├── screening/
│   │   └── engine.py                    # EXTEND — thread new fundamental columns through _compute_snapshot_rows + _edgar_profiles; reference-threshold refresh for the value-composite cut
│   ├── strategies/
│   │   ├── midterm_value_composite.py   # NEW — declaration + rules() (mirrors momentum structure)
│   │   └── _helpers/
│   │       ├── value_composite.py       # NEW — cross-sectional composite scoring + within-sector ranking
│   │       └── reference_thresholds.py  # EXTEND — cache the value-composite percentile cut alongside gp/ag
│   ├── backtests/
│   │   └── runner.py                    # EXTEND — value-slug candidate pool + uses_fundamentals + NEEDED_TAGS
│   ├── agent/
│   │   └── advisor_prompt.py            # EXTEND — strategy-agnostic backtest path + value diagnostics lines
│   └── models/
│       └── strategy.py                  # EXTEND (optional) — value fields on Candidate / AnalyzeResponse
└── tests/
    ├── indicators/
    │   ├── test_valuation.py            # NEW — golden fixtures (BEFORE strategy)
    │   └── test_piotroski.py            # NEW — golden fixtures (BEFORE strategy)
    ├── strategies/
    │   └── test_midterm_value_composite.py   # NEW — gates, ranking, levels, determinism, sector handling, value traps
    ├── data/
    │   └── test_value_metrics_as_of.py  # NEW — point-in-time selection, missing-input handling
    └── backtests/
        └── test_runner_value.py         # NEW — value branch builds a snapshot + per-year metrics

frontend/
├── src/
│   ├── app/ (screen / candidate / analyze / compare)   # mostly data-driven; verify value columns render
│   └── components/                                       # reuse; add value diagnostic chips if needed
└── tests/e2e/
    ├── no-directive-copy.spec.ts        # EXTEND — new strategy's surfaces stay clean
    └── value-strategy.spec.ts           # NEW (optional) — strategy appears + compares vs momentum
```

**Structure Decision**: Web-application layout (existing). The new strategy is a
backend-first, additive change that mirrors `midterm_52w_high_momentum` so it
inherits the engine, gate-accounting, reference thresholds, level derivation, and
backtest runner. The only genuinely new code is the fundamentals extension and
the two test-first indicator modules; the frontend is data-driven and largely
unchanged. No new top-level project, data source, or persistence layer.

## Complexity Tracking

> No constitutional violations. This feature is additive and follows the
> established mid-term-strategy pattern; the table is intentionally empty.
