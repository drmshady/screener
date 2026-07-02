---
description: "Task list for feature 014 — AI Sentiment & Narrative Intelligence (+ 3 bug fixes)"
---

# Tasks: AI Sentiment & Narrative Intelligence (+ three bug fixes)

**Input**: Design documents from `specs/014-ai-sentiment-narrative/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (sentiment.md, bugfixes.md, deploy-finbert.md)

**Tests**: INCLUDED. The spec/plan explicitly require test-first for financial logic (Constitution
Principle IV): golden-fixture scorer tests, Bug B regime determinism/reason tests, narrative-risk
rule tests, the pure narrative-builder test, the `/sentiment/report` contract test, and the extended
no-directive / disclaimer / determinism lints. Tests for a story are written first and must FAIL
before its implementation.

**Organization**: Grouped by user story (priority order) for independent implementation & testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: `US1`=Bug A, `US2`=Bug B, `BUGC`=Bug C, `US3`=sentiment report, `US4`=portfolio holdings
- Exact file paths are included in each task.

## Path Conventions

Web app: `backend/src/`, `backend/tests/`, `frontend/src/`, `scripts/`, `.github/workflows/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies + config flags shared across the sentiment feature. The three bug-fix
stories (US1/US2/BUGC) depend only on this phase, not on Phase 2.

- [X] T001 [P] Split dependencies in `backend/pyproject.toml`: add runtime wheels `onnxruntime`, `tokenizers`, `google-genai` to `[project].dependencies`; add optional `anthropic`; add `[project.optional-dependencies].export = ["torch", "transformers", "optimum[onnxruntime]"]` (export-only, never baked — per contracts/deploy-finbert.md §1).
- [X] T002 [P] Add new sentiment flags to `backend/src/lib/flags.py`: `SCREENER_SENTIMENT_ENABLED` (default 0), `SCREENER_SENTIMENT_SCORER` (finbert|lexicon), `SCREENER_SENTIMENT_NEWS_PROVIDERS`, `SCREENER_SENTIMENT_LLM_PROVIDER` (gemini|anthropic|none), `SCREENER_SENTIMENT_LLM_MODEL`, `SCREENER_SENTIMENT_MONTHLY_CAP_USD` (default 5.00), `SCREENER_SENTIMENT_SOCIAL` (default 0), reading Finnhub/AlphaVantage/Gemini/Anthropic keys from env only (never written to file).
- [X] T003 [P] Update `.github/workflows/daily-refresh.yml`: add the `export` extra to the CI `pip install` line and document the new HF Space runtime secrets (`FINNHUB_API_KEY`, `ALPHAVANTAGE_API_KEY`, `GEMINI_API_KEY`, optional `ANTHROPIC_API_KEY`) per contracts/deploy-finbert.md §3 (no key ever written to a file).

---

## Phase 2: Foundational — Sentiment engine core (Blocking Prerequisites for US3 + US4)

**Purpose**: The shared, capture-and-serve sentiment engine reused by both sentiment stories (US3
and US4). Determinism, sourcing, budget, and no-directive rules are enforced here.

**⚠️ CRITICAL**: US3 and US4 cannot begin until this phase is complete. (US1/US2/BUGC do not depend on it.)

- [X] T004 [P] Create Pydantic models in `backend/src/models/sentiment.py`: `SourceItem`, `SentimentReport`, `ReportRequest`/`Selection`, and internal `SpendLedger` per data-model.md (fingerprint field, label enum, narrative_source enum, budget_state enum, presentation-only fields).
- [X] T005 [P] Golden-fixture test for the scorer in `backend/tests/sentiment/test_scorer.py`: assert deterministic `P(pos)-P(neg)` labels for known finance headlines on both the FinBERT and Loughran-McDonald lexicon paths (must FAIL first).
- [X] T006 Implement `backend/src/sentiment/scorer.py`: FinBERT (ONNX INT8) score/label lazy-loaded + capped intra-op threads, with the vendored Loughran-McDonald lexicon fallback selected by `SCREENER_SENTIMENT_SCORER` (satisfies T005).
- [X] T007 [P] Add one-time export script `scripts/export_finbert_onnx.py` (uses the `export` extra) writing `backend/data/finbert_onnx/` (model+tokenizer+config) pinned to a FinBERT revision; idempotent (skip if present).
- [X] T008 Bake the model: add scoped `COPY backend/data/finbert_onnx /app/backend/data/finbert_onnx` to `backend/Dockerfile` and call `export_finbert_onnx.py` before the docker build in `scripts/publish_chain.ps1` (mirrors seed_universe; depends on T007).
- [X] T009 Test-first + implement the captured-report store in `backend/src/sentiment/store.py` (+ `backend/tests/sentiment/test_store.py`): fingerprint-keyed durable store under `backend/data/cache/reports.sqlite`; same fingerprint ⇒ byte-identical served artifact, never regenerated; never writes the read-only baked snapshot dirs.
- [X] T010 Test-first + implement the budget guard in `backend/src/sentiment/budget.py` (+ `backend/tests/sentiment/test_budget.py`): monthly spend ledger at `backend/data/cache/spend.json`; a paid call proceeds only if `estimated_spend + projected_cost ≤ cap`; otherwise degrade to `template`; cache hits unmetered.
- [X] T011 [P] Implement bounded, labeled collectors in `backend/src/sentiment/sources.py`: yfinance-news baseline + Finnhub/AlphaVantage backups (fail-soft ordered chain), EDGAR/8-K reuse, free analyst opinion; per-class labeling; social omitted by default; each SourceItem carries source tag + `published_at` + `is_stale`.
- [X] T012 [P] Test-first + implement `backend/src/sentiment/composite.py` (+ test): 24h/7d/30d/90d recency-weighted composite with renormalized missing components (presentation-only).
- [X] T013 [P] Test-first + implement `backend/src/sentiment/narrative_risk.py` (+ `backend/tests/sentiment/test_narrative_risk.py`): rules-based 0–100 score from feasible signals only, with NEUTRAL non-directive labels; omit signals whose sources are unavailable (never estimate).
- [X] T014 Test-first + implement `backend/src/sentiment/narrative.py` (+ `backend/tests/sentiment/test_narrative.py`): pure deterministic template assembler given captured inputs, plus optional provider-swappable LLM prose (Gemini default / Claude Haiku / `none`→template), capture-once; server-side no-directive validation before storing a model narrative (depends on T004, T010, T011).

**Checkpoint**: Sentiment engine complete and unit-tested — US3 can now wire the endpoint.

---

## Phase 3: User Story 1 — Add any screener candidate to the watchlist (Priority: P1) 🎯 MVP — Bug A

**Goal**: Owner can add a candidate to the watchlist from BOTH the results table and the candidate
detail page, with immediate confirmation and no duplicates. Browser-only (no backend/API change).

**Independent Test**: From the results table AND the detail page, add a candidate → visible
confirmation → it appears on `/watchlist` with its entry/stop/target snapshot; re-add ⇒ "already
watched", no duplicate.

### Tests for User Story 1

- [X] T015 [P] [US1] Playwright test in `frontend/tests/e2e/watchlist-parity.spec.ts`: add from table + from detail page, assert confirmation, presence on `/watchlist` with levels snapshot, and no-duplicate on re-add (must FAIL first).

### Implementation for User Story 1

- [X] T016 [US1] Create shared `frontend/src/components/AddToWatchlist.tsx`: calls the existing idempotent `saveCandidate` (dedup on `ticker+strategy_slug`), renders immediate confirmation (FR-A2) and an "already watched" state (FR-A4).
- [X] T017 [US1] Wire `frontend/src/components/CandidateRow.tsx` to use the shared `AddToWatchlist` control (replaces the confirmation-less table click).
- [X] T018 [US1] Add the `AddToWatchlist` control to `frontend/src/app/candidate/[ticker]/page.tsx` (parity with the table; FR-A1).

**Checkpoint**: US1 fully functional and independently testable (MVP shippable).

---

## Phase 4: User Story 2 — Trustworthy market-regime SPY 200-day SMA (Priority: P1) — Bug B

**Goal**: The regime panel shows a concrete SPY close, computed 200-day SMA, verdict, source, and
as-of — never a bare "Unknown" when the data exists; an explicit reason (+ "gate fails open") when
the SMA genuinely can't be computed. Deterministic; no strategy/baseline change.

**Independent Test**: On a fresh/offline/hosted run, the panel shows numeric SPY close + 200-day
SMA + verdict + source + as-of. Forcing true insufficient history ⇒ explicit reason, not "Unknown".
Two runs on one snapshot ⇒ identical.

### Tests for User Story 2

- [X] T019 [P] [US2] Test in `backend/tests/regime/test_regime_source_selection.py`: SPY source selection prefers the series with ≥ `sma_length` rows (baked/stooq over a short yfinance frame), determinism across two runs on one snapshot, and `unavailable_reason` populated on true insufficient history (must FAIL first).

### Implementation for User Story 2

- [X] T020 [US2] Add `unavailable_reason` (and ensure `price_source_name`) to `backend/src/models/regime.py` per data-model.md (verdict null ⇒ reason present).
- [X] T021 [US2] Fix `backend/src/screening/regime.py` `_load_spy` so a short/partial yfinance frame no longer wins over the daily-baked SPY series when it lacks ≥ `sma_length` usable rows.
- [X] T022 [US2] Update `backend/src/regime/calculator.py` to emit a concrete `unavailable_reason` (+ "gate fails open") only when the 200-day SMA is genuinely null, and to cache only a fully-resolved reading (satisfies T019).
- [X] T023 [US2] Surface `spy_close`/`spy_sma200`/`spy_above_sma200`/`price_source_name`/`unavailable_reason`/`as_of_date` in `backend/src/api/regime.py` (RegimeResponse.inputs delta per contracts/bugfixes.md).
- [X] T024 [US2] Update `frontend/src/components/RegimePanel.tsx` to render numeric SPY close/SMA/verdict/source/as-of, or the explicit `unavailable_reason` — never "Unknown".
- [X] T025 [P] [US2] Frontend test in `frontend/tests/e2e/regime-panel.spec.ts` (or Vitest) asserting numeric render and reason render (no "Unknown").

**Checkpoint**: US2 works independently, including hosted + live-feed-down.

---

## Phase 5: Bug C — Trustworthy market-events calendar (Priority: P1)

**Goal**: The Market Events panel reflects the calendar's actual last reseed time (not the static
content date), lists upcoming FOMC/CPI/NFP/PCE/PPI with real dates, and shows the stale badge only
when genuinely past the refresh interval; when official schedules end, it says so (never fabricates
dates or empties silently). Deterministic; no strategy/baseline change.

**Independent Test**: After `scripts/ingest_daily.py` reseeds today, `/events/market` returns
`is_stale: false` with real upcoming dates and no spurious badge; two runs on one snapshot ⇒ identical.

### Tests for Bug C

- [ ] T026 [P] [BUGC] Test in `backend/tests/events/test_market_events_freshness.py`: `is_stale` derives from actual `last_refreshed_at` (reseeded today ⇒ not stale), curated window rolls forward with real dates, and determinism across two runs on one snapshot (must FAIL first).

### Implementation for Bug C

- [ ] T027 [BUGC] Fix `backend/src/data/econ_calendar.py` reseed to stamp a real refresh timestamp on `EventSource.last_refreshed_at` and roll the curated window forward with officially-published dates only (Fed/BLS/BEA); label when the schedule ends.
- [ ] T028 [BUGC] Update `backend/src/models/events.py` so `is_stale` is derived from `now - last_refreshed_at > refresh_interval_days`, with `source_as_of` (content date) surfaced separately.
- [ ] T029 [BUGC] Surface the corrected freshness fields in `backend/src/api/events.py` (`GET /events/market` delta per contracts/bugfixes.md).
- [ ] T030 [BUGC] Ensure `scripts/ingest_daily.py`'s `seed_econ_calendar` call stamps the actual reseed time so the daily refresh advances freshness without owner action.
- [ ] T031 [BUGC] Update `frontend/src/components/MarketEventsPanel.tsx` to show the "Stale events data" badge only when truly stale, and a "schedule extends through <last real date>" note when the curated window ends.
- [ ] T032 [P] [BUGC] Frontend test in `frontend/tests/e2e/market-events-panel.spec.ts` asserting no spurious badge after reseed and the schedule-ends note.

**Checkpoint**: All three P1 bug fixes ship independently (MVP + trust fixes complete).

---

## Phase 6: User Story 3 — Run sentiment & narrative on-request for selected stocks (Priority: P2)

**Goal**: Owner selects stocks (screener results and/or manual ticker), triggers the report, and
each selected name shows a coarse label + short sourced narrative — deterministic, fail-soft,
budget-capped, zero directive language, envelope-carrying. Only selected names run.

**Independent Test**: Select ≥1 stock (results + manual) → run → each shows label + ≤N-sentence
narrative with dated sources; unresolved manual ⇒ "symbol not found"; no-coverage ⇒ explicit
"no signal"; re-run on unchanged snapshot ⇒ byte-identical + $0 spend; no directive terms; unselected
names never analyzed.

### Tests for User Story 3

- [ ] T033 [P] [US3] Contract test in `backend/tests/api/test_sentiment_report.py`: empty selections ⇒ 400; per-name fail-soft (unresolved manual ⇒ `resolution:"symbol_not_found"`, no top-level error); byte-identical re-post from the captured store with $0 added spend; `data_as_of`+`disclaimer` present; only selected tickers analyzed (must FAIL first).

### Implementation for User Story 3

- [ ] T034 [US3] Implement `backend/src/api/sentiment.py` `POST /sentiment/report`: validate non-empty selections, per-name orchestration (sources → scorer → composite → narrative_risk → narrative), capture-and-serve via the store, budget guard, per-name fail-soft, envelope + hosted directive-OFF (depends on Phase 2; satisfies T033).
- [ ] T035 [US3] Register the sentiment router in `backend/src/api/app.py` (owner-secret middleware gates it; no BFF change needed per contracts/deploy-finbert.md §BFF).
- [ ] T036 [US3] Add the client + Zod schemas for `/sentiment/report` in `frontend/src/lib/api.ts`.
- [ ] T037 [US3] Create `frontend/src/components/SentimentReport.tsx`: selection UI + on-request render of label, narrative, per-class sources, narrative_risk, and no-signal/symbol-not-found states.
- [ ] T038 [US3] Create `frontend/src/app/sentiment/page.tsx`: manual-ticker entry + cross-surface selection entry point + "select at least one stock" guard (FR-S0c).
- [ ] T039 [US3] Wire screener results selection (`frontend/src/components/CandidateRow.tsx` / results table) so candidates can be selected and sent to the sentiment report.
- [ ] T040 [P] [US3] Extend Playwright lints for the new surface: `frontend/tests/e2e/no-directive-copy.spec.ts` and `disclaimer-everywhere.spec.ts` sweep `/sentiment`; add a determinism check (same selection ⇒ identical rendered label + narrative).

**Checkpoint**: US3 fully functional and independently testable.

---

## Phase 7: User Story 4 — Run the report on selected portfolio holdings (Priority: P3)

**Goal**: From the portfolio view, owner selects one or more holdings and runs the same on-request
report (reuses the US3 engine + component), under the same determinism / no-advice / fail-soft rules.
Unselected holdings are not analyzed.

**Independent Test**: With holdings present, select ≥1 and run ⇒ each shows label + narrative (or
"no signal"); unselected holdings are never analyzed.

### Tests for User Story 4

- [ ] T041 [P] [US4] Test in `frontend/tests/e2e/portfolio-sentiment.spec.ts`: select holdings → run report → each renders label/narrative or "no signal"; unselected holdings incur no report (must FAIL first).

### Implementation for User Story 4

- [ ] T042 [US4] Add holding selection + "Run report" to `frontend/src/app/portfolio/page.tsx`, reusing `SentimentReport.tsx` with `origin:"holding"` selections (depends on US3).

**Checkpoint**: All user stories independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T043 [P] Verify `scripts/secret_scan.ps1` still passes (no Finnhub/AlphaVantage/Gemini/Anthropic key written to any file).
- [ ] T044 [P] Run the quickstart.md validation §2–§4 (bug fixes, on-request report, budget-degrade with `SCREENER_SENTIMENT_MONTHLY_CAP_USD=0.001`).
- [ ] T045 Verify SC-008: with `SCREENER_SENTIMENT_ENABLED=0`, the baked baseline output is byte-identical (no strategy rule/default/citation/indicator/backtest change).
- [ ] T046 [P] Walk the deploy compatibility checklist (contracts/deploy-finbert.md §Compatibility): BFF reachability, slim runtime image (no `torch`), baked ONNX offline, Space secrets, runtime-writable cache under `backend/data/cache/`.
- [ ] T047 Green-build gate: `py -3.12 -m pytest backend/tests -q`, `npm.cmd run test`, and the no-directive / disclaimer / determinism Playwright specs all pass; end on a suite-green commit.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks US3 + US4 only.** (US1/US2/BUGC depend only on Setup.)
- **US1 / US2 / BUGC (Phases 3–5, all P1)**: Depend only on Setup; mutually independent — can proceed in parallel and ship first.
- **US3 (Phase 6, P2)**: Depends on Foundational (Phase 2).
- **US4 (Phase 7, P3)**: Depends on US3 (reuses its engine + `SentimentReport.tsx`).
- **Polish (Phase 8)**: Depends on all desired stories being complete.

### User Story Dependencies

- **US1 (Bug A, P1)**: Independent — frontend only.
- **US2 (Bug B, P1)**: Independent — backend + frontend.
- **BUGC (Bug C, P1)**: Independent — backend + frontend.
- **US3 (P2)**: Needs Phase 2 engine; independent of the bug-fix stories.
- **US4 (P3)**: Builds on US3.

### Within Each Story

- Tests written first and FAIL before implementation.
- Models → services/engine → endpoints → frontend wiring.

### Parallel Opportunities

- Phase 1: T001, T002, T003 all [P].
- Phase 2: T004, T005, T007, T011, T012, T013 [P] (distinct files); T006 after T005; T008 after T007; T014 after T004/T010/T011.
- The three P1 bug-fix phases (US1, US2, BUGC) can be worked fully in parallel by different developers.
- Test tasks marked [P] within a story run in parallel.

---

## Parallel Example: P1 bug fixes (after Setup)

```bash
# Three independent P1 stories can start together:
Developer A: US1 — T015 (test) → T016, T017, T018
Developer B: US2 — T019 (test) → T020, T021, T022, T023, T024, T025
Developer C: BUGC — T026 (test) → T027, T028, T029, T030, T031, T032
```

---

## Implementation Strategy

### MVP First

1. Phase 1 (Setup).
2. Phase 3 (US1 — Bug A) → **STOP & VALIDATE** → ship the watchlist-parity MVP.

### Incremental Delivery

1. Setup → ship the three P1 bug fixes (US1, US2, BUGC) independently.
2. Phase 2 (engine) + US3 → on-request sentiment report → validate → ship.
3. US4 → portfolio-holding reports → validate → ship.
4. Polish → deploy via `workflow_dispatch` `force_rebuild=true` (`-SkipGuard`, code-only), overlay disabled-by-default until turned on.

---

## Notes

- [P] = different files, no dependencies.
- Keep `SCREENER_SENTIMENT_ENABLED=0` through delivery to preserve the byte-identical baked baseline (SC-008).
- `torch` never enters the runtime image — export-only extra (contracts/deploy-finbert.md).
- Captured store lives under `backend/data/cache/` (runtime-writable, never the read-only baked snapshot).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
