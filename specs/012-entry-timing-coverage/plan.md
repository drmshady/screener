# Implementation Plan: Entry-Timing & Candidate Coverage

**Branch**: `012-entry-timing-coverage` | **Date**: 2026-06-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/012-entry-timing-coverage/spec.md`

## Summary

Three independent, additive-by-default slices layered on the live (feature 010
hosted) single-owner screener. Each ships OFF/at-defaults so the baseline screen is
byte-identical until the owner opts in (SC-009).

1. **US1 (P1) — Entry-timing quality overlay.** A neutral, mechanically-defined
   per-candidate diagnostic attached **only to the mid-term momentum strategy**
   (`midterm_52w_high_momentum`, FR-023). It classifies each surfaced candidate as
   **entry-ready / not-entry-ready / entry-undetermined** from six pass/fail/undetermined
   components (pivot proximity, trend above SMA-200, volume-confirmed breakout, base
   maturity, base depth, not-extended-from-SMA-200) plus explicit disqualifiers
   (climax-top exhaustion, huge-gap breakout; a recent short-lived catalyst attaches a
   non-directive "sell-the-news" warning only). The pivot/base come from an **explicit
   geometric pattern classifier** (flat / cup / cup-with-handle / double-bottom,
   FR-002a) — a new golden-fixture-tested indicator. An optional "entry-ready only"
   filter (default OFF) narrows the list. Each rule is attributed to its source
   (base/pivot/breakout → Minervini (2013)); it is **not** a CAN SLIM strategy and
   emits zero directive language.

2. **US2 (P2) — Expanded candidate coverage.** A per-strategy **three-tier gate
   classification** (FR-009): **essential** (fail → exclude) = liquidity, feature-008
   data-integrity, primary thesis; **preferred/non-essential** (non-pass → retained,
   marked `skipped`, demoted below all clean names) = market regime, sector strength,
   relative strength; **disqualifier** (positive detection → hard-exclude / force
   not-entry-ready) = climax-top exhaustion, huge-gap breakout. Toggleable
   (`expanded_coverage`, default OFF → today's behaviour exactly, FR-013/SC-009). No
   gate threshold changes — only whether a non-pass on a *non-essential* gate excludes
   (FR-015).

3. **US3 (P3) — Quarterly Shariah universe refresh.** Refresh the Halal Terminal–sourced
   compliant universe only when **≥ 90 calendar days** have elapsed since the last
   successful refresh (or on explicit force), reusing the cache with **zero API calls**
   inside the window (FR-016/017), persisting/reading a last-refresh timestamp (missing
   → due, FR-018), surfacing a loud "compliance data stale" warning when the window
   lapses without a successful refresh (FR-019), and updating the reported refresh
   interval to ~90 days so staleness messaging stays accurate (FR-020). Deterministic
   given elapsed-time + key-availability (FR-021).

**Cross-cutting (constitution):** determinism preserved end-to-end (same snapshot →
same classification, candidate set, ordering, refresh decision); `data_as_of` +
`disclaimer` on every response exposing new data; hosted directive-OFF force unchanged;
**no existing strategy rule, default, threshold, citation, indicator, or backtest
baseline changes** (US1 is an additive post-screen annotation, US2 changes only which
already-computed candidates are surfaced/ordered, US3 is data-ops only). New US1
indicators get golden-fixture tests before any surface depends on them. Momentum is
primary; value tests still pass.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 15 + React 19 (frontend). No language change.
**Primary Dependencies**: Existing only — FastAPI, Pydantic v2, pandas/numpy, pytest + hypothesis (backend); TanStack Query, Zod, Tailwind, Vitest/Playwright (frontend). **No new runtime dependency.** US1 adds pure-Python indicator + overlay modules; US2 adds a per-strategy gate-tier map + an order-preserving demotion path that reuses the existing `warning_count`/`data_suspect` sort; US3 adds a calendar-day cadence guard around the existing Halal Terminal seed.
**Storage**: Unchanged — SQLite (`shariah_sources`, `catalog.db`) + partitioned Parquet prices (Stooq deep archive + yfinance warm overlay), EDGAR slim cache, `backend/data/manifest.json`. US1 base/pivot diagnostics are computed from the **price history already loaded** in `_compute_snapshot_rows` (no new store, no schema migration; the Stooq snapshot cache version bumps so older cached snapshots that lack the new columns are invalidated). US3 changes the Halal Terminal source's `refresh_interval_days` (7 → 90) and gates the write — no schema change.
**Testing**: pytest (backend) adds: base-pattern classifier golden-fixture tests (FR-002a, Principle IV, **test-first**); entry-timing component + disqualifier threshold/determinism tests (FR-001–008/022); three-tier gate retention/exclusion/ordering tests (FR-009–015, SC-003/004); Shariah cadence call/skip/stale-decision tests with injected clocks (FR-016–021, SC-005/006/007). Vitest/Playwright add: entry-timing annotation + "entry-ready only" filter rendering, skipped-gate surfacing, zero-directive lint over all new copy (SC-008), `data_as_of`/`disclaimer` presence stays green, and a default-off byte-identical baseline check (SC-009).
**Target Platform**: Public web, free tier — backend on a Hugging Face Docker Space (baked read-only owner-gated snapshot), frontend on Vercel (NextAuth BFF proxy). Local single-user dev runbook unchanged (Windows: `py -3.12`, `npm.cmd`). US3's API-conserving cadence runs in the local-then-republish ingest (`scripts/ingest_daily.py`); the host stays read-only.
**Project Type**: Web application (backend + frontend) + a data-ops cadence guard in the ingest script.
**Performance Goals**: Base/pivot classification is O(history) per candidate computed once in the existing snapshot pass — no extra price I/O, no measurable screen-latency regression (constitution p95 ≤ 10 s screen preserved; the disk snapshot cache already memoizes it). The entry overlay and tier demotion are O(candidates). US3 strictly *reduces* external calls.
**Constraints**: Determinism preserved (same snapshot → byte-identical classification, candidate set, ordering, refresh decision; SC-002/SC-009). Zero directive language in any new copy (SC-008, existing Playwright lint extended). No existing strategy rule/default/threshold/citation/indicator/backtest-baseline change (FR-006/015, spec "Constitutional alignment"). Hosted directive-OFF force + `data_as_of` + `disclaimer` unchanged. US1 base detection bounded by the free daily-bar tier — unclassifiable patterns yield **entry-undetermined**, never a false entry-ready (FR-002a/FR-003). API keys runtime-only, never written to an artifact (US3 touches no key path beyond reading availability).
**Scale/Scope**: Exactly one authorized user; the liquid/compliant universe snapshot already served by 010 (hundreds of compliant names). US1 overlay attaches to momentum candidates only. No backtest re-baseline (distinguishes this feature from 011).

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.1.0. Re-checked after Phase 1 design.*

| Principle | Verdict | Notes |
|-----------|---------|-------|
| **I. Data Integrity & Provenance** (NON-NEGOTIABLE) | ✅ Pass | No new data source. US1 base/pivot/volume diagnostics derive from the **same split/dividend-adjusted price series** feature 008 already enforces (computed in `_compute_snapshot_rows`), carrying the snapshot's `data_as_of`. US3 *reduces* external fetches and keeps the point-in-time compliant universe; a missing/lapsed refresh is surfaced as stale (loud), never silently treated as fresh (FR-018/019). Determinism + delisted/stale handling unchanged. |
| **II. Strategy Transparency** | ✅ Pass | Existing strategies' rules, gates, thresholds, ranking, and **citations are unchanged** (FR-006/015). US1 is an additive post-screen **diagnostic** whose every rule is deterministic, parameterized (documented defaults + ranges), and attributed to its source (Minervini (2013) for base/pivot/breakout); it is explicitly **not** presented under O'Neil/CAN SLIM (FR-007, spec alignment). US2's three-tier map is explicit, per-strategy discoverable, and configurable; it never alters a gate's pass/fail threshold. |
| **III. Reproducible Backtesting** (NON-NEGOTIABLE) | ✅ Pass | **No backtest baseline change.** US1 is a live-screen annotation only (FR-006); US2 changes surfacing/ordering of already-computed candidates, not the strategy whose backtest is committed; US3 is data-ops. No committed `backend/data/backtests/*` artifact is rewritten. Determinism preserved (SC-002/SC-009). Distinguishes this feature from 011's gated re-baseline — there is no Complexity Tracking entry here. |
| **IV. Test-First for Financial Logic** | ✅ Pass | The new **base-pattern geometric classifier** (`indicators/base_pattern.py`) is an indicator and ships with golden-fixture tests asserting flat/cup/cup-with-handle/double-bottom labelling, pivot/handle-high location, length, and depth **before** any overlay consumes it (Principle IV, FR-002a). Entry-component arithmetic, disqualifier triggers, and the tier-demotion ordering get fixture/property tests before the surfaces render them. |
| **V. No-Advice Boundary** (+ hosted clause) | ✅ Pass / enforced | "Good entry point" is rendered as an objective, cited **technical-state classification** ("near pivot", "extended", "immature base") — **zero directive language** (Playwright lint extended to all new copy, SC-008). The short-lived-catalyst "sell-the-news" caution is phrased to *describe* risk, never instruct an action (FR-022). Hosted directive mode stays forced OFF and non-waivable; `data_as_of` + `disclaimer` ride every response exposing the new data. |

**Gate result: PASS — no violations, no tracked exceptions.** Unlike feature 011,
nothing here touches a NON-NEGOTIABLE principle, so Complexity Tracking is empty. The
sensitive areas and how the design closes them: (a) US1 never emits a false
entry-ready — missing/unclassifiable inputs are entry-undetermined (FR-003/002a); (b)
US2 can never surface an essential-gate failure or a disqualifier trigger regardless of
the toggle (FR-011), and never reorders a clean name below a skipped-gate name (FR-012);
(c) US3 fails safe toward freshness (missing timestamp → due) and loudly toward
staleness, never silently reusing an expired universe as if current.

## Project Structure

### Documentation (this feature)

```text
specs/012-entry-timing-coverage/
├── plan.md              # This file
├── research.md          # Phase 0 — pattern-classifier method, component placement, tier model, cadence-guard, determinism decisions
├── data-model.md        # Phase 1 — Entry-timing classification, Base/pivot, Gate classification (3-tier), Compliant-universe refresh state
├── quickstart.md        # Phase 1 — enabling the overlay + filter, the expanded-coverage toggle, and the quarterly-refresh cadence locally
├── contracts/
│   ├── entry-timing.md      # FR-001–008/022/023: classification states, six components, disqualifiers, determinism, momentum-only attach, zero-directive
│   ├── base-pattern.md      # FR-002a: geometric classifier (flat/cup/cup-with-handle/double-bottom), pivot/handle-high, length, depth; golden-fixture contract
│   ├── gate-tiers.md        # FR-009–015: three-tier per-strategy map, fail-open retention + demotion, essential/disqualifier exclusion, default-off identity
│   └── shariah-refresh.md   # FR-016–021: 90-day cadence decision, in-window zero-call reuse, stale surfacing, force bypass, determinism
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
backend/src/
├── indicators/
│   └── base_pattern.py                 # NEW (US1, test-first): explicit geometric base classifier — recognizes/labels
│                                       #   flat / cup / cup-with-handle / double-bottom from an OHLC series, returns
│                                       #   {base_type, pivot, handle_high, base_length_weeks, base_depth, detected}.
│                                       #   Pure, deterministic, golden-fixture tested before any consumer (FR-002a).
├── screening/
│   ├── entry_timing.py                 # NEW (US1): pure overlay composing the six components + disqualifiers from the
│   │                                   #   scalar base/pivot/volume/SMA columns into an entry-timing classification
│   │                                   #   (FR-001–004/022). Zero directive language; momentum-only caller (FR-023).
│   ├── gate_tiers.py                   # NEW (US2): per-strategy gate→tier map (essential/preferred/disqualifier),
│   │                                   #   discoverable + configurable (FR-009/009a); the demote-not-exclude policy
│   │                                   #   for preferred gates and the hard-exclude policy for disqualifiers.
│   └── engine.py                       # MODIFY: in _compute_snapshot_rows, compute base/pivot/breakout-volume columns
│                                       #   from the in-scope price history (no new I/O); bump the Stooq snapshot cache
│                                       #   version. In _screen_from_universe, attach the entry overlay for momentum
│                                       #   only and honor the entry_ready_only + expanded_coverage parameters; the
│                                       #   skipped-gate demotion reuses the existing warning_count/data_suspect sort.
├── strategies/
│   └── midterm_52w_high_momentum.py    # MODIFY (additive): consume the three-tier map for US2 expanded coverage
│                                       #   (preferred gates demote-not-exclude) WITHOUT changing any threshold,
│                                       #   default, citation, ranking, or the output contract. relative-strength
│                                       #   preferred gate added as a soft confirmation only when enabled.
├── shariah/
│   └── refresh_cadence.py              # NEW (US3): should_refresh(now, last_success, interval_days=90, force, key_present)
│                                       #   → deterministic call/skip/stale decision (FR-016–021). Pure, clock-injected.
├── data/
│   └── shariah_halal_terminal.py       # MODIFY (US3): seed_halal_terminal_results / bulk_screen_universe consult the
│                                       #   cadence guard before any network call; refresh_interval_days 7 → 90 in the
│                                       #   manifest metadata (FR-016/017/020). No key ever written to an artifact.
├── lib/
│   └── flags.py                        # MODIFY: add documented, env-overridable knobs — entry-timing thresholds
│                                       #   (pivot window, volume ratios, base-maturity weeks, base-depth %, SMA-200
│                                       #   extension %, climax-top bounds), the gate-tier overrides, and the
│                                       #   Shariah refresh-interval days — same idiom as the existing 011 knobs.
└── models/
    └── strategy.py                     # MODIFY: extend Candidate with an `entry_timing` object (state + six component
                                        #   results + diagnostics) and a `skipped_gates` list (gate + reason). Backward
                                        #   compatible (Optional, default None/[]). ScreenResult unchanged in shape.

backend/tests/
├── indicators/                         # NEW: base_pattern golden-fixture tests (flat/cup/cup-with-handle/double-bottom,
│                                       #   pivot=handle-high, length, depth; undetectable → detected=False). TEST-FIRST.
├── screening/                          # NEW: entry-timing component arithmetic + disqualifier triggers + determinism;
│                                       #   three-tier retention/exclusion/strict-ordering; default-off baseline identity.
└── shariah/                            # NEW: cadence call/skip/stale decisions with injected clocks; in-window zero-call.

frontend/
├── src/components/
│   ├── CandidateRow.tsx / ScreenerTable.tsx   # MODIFY: render the entry-timing classification + per-component chips
│   │                                          #   (neutral, zero-directive) and the skipped-gate badge + reason.
│   ├── StrategyGatesPanel.tsx                 # MODIFY: show the three-tier gate map (essential/preferred/disqualifier).
│   └── (screen controls)                      # MODIFY: "entry-ready only" + "expanded coverage" toggles (default OFF).
└── tests/                                      # NEW: entry-timing + skipped-gate rendering; EXTEND: zero-directive lint
                                                #   over new copy; data_as_of/disclaimer presence; default-off identity.

scripts/
└── ingest_daily.py                     # MODIFY (US3): route the Halal Terminal seed through the cadence guard (skip the
                                         #   API call inside the 90-day window; surface "compliance data stale" when the
                                         #   window lapsed without a successful refresh); honor a --force-shariah flag.
```

**Structure Decision**: Existing web-app layout (backend + frontend) plus a data-ops
cadence guard in the ingest script. US1 adds **one new indicator** (`base_pattern.py`,
test-first) and **one pure overlay** (`entry_timing.py`); detection runs inside the
existing single snapshot pass (`_compute_snapshot_rows`) where the price history already
lives, so there is no new price I/O and the disk snapshot cache memoizes it. US2 adds a
**per-strategy tier map** (`gate_tiers.py`) and reuses the existing
`warning_count`/`data_suspect` demotion sort in `_screen_from_universe`, so skipped-gate
names sink below all clean names by the same machinery as the data-integrity demotion.
US3 is a **calendar-day cadence guard** (`refresh_cadence.py`) wrapping the existing
Halal Terminal seed. All three default OFF/at-current-behaviour so the baseline screen
is byte-identical (SC-009). No new endpoints are required — the entry overlay and
coverage toggles ride existing screen parameters and the `Candidate` model.

## Phase 0 — Research

See [research.md](research.md). Decisions to resolve there:

1. **Base-pattern classifier method (US1, FR-002a).** How to recognize/label flat /
   cup / cup-with-handle / double-bottom and locate the pivot (handle high for
   cup-with-handle) from free daily bars deterministically, with a high-precision
   "undetectable → entry-undetermined" fallback so it never emits a false pivot.
2. **Entry-component placement & determinism (US1).** Compute base/pivot/breakout-volume
   columns in the existing snapshot pass vs a separate post-screen pass; confirm the
   chosen placement keeps detection on the adjusted series, memoized by the snapshot
   cache, and momentum-only (FR-023). Fix climax-top / huge-gap disqualifier thresholds
   and their deterministic measurement window (FR-022).
3. **Three-tier gate model (US2, FR-009/009a).** Map each existing momentum gate to
   essential / preferred / disqualifier; decide how the preferred "demote-not-exclude"
   path reuses the existing tiered-mode `warning_count` ordering without changing
   thresholds, and how the **new relative-strength** preferred confirmation is computed
   from existing series. Confirm default-off = today's output (SC-009).
4. **Shariah cadence guard (US3, FR-016–021).** 90 calendar days, missing-timestamp =
   due, force bypass, in-window zero-call reuse, stale surfacing on lapse; deterministic
   given (elapsed-time, key-present, force). Confirm the manifest `refresh_interval_days`
   bump to 90 drives `ShariahLookup._source_is_stale` staleness messaging (FR-020).

## Phase 1 — Design & Contracts

See [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md).

- **Entry-timing classification** — per-candidate overall state (entry-ready /
  not-entry-ready / entry-undetermined), the six component results (status + measured
  value + reason), the disqualifier results, and the auditable diagnostics (pivot, base
  type, base length, base depth, breakout volume ratio, distance above pivot, distance
  above SMA-200); deterministic, momentum-only, zero-directive
  ([contracts/entry-timing.md](contracts/entry-timing.md)).
- **Base / pivot** — a detected consolidation characterized by type, start/end, length
  (weeks), high (pivot / handle high), and low (depth); the most recent qualifying base
  supplies the active pivot; unclassifiable → not detected
  ([contracts/base-pattern.md](contracts/base-pattern.md)).
- **Gate classification (three-tier)** — per-strategy mapping of each gate to essential
  (exclude on fail) / preferred (non-pass → retained, `skipped`, demoted) / disqualifier
  (positive detection → hard-exclude / force not-entry-ready); configurable; default-off
  reproduces today's screen ([contracts/gate-tiers.md](contracts/gate-tiers.md)).
- **Compliant-universe refresh state** — the cached Halal Terminal compliant universe
  plus its last-successful-refresh timestamp, the ~90-day interval, and the staleness
  flag; the deterministic call/skip/stale decision
  ([contracts/shariah-refresh.md](contracts/shariah-refresh.md)).

**Agent context update**: the `<!-- SPECKIT START -->…<!-- SPECKIT END -->` pointer in
`CLAUDE.md` is repointed to this plan.

## Complexity Tracking

> No Constitution Check violations — this section is intentionally empty. All three
> slices are additive and default-off; nothing touches a NON-NEGOTIABLE principle and no
> committed backtest baseline is rewritten.
