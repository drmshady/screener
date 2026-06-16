# Implementation Plan: Strategy Defect Detection & Output Integrity (Momentum Pilot)

**Branch**: `008-momentum-data-integrity` | **Date**: 2026-06-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/008-momentum-data-integrity/spec.md`

## Summary

Make the screener able to **detect when its own strategy output is wrong**, so the operator can trust it without an external spot-check. The mechanism is an **invariant/contract-based detector**: each strategy declares a machine-checkable *output contract* (the properties every candidate row must satisfy), a strategy-agnostic engine validates the returned candidates against it, and any violation surfaces as a loud, specific, per-candidate **data-integrity warning** with the flagged name **demoted below all clean candidates** (never excluded). The contract is enforced in two places from one definition: a deterministic, no-network check on **every live screen**, and an **offline harness** (seeded-defect regression + independent-source cross-check) that runs the seeded test as a blocking CI gate and the network cross-check on demand.

The momentum strategy is the pilot. Alongside detection, the known momentum data defects are remediated so clean names are not falsely flagged: `return_12_1` and `52w_high` are computed from a **split+dividend-adjusted series** (the displayed entry stays the latest raw close), the **cross-source seam** stops dropping `adj_close` and is normalised so a stitched history shares one adjustment basis, and price/fundamentals never cross share classes. No strategy rule, default, citation, or committed backtest baseline changes — all work is confined to detection, data correctness, and presentation.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 15 + React 19 (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, pandas/numpy, pytest + hypothesis (backend); TanStack Query, Zod, Tailwind, Vitest + Playwright (frontend). New: a free-tier independent quote vendor SDK/HTTP (Finnhub) used **only by the offline harness**.
**Storage**: SQLite + partitioned Parquet (Stooq deep-history base, warm yfinance overlay store with `adj_close`, EDGAR slim cache). No schema migration; new per-row series-integrity signals are computed at snapshot build, not persisted to new stores.
**Testing**: pytest (golden-fixture indicator/invariant tests + seeded-defect suite), Vitest, Playwright (no-directive-language lint).
**Target Platform**: Local single-user web app (personal-use scope); Windows dev runbook (`py -3.12`, `npm.cmd`, Next prod-build for headless).
**Project Type**: Web application (backend + frontend) — existing repository layout.
**Performance Goals**: Live contract checks add **< 5% to total screen runtime** (SC-005); full-universe screen stays within the constitution's p95 ≤ 10 s EOD target. Series-integrity signals are computed once during the existing per-ticker snapshot loop (no extra passes).
**Constraints**: Live screen is **deterministic and no-network** (FR-002/FR-024 — same snapshot → identical figures *and* identical warning set). Free data tier only — no paid price feed (the independent reference is a free-tier vendor). Any independent-reference API key is **process-local, never written to any file**.
**Scale/Scope**: ~6,000-ticker liquid universe after gates; contract runs over the returned candidate list (top-N cross-check capped at 10). Pilot = `midterm_52w_high_momentum`; the engine is strategy-agnostic and `midterm_value_composite`'s existing implausibility backstop is re-expressed in the same contract form with no behaviour change.

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.1.0. Re-checked after Phase 1 design.*

| Principle | Verdict | Notes |
|-----------|---------|-------|
| **I. Data Integrity & Provenance** (NON-NEGOTIABLE) | ✅ Strengthens | The feature *exists* to enforce this principle: point-in-time adjustment consistency, no silent survivor/seam bias, every figure tied to one source basis. The independent reference is a TOS-permitted free-tier provider used for verification only; any key is process-local and never logged/written. |
| **II. Strategy Transparency** | ✅ Pass | The output contract is a declarative, inspectable rule list per strategy; no black box. No rule, parameter default, or citation changes (FR-023). |
| **III. Reproducible Backtesting** (NON-NEGOTIABLE) | ✅ Pass | No backtest code or baseline changes; SC-010 asserts committed summary metrics are byte-stable. The harness's independent fetch is an **offline validation** activity (timestamped, may be live); it never feeds a screen or backtest, so determinism (FR-024) and reproducibility hold. |
| **IV. Test-First for Financial Logic** | ✅ Pass | The seam-adjustment math and every invariant are financial logic → golden-fixture tests written first; the seeded-defect suite is the CI gate. Enforced by task ordering in tasks.md. |
| **V. No-Advice Boundary** | ✅ Pass | Data-integrity warnings are neutral, factual ("verify before acting") and travel verbatim into the advisor prompt; the directive flag (`SCREENER_PERSONAL_USE_DIRECTIVE`) is untouched and stays OFF by default. |

**Gate result: PASS — no violations.** Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/008-momentum-data-integrity/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions + rationale
├── data-model.md        # Phase 1 — entities (output contract, violation, signals)
├── quickstart.md        # Phase 1 — run the screen + harness; verify BELFB
├── contracts/
│   ├── output-contract.schema.md      # strategy-agnostic contract declaration shape
│   ├── momentum-contract.md           # the momentum pilot's concrete invariants
│   ├── integrity-warning.schema.md    # per-candidate data-integrity warning wire shape
│   └── harness-report.schema.md       # offline report structure (feature-002 pattern)
├── checklists/
│   └── requirements.md  # (existing)
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
backend/src/
├── screening/
│   ├── engine.py                 # MODIFY: run contract after rules(); demote-sort; data_notes
│   ├── integrity/                # NEW — strategy-agnostic detector (one contract, two callers)
│   │   ├── __init__.py
│   │   ├── contract.py           # OutputContract, Invariant, ContractViolation types
│   │   ├── invariants.py         # reusable invariant builders (coherence, gate, score,
│   │   │                         #   level-sanity, value-domain, series-integrity)
│   │   ├── engine.py             # evaluate_contract(results_df, contract) -> annotated df
│   │   └── harness.py            # offline: seeded-defect injection + independent cross-check + report
│   └── ... (regime.py, midterm_matrix.py unchanged)
├── strategies/
│   ├── midterm_52w_high_momentum.py   # MODIFY: declare OUTPUT_CONTRACT (no rule change)
│   └── midterm_value_composite.py     # MODIFY: re-express implausibility backstop as contract
├── data/
│   ├── prices.py / prices_store.py    # MODIFY: keep adj_close through the pipeline
│   ├── independent_quote.py           # NEW — harness-only free-tier quote provider (Finnhub)
│   └── ...
├── models/
│   └── strategy.py               # MODIFY: Candidate gains data_integrity_warnings + data_suspect;
│                                 #   Strategy gains optional output_contract
└── lib/flags.py                  # (env helpers; reuse)

backend/tests/
├── indicators/                   # golden tests for seam-adjustment helper
├── integrity/                    # NEW — invariant unit tests + seeded-defect suite (CI gate)
├── screening/                    # MODIFY: demote-ordering + determinism-with-warnings
├── strategies/                   # MODIFY: momentum contract; value backstop equivalence
└── agent/                        # MODIFY: advisor prompt includes integrity warnings verbatim

scripts/
└── run_integrity_harness.py      # NEW — on-demand: seeded report + independent cross-check report

frontend/src/
├── lib/api.ts                    # MODIFY: Candidate Zod schema gains data_integrity_warnings
├── components/CandidateRow.tsx   # MODIFY: prominent data-integrity badge; 12-1 momentum + sign
└── app/candidate/[ticker]/page.tsx  # MODIFY: surface integrity warning on detail view
```

**Structure Decision**: Existing web-app layout (backend + frontend). The detector is a new `backend/src/screening/integrity/` package so the *one* contract definition is shared by the live caller (`screening/engine.py`) and the offline caller (`integrity/harness.py` + `scripts/run_integrity_harness.py`). Per-strategy contracts live next to each strategy (transparency Principle II); the independent-reference provider lives under `data/` behind a small interface, mirroring `PriceProvider`, and is imported only by the harness so no live path can make a network call.

## Phase 0 — Research

See [research.md](research.md). Decisions resolved (the three clarified in spec.md plus design choices):

1. **Adjustment basis** — compute `return_12_1` / `52w_high` from a split+dividend-adjusted series; display entry = latest raw close (= latest `adj_close`, so `entry == close` coherence holds).
2. **Seam normalisation without new network** — Stooq base carries no `adj_close`; the warm yfinance store does. Stop dropping `adj_close` in `_OVERLAY_COLUMNS`; in the existing 5-day Stooq↔overlay overlap, derive the per-ticker adjustment factor (`yfinance adj_close / stooq close`) and back-adjust the Stooq segment onto the overlay's basis. Where the overlap is empty or the factor is unstable → **flag** (FR-013), never silently correct.
3. **Corporate-action source of truth** — the providers' adjustment data (the `adj_close/close` ratio curve already in the warm store + yfinance split/dividend actions); statistical jump detection is a backstop only for gaps the feed misses (FR-015).
4. **Share-class integrity** — verify the price series and fundamentals join resolve to one share-class identity; flag a cross-class join (BELFA/BELFB) (FR-014).
5. **Independent reference** — a free-tier third-party quote vendor outside the pipeline (Finnhub primary: `/quote` + `/stock/metric` 52-week high; Alpha Vantage fallback), behind a `IndependentQuoteProvider` interface; harness-only; key via `SCREENER_INDEPENDENT_QUOTE_API_KEY` (process-local).
6. **CI split** — seeded-defect suite is a deterministic pytest CI gate; the independent cross-check runs on demand via `scripts/run_integrity_harness.py` and never blocks CI (UNVERIFIED on outage).
7. **Determinism of live series-integrity signals** — computed once in `_compute_snapshot_rows` from data already loaded (no extra network/pass), attached as row columns the contract reads.

## Phase 1 — Design & Contracts

See [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md).

- **Output contract model**: `OutputContract` = ordered list of `Invariant`s; each `Invariant` has a `name`, `severity` (`candidate` → per-candidate warning + demotion; `aggregate` → data note), and a pure predicate over a candidate row (+ optional backing-series signals). The engine returns, per row, a list of `ContractViolation`s and a `data_suspect` boolean. Strategy-agnostic: adding/altering a contract never touches the engine (FR-001).
- **Momentum contract** (FR-003): coherence (`dist_to_high == (52w_high−close)/close`, `entry == close`), gate-satisfaction (proximity holds at the stated parameter), score-reproduction (declared formula within tolerance), level-sanity (`0 < stop_loss < entry < take_profit`, R-multiple matches), value-domain (no NaN/inf, positive price/ATR, `return_12_1`/`52w_high` within plausibility bounds), series-integrity (monotonic unique dates, no unexplained single-session jump, seam consistent).
- **Engine wiring** (`_screen_from_universe`): after `strategy.rules(universe)`, run `evaluate_contract`; attach `data_integrity_warnings` + `data_suspect`; extend the existing sort to `["data_suspect", "warning_count", "score", "ticker"]` so flagged names sort last (FR-018); add an aggregate data note recording how many names were flagged/corrected (FR-004, US4-AC4).
- **Wire models**: `Candidate` gains `data_integrity_warnings: List[DataIntegrityWarning]` and `data_suspect: bool` (additive, optional → existing API consumers unaffected). `Strategy` gains optional `output_contract`.
- **Advisor prompt** (`agent/advisor_prompt.py`): the per-candidate blocks and honesty footer include each candidate's data-integrity warning **verbatim** (FR-019); pure-function determinism preserved.
- **Offline harness** (`integrity/harness.py` + `scripts/run_integrity_harness.py`): (a) seeded-defect injection over a frozen snapshot asserting 100% detection (corrupted price, broken score, stale-but-fresh bar, NaN field, inconsistent `dist_to_high`, seam discontinuity, share-class swap); (b) top-N (≤10) independent cross-check assigning AGREES / DIVERGES-AND-FLAGGED / DIVERGES-UNFLAGGED / UNVERIFIED, distinguishing genuine staleness from a defect; emits a classified report (feature-002 pattern) with the independent-fetch timestamp.
- **Frontend**: `CandidateRow` shows a distinct, prominent data-integrity badge (separate from the existing soft-gate badge) and surfaces 12-1 momentum value **with its sign** (US5/FR-020); `api.ts` Candidate schema extended. Playwright no-directive lint still applies.

**Agent context update**: the `<!-- SPECKIT START -->…<!-- SPECKIT END -->` pointer in `CLAUDE.md` is repointed to this plan.

## Complexity Tracking

No constitution violations — none required.
