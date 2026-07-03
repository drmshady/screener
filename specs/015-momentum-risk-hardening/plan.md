# Implementation Plan: Momentum Risk & Validation Hardening

**Branch**: `015-momentum-risk-hardening` | **Date**: 2026-07-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/015-momentum-risk-hardening/spec.md`

## Summary

Apply the honest-review findings on the primary strategy (`midterm_52w_high_momentum`)
as a **validation, risk-management, and honesty** pass — no screening/selection rule,
gate threshold, citation, or indicator definition changes. Seven slices:

1. **Trustworthy backtest evidence (P1)** — give the *committed* backtest the rigor the
   011-US4 comparison study (`backtests/study.py`) already proved out but which never made
   it into the served baseline: finer-than-annual rebalance cadence (removes the
   January-31-only conditioning), an explicit disclosed per-side cost model, and per-period
   trade counts + low-reliability flags surfaced in the walk-forward panel.
2. **Validate the exits actually shown (P2)** — the runner already has an opt-in
   `modeled_exits` path (011-US4); produce a reproducible fixed-horizon-vs-modeled-exit
   comparison artifact and gate any baseline swap on a documented improvement.
3. **Trailing stop for open holdings (P2)** — add a third protective-level view per open
   holding from the chandelier-exit series already in the pipeline, so a winner shows a
   stop above cost. Presentation, not new data.
4. **Sizing fails safe + portfolio heat bounded (P2)** — replace the fail-open-to-cap-fill
   branch in `size_position` with a conservative fallback, and add an aggregate open-risk
   (portfolio-heat) ceiling reported as a binding constraint.
5. **Regime-aware risk budget (P3)** — opt-in overlay scaling the risk-per-trade fraction
   by the already-computed regime; byte-identical to today when disabled; adopted only if
   the strengthened backtest shows a drawdown improvement.
6. **Honest level rationale (P3)** — attribute the stop to the constraint that actually set
   it (the ATR risk cap when it binds, not the SMA rule) and recalibrate or drop the
   non-binding volatility reward ceiling.
7. **Clearer risk presentation (P2)** — surface risk distance + reward-to-risk on candidate
   cards, the three holding levels with status, sizing binding-constraint + heat headroom,
   and thin-sample year flags in the walk-forward panel — calm, uncluttered, non-directive.

**Technical approach**: extend the existing modules in place (`backtests/runner.py`,
`strategies/levels.py`, `portfolio/sizing.py`, `portfolio/exposure.py`,
`portfolio/holding_levels.py`, `lib/flags.py`) rather than adding new subsystems. Every new
knob is an env flag / `StrategyParameter` defaulting to **current** behavior, so a plain
deploy is byte-identical until the owner (or a gated re-baseline) flips a default. The
strengthened backtest is regenerated **locally and its artifact baked into the image** —
never computed in the hosted backend — matching the 010 hosted-mode "no heavy in-host
ingest / baked read-only snapshot" contract.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 15 App Router + React 19 (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, pandas/numpy, pytest + hypothesis (backend); TanStack Query, Zod, Vitest, Playwright (frontend)
**Storage**: Baked read-only Parquet/JSON snapshot under `backend/data/` (prices, backtests, reference_thresholds); single-owner `portfolio_state.json` / transactions blob; browser `localStorage` for portfolio/watchlist/settings
**Testing**: pytest golden-fixture + regression (financial logic, test-first per Principle IV); Vitest unit + Playwright e2e (no-directive + `data_as_of`/`disclaimer` lints)
**Target Platform**: Hosted = HF backend Space (GHCR Docker image, factory-rebuild) + Vercel BFF frontend; local = `py -3.12` backend + Next prod build
**Project Type**: Web application (FastAPI backend + Next.js BFF frontend)
**Performance Goals**: Live-screen p95 ≤ 10 s (≤ 2 s cached), single-ticker page p95 ≤ 1.5 s (constitution). The strengthened backtest is an **offline/local** job (not on any request path), so its longer runtime is unconstrained by the request SLA.
**Constraints**: Determinism (same snapshot → byte-identical output) end-to-end; `data_as_of` + `disclaimer` on every affected response; zero directive language (Playwright-linted); hosted-mode `personal_use_directive()` forced OFF; secrets runtime-env only, never written to any artifact; hosted backend never runs the heavy backtest and never writes the baked snapshot
**Scale/Scope**: Single owner/operator; ~6,000-ticker post-filter universe; frozen Stooq deep-history snapshot (2008–2024) for backtests; momentum is the primary/only fully-served strategy for this feature

**Deployment-compatibility notes** (the explicit ask — "compatible with current app structure and deployment"):
- The committed backtest baseline `backend/data/backtests/midterm_52w_high_momentum.json` is
  **baked into the image** and served read-only by `GET /strategies/{slug}/backtest`. The
  strengthened run is produced by `python -m backend.src.backtests.runner` **locally**, its
  artifact committed, then shipped via the existing `scripts/publish_chain.ps1` /
  daily-refresh force-rebuild path. No hosted-backend behavior change, no new in-host compute.
- All new behavior rides `lib/flags.py` env flags (same idiom as 011/012/014) and/or
  strategy `PARAMETERS`, each defaulting to **today's** output. `SCREENER_*` flags are the
  operator surface; hosted secrets/config stay runtime-env only.
- New fields are **additive/optional** on existing Pydantic response models
  (`SizingResponse`, `HoldingLevels`, `LevelBlock`, `PortfolioTotals`, backtest JSON), so the
  same-origin BFF proxy and frontend Zod schemas widen without breaking older payloads.
- No new router, no new auth surface, no new external data source, no change to the
  owner-secret dependency or CORS pin.

**NEEDS CLARIFICATION**: none. Every open choice (cadence value, cost bps, heat ceiling,
regime-scale, conviction signal) is a knob whose *default preserves current output* and
whose adopted value is chosen by the gated A/B artifact (US4 rule: test, don't trust), not
guessed here.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| **I. Data Integrity & Provenance** (NON-NEGOTIABLE) | ✅ PASS | No new data source. Reuses the point-in-time frozen Stooq snapshot + EDGAR companyfacts; chandelier/ATR already computed in-pipeline. Cost model is a *disclosed modeled assumption*, tagged in the bias check. Survivorship stays a surfaced known limitation (free Stooq has no delisted names) — this feature does not conceal it, and finer cadence must not hide the sparse-crisis-year coverage note. |
| **II. Strategy Transparency & Peer-Reviewed Foundations** | ✅ PASS | Zero change to `rules()`, gates, thresholds, ranking, or the George & Hwang (2004) citation. New knobs (cadence, cost, heat ceiling, regime budget, conservative fallback) documented in `flags.py`/`PARAMETERS` with defaults + ranges. Regime-aware budgeting is a sizing overlay, not a selection rule. |
| **III. Reproducible Backtesting & Bias Avoidance** (NON-NEGOTIABLE) | ✅ PASS (strengthens) | This feature *tightens* Principle III: adds the required realistic-cost model, enlarges the sample, keeps point-in-time correctness (next-open entry, no look-ahead), keeps ≥15-yr window incl. 2008–2009, and preserves byte-identical re-runs. Any baseline change is gated on a documented, reproducible improvement (FR-006) — never silent. |
| **IV. Test-First for Financial Logic** | ✅ PASS | FR-016: golden/regression tests land before the logic they cover (cost model, trailing level, portfolio heat, conservative fallback, regime scale, rationale attribution). Existing suites stay green with zero silent skips. |
| **V. User Safety, Risk Disclosure & No-Advice Boundary** | ✅ PASS | All new/changed surfaces are neutral and zero-directive (Playwright-linted), carry `data_as_of` + `disclaimer`, and degrade gracefully. Hosted mode keeps `personal_use_directive()` forced OFF and non-waivable. No new PII/credentials. |

**Result**: No violations. Complexity Tracking below is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/015-momentum-risk-hardening/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output — decisions + rationale
├── data-model.md        # Phase 1 output — entities/fields extended
├── quickstart.md        # Phase 1 output — local runbook + gated re-baseline + deploy
├── contracts/           # Phase 1 output — API response deltas
│   ├── backtest.md
│   ├── holdings.md
│   └── sizing.md
├── checklists/          # (pre-existing)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

This feature edits existing files in place; it introduces **no new subsystem, router, or
data source**. Touched paths:

```text
backend/
├── src/
│   ├── lib/
│   │   └── flags.py                     # + cadence, cost-bps, heat-ceiling, regime-budget, conservative-fallback knobs (defaults preserve today)
│   ├── backtests/
│   │   ├── runner.py                    # committed baseline: rebalance cadence, per-side cost, per-period trade counts + reliability flags, modeled-exit already present
│   │   ├── bias_check.py                # `costs` line reflects modeled cost (no longer "not included")
│   │   ├── metrics.py                   # per-period trade count + low-reliability flag in yearly_metric
│   │   └── study.py                     # (reference rigor already here; reuse cadence/cost helpers)
│   ├── strategies/
│   │   └── levels.py                    # US6: honest stop attribution when the ATR cap binds; recalibrate/drop the vol reward ceiling
│   ├── portfolio/
│   │   ├── sizing.py                    # US4: conservative fallback (replace fail-open cap-fill) + portfolio-heat ceiling + binding-constraint
│   │   ├── exposure.py                  # US4: aggregate open-risk (portfolio heat) helper
│   │   └── holding_levels.py            # US3: third "trailing" LevelBlock from chandelier exit
│   ├── models/
│   │   └── portfolio.py                 # additive optional fields (trailing block, heat, binding-constraint, risk-distance/RR)
│   └── api/
│       └── backtest.py                  # pass through per-period counts / reliability flags (read-only)
├── data/backtests/
│   └── midterm_52w_high_momentum.json   # regenerated LOCALLY (gated), baked into image — never computed in-host
└── tests/
    ├── backtests/  strategies/  portfolio/   # test-first golden/regression per FR-016

frontend/
└── src/
    ├── components/
    │   ├── WalkForwardMetricsPanel.tsx  # thin-sample-year flag + per-period trade count column
    │   └── (candidate card / holding levels / sizing)  # risk distance + RR, three holding levels w/ status, heat headroom
    └── lib/api.ts                       # widen Zod/TS types for the additive fields

scripts/
└── publish_chain.ps1                    # unchanged path; used to ship the re-baked artifact + code
```

**Structure Decision**: Web application (existing `backend/` + `frontend/` split). No new
top-level structure. The feature is deliberately implemented as **in-place extensions** to
the modules the honest review named, keeping the deploy surface (baked snapshot + BFF proxy
+ env flags) exactly as feature 010/011 established it.

## Complexity Tracking

> No Constitution Check violations. No entries required.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
