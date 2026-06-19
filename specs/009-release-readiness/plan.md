# Implementation Plan: Release Readiness — Test, Harden, Refresh-on-Start & Deployment Prep

**Branch**: `009-release-readiness` | **Date**: 2026-06-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/009-release-readiness/spec.md`

## Summary

A **stabilization and release-readiness pass** over the assembled screener — no
new strategy, no new user capability, and (per the constitution) **no strategy
rule, default, citation, or backtest baseline change**. Four workstreams deliver
the spec's five user stories:

1. **Refresh-on-start (US1)** — a fast (≤ 3 s), no-mutation **startup staleness
   check** that reads only cached `data_as_of` metadata, computes staleness
   against the *latest completed trading session*, and prompts the operator to
   refresh (operator-initiated, never silent). "Refresh" reuses the existing
   **incremental** `/data/refresh` path; nothing rebuilds the universe.
2. **Advisor-prompt completeness (US2)** — make the exported prompt fully
   self-contained: add **per-material-input freshness** to the candidate/honesty
   blocks, confirm integrity warnings travel verbatim, and keep the mandatory
   honesty block driven by the real backtest bias check. Builder stays a pure,
   deterministic function.
3. **Correctness, bug scan & cleanup (US3) + robustness (US4)** — run the full
   backend + frontend suites green on a clean checkout, perform a deliberate bug
   scan across the real runtime surfaces, fix every correctness/integrity/crash
   finding (block-on-correctness bar), harden empty/missing/timeout paths, and
   remove dead code — all preserving determinism.
4. **Deployment readiness (US5)** — a reproducible deployment runbook
   (`quickstart.md`) that takes a clean environment to a running production
   build, documents data directories + process-only provider keys, and ends with
   a suite-green commit on this branch.

**Momentum is primary**; the value strategy is postponed (no further work,
feature 007 not merged) but its existing tests must still pass.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 15 + React 19 (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, pandas/numpy (backend); TanStack Query, Zod, Tailwind, Vitest + Playwright (frontend). No new runtime dependency.
**Storage**: Existing — SQLite + partitioned Parquet (Stooq base, yfinance overlay), EDGAR slim cache, `backend/data/manifest.json` (per-source freshness), calendars. **No schema migration, no new store.**
**Testing**: pytest (backend unit/integration/golden + seeded-defect CI gate), Vitest (frontend unit), Playwright (e2e + no-directive-language lint + `data_as_of`/`disclaimer` presence).
**Target Platform**: Local single-user web app (personal-use scope). Windows dev runbook (`py -3.12`, `npm.cmd`, Next production build for headless).
**Project Type**: Web application (backend + frontend) — existing repository layout.
**Performance Goals**: Startup staleness check **p95 ≤ 3 s** reading cached metadata only (SC-002); full-universe EOD screen stays within the constitution's p95 ≤ 10 s; no regression to existing targets.
**Constraints**: Startup check is **read-only and no-mutation** (never refreshes silently). Refresh is **incremental** (stale-only, reuses caches; FR-003) and **operator-initiated** (FR-001). Determinism preserved: same snapshot → identical screen/regime/sizing/event output (FR-015, SC-010). Free data tier by default; any optional provider key stays **process-local, never written to a file**. "Latest" = latest completed trading session, not calendar day (FR-005).
**Scale/Scope**: Single operator, one machine, ~6,000-ticker liquid universe. Bug scan is bounded to the app's **actual** endpoints and primary flows (screen, candidate detail, advisor prompt, portfolio, data refresh), not hypothetical features.

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.1.0. Re-checked after Phase 1 design.*

| Principle | Verdict | Notes |
|-----------|---------|-------|
| **I. Data Integrity & Provenance** (NON-NEGOTIABLE) | ✅ Strengthens | Refresh-on-start makes the EOD ≤ 1-trading-day freshness SLA actually hold instead of depending on the operator's memory; per-source `data_as_of`/`is_stale` already carried in the manifest. Staleness is measured against the latest *completed trading session* (FR-005), honoring point-in-time honesty. No source change; free providers reused. |
| **II. Strategy Transparency** | ✅ Pass | No strategy rule, parameter default, ranking expression, or citation changes (FR-014, spec Assumptions). Cleanup is forbidden from touching strategy code semantics; suite stays green to prove it. |
| **III. Reproducible Backtesting** (NON-NEGOTIABLE) | ✅ Pass | No backtest code or committed baseline changes. Determinism guarantee (FR-015, SC-010) is explicitly re-asserted as an acceptance criterion. The advisor prompt builder remains a pure function (no wall-clock in body). |
| **IV. Test-First for Financial Logic** | ✅ Pass | This *is* the verification feature: the full fixture-anchored suite must pass green (FR-011) with **0 silently skipped financial-logic tests** (SC-006). New non-financial code (startup-check endpoint, freshness wiring) gets its own tests; it computes no indicator value. |
| **V. No-Advice Boundary** | ✅ Pass | Advisor-prompt work only *adds* freshness/limitations disclosure (more honesty, not less). Zero directive language enforced by the Playwright lint (FR-010, SC-005). `SCREENER_PERSONAL_USE_DIRECTIVE` untouched, OFF by default. Every API response keeps `data_as_of` + `disclaimer` (FR-019). |

**Gate result: PASS — no violations.** Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/009-release-readiness/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions + rationale
├── data-model.md        # Phase 1 — Data Freshness Record, Advisor Prompt Document, Bug Scan Finding, Deployment Runbook
├── quickstart.md        # Phase 1 — the deployment runbook (FR-020) + release verification steps
├── contracts/
│   ├── startup-freshness.md       # GET /data/freshness — read-only staleness detection (≤3s)
│   ├── data-refresh.md            # POST /data/refresh — existing incremental refresh (formalized)
│   ├── advisor-prompt-completeness.md  # required sections incl. per-input freshness
│   ├── bug-scan-log.md            # structure of the findings log + severity/resolution rules
│   └── deployment-runbook.md      # required runbook contents + acceptance
├── checklists/
│   └── requirements.md  # (existing)
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
backend/src/
├── api/
│   ├── data.py            # MODIFY: add GET /data/freshness (read-only, no-mutation staleness detection,
│   │                      #   per-source as-of vs latest completed trading session). /data/refresh unchanged in behavior.
│   ├── meta.py            # REUSE/verify: per-source freshness already manifest-driven; ensure latest-session basis
│   └── analyze.py / screen.py / strategies.py  # MODIFY (if scan finds gaps): empty-state + missing-input + error robustness
├── agent/
│   └── advisor_prompt.py  # MODIFY: per-material-input freshness lines in candidate + honesty blocks (additive, pure)
├── data/
│   ├── prices.py          # REUSE: latest_completed_trading_day(); fetch_incremental_ohlcv() (incremental)
│   └── market_calendar.py # REUSE: trading-session math (weekend/holiday aware)
└── lib/                   # REUSE flags/disclaimer helpers

backend/tests/
├── api/                   # NEW/MODIFY: GET /data/freshness contract + ≤3s read-only behavior; empty-state & error-path tests
├── agent/                 # MODIFY: advisor prompt includes per-input freshness; self-contained; integrity verbatim
└── (existing suites)      # MUST stay green; bug-scan regression tests added where a defect is fixed

frontend/src/
├── components/
│   ├── StartupFreshnessGate.tsx   # NEW: on mount, calls /data/freshness; if stale, prompts refresh-now / proceed-on-cached
│   ├── DataFreshnessPanel.tsx     # MODIFY: drive per-source from /data/freshness; show refresh control + status
│   └── GlobalDataAsOf.tsx         # REUSE/verify: header as-of reflects latest session
├── lib/api.ts             # MODIFY: Zod schema for /data/freshness response
└── app/                   # MODIFY (if scan finds gaps): empty-state, retryable error surfaces

tests (frontend)/
├── unit (Vitest)          # NEW: StartupFreshnessGate states (stale→prompt, current→silent, unreachable→notice)
└── e2e (Playwright)       # MODIFY: startup staleness flow; no-directive lint + data_as_of/disclaimer presence stay green

docs / runbook:
README.md + specs/009-release-readiness/quickstart.md  # MODIFY/NEW: reproducible production-build deployment runbook
specs/009-release-readiness/bug-scan-log.md            # NEW: findings log (location/desc/severity/resolution)
```

**Structure Decision**: Existing web-app layout (backend + frontend) — this is a
hardening pass, so the footprint is deliberately small. The **only genuinely new
runtime surface** is a read-only `GET /data/freshness` endpoint plus a frontend
`StartupFreshnessGate` that consumes it; everything else either reuses an
existing path (`/data/refresh` incremental refresh, `latest_completed_trading_day`,
the manifest) or is additive disclosure (advisor-prompt freshness lines). The
deployment runbook lives in `quickstart.md` (and is mirrored into `README.md` Run
Locally), and the bug scan produces a tracked findings log under the feature dir.

## Phase 0 — Research

See [research.md](research.md). Decisions resolved (the four clarified in
spec.md plus design choices):

1. **Startup refresh UX** — manual-trigger-with-prompt (clarified). A mount-time
   `StartupFreshnessGate` calls the read-only check and, when stale, surfaces a
   non-blocking prompt: *Refresh now* (→ incremental `/data/refresh`) or *Proceed
   on cached data*. Never silent, never auto.
2. **Refresh scope** — incremental / stale-only (clarified). Reuse the existing
   `/data/refresh` (already incremental, ≤ 1,200-ticker capped, updates manifest,
   clears snapshot caches, refreshes reference thresholds). No full rebuild.
3. **Staleness-detection budget** — ≤ 3 s (clarified). The check reads only the
   manifest's cached `data_as_of`/`last_bar_date` per source and compares to
   `latest_completed_trading_day()`. **No network, no recomputation** → easily
   sub-second; the 3 s ceiling is the guarantee, not the target.
4. **Minimum fix bar** — block on correctness + crashes (clarified). The bug-scan
   log classifies each finding; correctness / data-integrity / crash-or-hang in a
   primary flow = **must-fix before release**; cosmetic/minor = may defer with a
   logged rationale.
5. **Detection endpoint vs reusing `/meta`** — add a dedicated, semantically
   explicit `GET /data/freshness` (returns per-source `is_stale`, `data_as_of`,
   `latest_session`, `sessions_behind`, and `any_stale`) rather than overloading
   `/meta`, so the startup gate has a single purpose-built, contract-tested call.
   `/meta` stays for the detailed freshness panel.
6. **Per-surface freshness** — each data-bearing surface reflects its own
   material inputs' as-of (FR-004); the advisor prompt lists per-input freshness
   instead of one global timestamp that could overstate currency.
7. **Determinism & no-mutation** — the startup check mutates nothing; refresh is
   the only mutation and is operator-initiated. The advisor-prompt builder stays
   pure (freshness values come from the snapshot, not wall-clock).

## Phase 1 — Design & Contracts

See [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md).

- **Data Freshness Record** (per source): `source_name`, `kind`,
  `data_as_of` (latest completed session covered), `latest_session`,
  `sessions_behind`, `is_stale`, `last_refresh_outcome`
  (`success` | `failed` | `skipped-current`). Surfaces drive their display from
  this; `GET /data/freshness` returns the list + `any_stale`.
- **Startup freshness contract** (`GET /data/freshness`): read-only, no-mutation,
  ≤ 3 s; staleness computed against latest completed trading session
  (weekend/holiday aware). Carries `data_as_of` + `disclaimer` like every
  response. The frontend gate prompts only when `any_stale` is true.
- **Refresh contract** (`POST /data/refresh`): formalize the existing incremental
  behavior (stale-only, capped, never a full rebuild; on source-unreachable it
  returns the cached state + a non-blocking staleness note rather than failing
  the session — FR-002).
- **Advisor Prompt Document** (additive): candidate block + honesty block gain
  **per-material-input freshness** lines (prices `data_as_of`, fundamentals
  `data_as_of`, regime as-of) so the prompt is self-contained; integrity warnings
  remain verbatim and prominent; honesty block stays driven by the real backtest
  bias check. Builder remains pure/deterministic (FR-006–FR-010).
- **Bug Scan Finding** + **bug-scan-log.md**: each finding = location,
  description, severity (`correctness` | `integrity` | `crash/hang` | `minor`),
  resolution (`fixed` | `deferred-with-rationale`). Release gate: zero open
  must-fix findings (SC-007).
- **Deployment Runbook** (`quickstart.md`): ordered steps from clean environment
  → production build → running app, data-directory + process-only-key config, and
  the primary-flow smoke verification (SC-009). Mirrored into README Run Locally.
- **Robustness**: empty screen → explicit empty-state (FR-016); missing material
  input → deterministic exclude/flag with stated reason (FR-017); backend
  failure/timeout → retryable human-readable frontend error, rest of app
  navigable (FR-018); `data_as_of` + `disclaimer` unconditionally rendered
  (FR-019). Each gets a regression test where a defect is found.

**Agent context update**: the `<!-- SPECKIT START -->…<!-- SPECKIT END -->`
pointer in `CLAUDE.md` is repointed to this plan.

## Complexity Tracking

No constitution violations — none required.
