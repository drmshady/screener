# Implementation Plan: Automated Daily Refresh, Realistic Risk Levels & Smarter Sizing

**Branch**: `011-auto-refresh-risk-sizing` | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/011-auto-refresh-risk-sizing/spec.md`

## Summary

Three independent slices layered on the now-live (feature 010) single-owner screener:

1. **US1 — Automated daily refresh & deploy.** Move the existing manual publish
   chain (`scripts/publish.ps1`: refresh → integrity → secret-scan → build →
   push GHCR → Factory-rebuild the Hugging Face Space) into an **unattended cloud
   CI cron** so the hosted `data_as_of` advances every trading day with zero owner
   action. The hosted instance stays read-only (no in-host ingest); only the
   scheduled CI job ingests. A failed step leaves the last known-good snapshot
   live and notifies the owner.
2. **US2 — Realistic stop-loss & take-profit.** Replace the current level method
   (`take_profit = entry + R·(entry − stop)` with a trend/SMA-200 stop that can sit
   arbitrarily far below price) with a **bounded, volatility-/horizon-aware**
   derivation so neither risk distance nor reward distance is ever implausible,
   each candidate carrying a short plain-language, zero-directive rationale.
3. **US3 — Smarter, risk- and conviction-aware sizing.** Replace pure cap-fill
   (`size_position`) with **risk-per-trade sizing** (a configurable capital
   fraction risked to the realistic stop) as the backbone, then an **empirically
   chosen conviction/quality modulation** — fair-value margin of safety is **one
   candidate among several** (volatility targeting / inverse-vol, strategy-rank /
   conviction weighting, or risk-per-trade-only), compared on real data in US4 and
   adopted only if it earns its place — still hard-bounded by the existing
   per-position / per-sector caps. (The owner's original ask was "investigate a
   better option **including** use of fair price"; this keeps fair value in the
   bake-off rather than assuming it.)

**US4 — Investigation & honest validation** is the guardrail: a reproducible,
deterministic comparison artifact on a frozen snapshot chooses each adopted
default and surfaces any backtest-baseline impact. Because the adopted levels
become the **single source of truth in both the live display and the backtest's
modeled exits**, this feature performs a **one-time, controlled re-baseline** of
the affected backtest metrics — **gated behind** the US4 artifact proving the new
method is an improvement, with a constitution reproducibility re-check, never
applied silently. **Screening/selection rules, gates, and citations are
unchanged.** Determinism (same snapshot → byte-identical output), `data_as_of` +
`disclaimer` on every response, zero directive language, and the hosted
directive-OFF force are all preserved. Momentum is primary; value stays postponed
but its tests must still pass.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 15 + React 19 (frontend). No language change.
**Primary Dependencies**: Existing — FastAPI, Pydantic v2, pandas/numpy, pytest + hypothesis (backend); TanStack Query, Zod, Tailwind, Vitest/Playwright (frontend). **New: none at runtime.** US1 adds a **GitHub Actions** scheduled workflow (CI config, not an app dependency) that runs the existing Python pipeline and `docker build/push` + the HF Factory-rebuild REST call. US2/US3 are pure-Python additions to existing modules.
**Storage**: Unchanged — SQLite (`catalog.db` incl. `backtest_runs`) + partitioned Parquet prices, EDGAR slim cache, `backend/data/manifest.json`, calendars. The fair-value estimate reuses the existing point-in-time `FundamentalsLoader.value_metrics_as_of` inputs (book equity, net income TTM, operating CF TTM, revenue TTM, shares) — **no new store, no schema migration**. A re-baselined backtest rewrites the committed `backend/data/backtests/*.json` + `backend/backtests/<slug>/*` artifacts once, deliberately.
**Testing**: pytest (backend) adds: level-realism property tests (FR-007/008/009/010/012), risk+fair-value sizing tests (FR-013–017), fair-value indicator golden-fixture tests (FR-018, Principle IV) if a new computed indicator is adopted, and the method-comparison harness regeneration test (FR-019). Vitest/Playwright add: levels-rationale + sizing-rationale rendering, zero-directive lint on the new copy, `data_as_of`/`disclaimer` presence. The CI workflow gets a dry-run/idempotency check.
**Target Platform**: Public web, free tier — backend on a **Hugging Face Docker Space** (baked read-only snapshot, owner-gated), frontend on **Vercel** (NextAuth BFF proxy). **New automation surface:** GitHub Actions scheduled workflow (cloud CI, no owner machine). Local single-user dev runbook unchanged (Windows: `py -3.12`, `npm.cmd`).
**Project Type**: Web application (backend + frontend) + a CI automation workflow.
**Performance Goals**: Level + sizing derivation stays O(1) per candidate — no measurable screen-latency regression (constitution p95 ≤ 10 s screen preserved). CI daily run completes well within a trading-day gap; it is idempotent and a no-op on non-trading days.
**Constraints**: Determinism preserved (same snapshot → byte-identical levels, sizing, screen, and — post-rebaseline — backtest, FR-012/SC-006). Read-only host, no in-host ingest (010 preserved; CI ingest is the only relaxation, FR-001a). Secrets runtime-only in the CI/host secret stores, never committed or written to any artifact (FR-002a/006, SC-008). Directive mode forced OFF, non-waivable on host (FR-021). `data_as_of` + `disclaimer` on every user-visible response. Free-data fair-value basis only (no paid feed). Never serve a partial/corrupt snapshot (FR-003).
**Scale/Scope**: Exactly one authorized user; the screened liquid/compliant universe snapshot already served by 010. Backtest re-baseline is a one-time controlled regeneration of the affected committed metrics.

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.1.0. Re-checked after Phase 1 design.*

| Principle | Verdict | Notes |
|-----------|---------|-------|
| **I. Data Integrity & Provenance** (NON-NEGOTIABLE) | ✅ Pass | No new data source: the fair-value estimate is computed from inputs already in the snapshot (EDGAR point-in-time `value_metrics_as_of` + price) and carries a source tag + as-of + an availability/trust flag (FR-018). US1 runs the **same** ingest pipeline, only relocated to cloud CI; the snapshot stays point-in-time and the host still serves read-only baked data (FR-001a). The fair-value estimate never applies hindsight (uses the as-of fundamentals already enforced by the loader). |
| **II. Strategy Transparency** | ✅ Pass | Screening/selection rules, gates, ranking, and **citations are unchanged** (FR-022, Out of Scope). The change is to the **post-screen risk overlay** (levels) and **portfolio sizing**, both of which are documented, deterministic, parameterized methods. New/changed parameters (risk-distance bound, reward ceiling basis, risk-per-trade fraction, fair-value adjustment rule) get documented defaults + ranges in code, same as existing `take_profit_r_multiple` / `stop_mode`. The level rationale makes "why this stop/target" inspectable (FR-011). |
| **III. Reproducible Backtesting** (NON-NEGOTIABLE) | ⚠️ Controlled re-baseline — Pass with guardrail | FR-020 makes the adopted levels the single source of truth in the backtest's **modeled exits**. Today the runner exits on a **fixed holding horizon** (`_forward_return`), not on stop/target; adopting level-driven exits **moves the committed baseline**. This is **not** a relaxation of the principle: point-in-time data, delisted coverage, cost/slippage discipline, and **determinism are all preserved**; the same snapshot still reproduces identical results. The re-baseline is **one-time, gated behind the FR-019 comparison artifact** (must show improvement), surfaced explicitly with a reproducibility re-check, and never silent (FR-020, US4). Complexity Tracking records it. |
| **IV. Test-First for Financial Logic** | ✅ Pass | If the adopted fair-value basis introduces a **new computed indicator** (e.g. a simple cited intrinsic-value model), it ships with a golden-fixture test **before** implementation (Principle IV). Level derivation and sizing get fixture/property tests asserting the realism bounds and risk/fair-value monotonicity before the new logic lands. Refactor tolerance respected. |
| **V. No-Advice Boundary** (+ hosted clause) | ✅ Pass / enforced | Level and sizing rationales use neutral framing with **zero directive language** (Playwright lint extended to the new copy). Hosted directive mode stays **forced OFF and non-waivable** (FR-021, unchanged 010 force). Every user-visible response keeps `data_as_of` + `disclaimer`. Secrets (CI + host) are runtime-only, never committed or written to an artifact (FR-002a/006, SC-008). |

**Gate result: PASS — one tracked, justified item (the controlled backtest
re-baseline, III).** See Complexity Tracking.

The sensitive areas and how the design closes them: (a) the backtest re-baseline is
gated behind the US4 artifact and a reproducibility re-check, never silent; (b) the
fair-value estimate is free/transparent/point-in-time with a trust flag and a
fail-open path, so it never silently corrupts sizing; (c) CI ingest preserves the
read-only-host and determinism guarantees of 010.

## Project Structure

### Documentation (this feature)

```text
specs/011-auto-refresh-risk-sizing/
├── plan.md              # This file
├── research.md          # Phase 0 — level-method, sizing-method, fair-value-basis, automation, re-baseline decisions
├── data-model.md        # Phase 1 — Daily update run, Candidate risk levels, Fair-value estimate, Sizing suggestion, Method comparison artifact
├── quickstart.md        # Phase 1 — enabling the CI automation + regenerating the comparison artifact + performing the gated re-baseline
├── contracts/
│   ├── daily-automation.md     # GitHub Actions cron: schedule, idempotency, abort-before-publish, notify-on-fail
│   ├── risk-levels.md          # derive_levels v2 contract: invariants + realism bounds + rationale + determinism
│   ├── sizing.md               # size_position v2 contract: risk-per-trade + fair-value modulation + cap hard-bound + fail-open + rationale
│   ├── fair-value.md           # fair-value estimate contract: basis, provenance/freshness, trust flag, fallback
│   └── method-comparison.md    # FR-019 artifact contract: deterministic per-method realism/robustness report + selected default + backtest impact
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
backend/src/
├── strategies/
│   ├── midterm_52w_high_momentum.py   # MODIFY: derive_levels → bounded realism method (risk-distance cap,
│   │                                  #   reward ceiling), level rationale string, graceful insufficient-data state.
│   │                                  #   New documented PARAMETERS (max risk-distance ATR/%, reward-ceiling basis).
│   │                                  #   Screening rules()/gates/citation UNCHANGED.
│   └── midterm_value_composite.py     # MODIFY: same level-method update (shared helper) so both mid-term
│                                      #   strategies derive realistic levels. Selection logic unchanged.
├── indicators/
│   ├── valuation.py                   # REUSE: existing yields feed the fair-value estimate.
│   └── fair_value.py                  # NEW (if adopted): a simple cited intrinsic-value model, pure + golden-fixture
│                                      #   tested. Carries its own provenance; returns None when inputs are missing.
├── portfolio/
│   └── sizing.py                      # MODIFY: size_position → risk-per-trade target (capital fraction at risk to
│                                      #   the FR-007 stop) × fair-value margin-of-safety modulation, still ≤ caps;
│                                      #   binding-constraint rationale; fail-open when fair value unavailable.
├── lib/
│   └── (config readers)               # MODIFY: add risk-per-trade fraction + level-bound config readers
│                                      #   (documented defaults; env-overridable like existing flags).
├── backtests/
│   └── runner.py                      # MODIFY (gated): add level-driven modeled exits (stop/target) as the single
│                                      #   source of truth, replacing/augmenting fixed-horizon forward return for the
│                                      #   re-baseline. Point-in-time + determinism preserved.
└── models/
    ├── strategy.py / portfolio.py     # MODIFY: extend level + sizing response models with realism-bound metadata,
                                       #   fair-value estimate + trust flag, binding-constraint + rationale fields.

backend/tests/
├── strategies/ or screening/         # NEW: level realism-bound property tests (invariants, bounded risk/reward,
│                                     #   reward ceiling, insufficient-data fallback, determinism).
├── portfolio/                        # NEW: risk-per-trade sizing, wider-stop→smaller-size, fair-value monotonicity,
│                                     #   cap hard-bound never breached, fail-open path, rationale + determinism.
├── indicators/                       # NEW (if adopted): fair_value golden-fixture test (Principle IV, test-first).
└── backtests/                        # NEW: modeled-exit determinism + the re-baseline regeneration check.

frontend/
├── src/components/                   # MODIFY: render the per-candidate level rationale + sizing binding-constraint
│                                     #   rationale (neutral, zero-directive); show fair-value + trust flag.
└── tests/                            # NEW: rationale rendering; EXTEND: no-directive lint over new copy;
                                      #   data_as_of/disclaimer presence stays green.

automation (repository root):
├── .github/workflows/daily-refresh.yml   # NEW: scheduled cron → run pipeline → integrity → secret-scan → build →
│                                         #   push GHCR → Factory-rebuild HF Space → notify on failure. Secrets from
│                                         #   the Actions encrypted store only (FR-002a). Idempotent / non-trading-day no-op.
├── scripts/publish.ps1                   # REUSE/REFACTOR: factor the shared steps so CI and local invoke one chain.
└── tools/ (comparison harness)           # NEW: the FR-019 method-comparison artifact generator (deterministic,
                                          #   frozen-snapshot) that justifies the adopted defaults + reports backtest impact.
```

**Structure Decision**: Existing web-app layout (backend + frontend), plus a
**CI automation workflow** and a **comparison-harness tool**. US2/US3 modify
existing computation modules in place (`derive_levels`, `size_position`) behind
their existing call sites (`api/analyze.py`, `api/portfolio.py`) so the API shape
and determinism are preserved; only the derivation math, response metadata, and
rationale strings change. US1 is pure CI/ops config wrapping the existing publish
chain. The backtest runner change is **gated** and one-time.

## Phase 0 — Research

See [research.md](research.md). Decisions to resolve there:

1. **Level method (US2).** Choose the bounded realism method: cap the **risk
   distance** (e.g. `entry − stop` ≤ k·ATR and/or ≤ a % of price) so a far-below
   SMA-200 trend stop can't blow up the R-multiple target, and bound the
   **reward** by a realistic ceiling (a measured technical move, a volatility ×
   √horizon limit, and/or a fair-value cap). Keep entry = latest close. Decide
   exact bounds **empirically in US4**.
2. **Fair-value basis (US3, FR-018/019).** Compare at least (a) reusing the
   existing value-composite/valuation yields vs (b) a simple **cited** intrinsic
   model (e.g. Graham number / earnings-power value / residual income) on real
   data for reliability + coverage; adopt the most reliable; record in the
   artifact. New computed indicator ⇒ golden-fixture test-first.
3. **Sizing method (US3).** Risk-per-trade fraction f of capital risked to the
   stop ⇒ `shares ≈ f·capital / (entry − stop)` as the backbone, then a
   **conviction/quality modulation chosen empirically from a candidate set** —
   (a) fair-value margin of safety (discount → no smaller, may be larger; premium
   → may shrink/cap), (b) volatility targeting / inverse-volatility, (c)
   strategy-rank / conviction weighting, (d) none (risk-per-trade only) — then
   clamp to the per-position/per-sector caps. Each candidate is compared in US4 on
   real data for sizing realism + robustness; the most reliable is adopted, fair
   value not assumed to win. Fail-open when the adopted modulator's input is
   missing (e.g. no trusted fair value).
4. **Backtest exit model (FR-020).** Decide modeled stop/target exits (intrabar
   stop-then-target ordering, gap handling) that make the adopted levels the
   single source of truth, preserving point-in-time + determinism. Quantify the
   baseline delta in the artifact; the re-baseline is gated on it being an
   improvement.
5. **Automation (US1).** GitHub Actions scheduled cron: trading-day/idempotency
   guard (skip when no new completed session), abort-before-publish on any
   failed step, last-good stays live, owner notification channel, secrets in the
   Actions store. Confirm a cloud runner can `docker build`/push to GHCR and call
   the HF Factory-rebuild REST endpoint.

## Phase 1 — Design & Contracts

See [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md).

- **Daily update run** — one scheduled CI execution with a success/failure
  outcome, idempotent and a no-op on non-trading days; advances `data_as_of` only
  on success; notifies on failure ([contracts/daily-automation.md](contracts/daily-automation.md)).
- **Candidate risk levels** — entry, stop_loss (+ tighter variant), take_profit,
  the realism bounds satisfied, and the derivation rationale; invariants
  `stop_loss < entry < take_profit`, `stop_loss > 0`; deterministic
  ([contracts/risk-levels.md](contracts/risk-levels.md)).
- **Fair-value estimate** — per-candidate intrinsic/fair price with a documented
  free basis, freshness/provenance, and an availability/trust flag; out-of-range
  estimates are not trusted blindly ([contracts/fair-value.md](contracts/fair-value.md)).
- **Sizing suggestion** — suggested shares/value, the risk-per-trade target, the
  fair-value adjustment, the binding constraint, cap-respect status, and rationale
  ([contracts/sizing.md](contracts/sizing.md)).
- **Method comparison artifact** — the reproducible per-method realism/robustness/
  coverage report on a frozen snapshot that justifies each adopted default and
  states the backtest-baseline impact ([contracts/method-comparison.md](contracts/method-comparison.md)).

**Agent context update**: the `<!-- SPECKIT START -->…<!-- SPECKIT END -->`
pointer in `CLAUDE.md` is repointed to this plan.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| One-time controlled re-baseline of the committed backtest metrics (touches NON-NEGOTIABLE Principle III) | FR-020: the displayed levels must equal the backtest's modeled exits, or the backtest no longer reflects what the owner would actually do — keeping old exits while showing new levels is itself a transparency/reproducibility defect. | Keeping the backtest on fixed-horizon exits while changing displayed levels was rejected: it makes the published equity curve describe a strategy the owner isn't running. The re-baseline preserves point-in-time data, delisted coverage, cost/slippage, and determinism; it is gated behind the FR-019 improvement artifact and a reproducibility re-check, and surfaced explicitly — so the principle's intent (no bias, fully reproducible, never silent) is upheld. |
