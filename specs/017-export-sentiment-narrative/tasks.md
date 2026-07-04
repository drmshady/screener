---
description: "Task list for feature 017 — Sentiment & Narrative in Exported Advisor Prompts (+ Watchlist Export)"
---

# Tasks: Sentiment & Narrative in Exported Advisor Prompts (+ Watchlist Export)

**Input**: Design documents from `specs/017-export-sentiment-narrative/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/watchlist-advisor-prompt.md, quickstart.md

**Tests**: INCLUDED. Constitution Principle IV (test-first for financial logic) and the plan's
Phase-1 test list require fixture + determinism + no-directive + byte-identical-absent + migration
tests written before the code they cover.

**Organization**: Tasks are grouped by user story. US1 and US2 are both P1; US3 is P2. The store
lookup and the shared `_sentiment_section` renderer are Foundational because all three stories
depend on them.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, and Polish tasks carry no story label)
- Every task names an exact file path.

## Path Conventions

Web application (per plan.md): backend at `backend/src/` + `backend/tests/`; frontend at
`frontend/src/` + `frontend/tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Freeze the pre-feature baseline so byte-identical / no-change guarantees (FR-008,
SC-004, SC-008) can be verified later, and confirm the store fixture path.

- [X] T001 Confirm the full backend + frontend suites are green on a clean checkout (baseline for regression), running `py -3.12 -m pytest backend/tests` and the frontend Vitest/Playwright suites per `specs/017-export-sentiment-narrative/quickstart.md`.
- [X] T002 [P] Capture a frozen baseline of today's sentiment-free prompt output for one screen candidate, one holding, and (for later diffing) note there is no watchlist export yet — save fixtures under `backend/tests/agent/fixtures/017_baseline_prompts/` for the byte-identical-absent assertions (FR-008/SC-004).
- [X] T003 [P] Add a shared pytest fixture that builds a temporary `CapturedReportStore` seeded with captured `SentimentReport` artifacts (normal, no-signal, template-only/budget-exhausted, stale-source) in `backend/tests/sentiment/conftest.py` for reuse across store, agent, and API tests.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The ticker-indexed store lookup (Decision 1) and the shared pure renderer +
builder threading (Decisions 2/3/5) that ALL three user stories consume. No user story can be
wired until these exist.

**⚠️ CRITICAL**: No user-story work (Phase 3+) can begin until this phase is complete.

### Store: ticker-indexed lookup + migration (data-model.md §Extended store; research Decision 1)

- [X] T004 [P] Write failing tests for the store's new `latest_for_ticker` + migration in `backend/tests/sentiment/test_store_latest_for_ticker.py`: (a) `put()` populates `ticker`; (b) `latest_for_ticker` returns the most-recent `captured_at` row for a ticker and `None` when none exist; (c) migration adds the `ticker` column + index to a pre-existing schema and backfills `ticker` from `artifact_json` for legacy rows.
- [X] T005 Add the nullable `ticker` column + `idx_reports_ticker(ticker, captured_at)` index in `_init()`, populate `ticker` from `report.ticker` in `put()`, add the `latest_for_ticker(ticker)` method, and backfill legacy rows once on migration — all in `backend/src/sentiment/store.py` (makes T004 pass).

### Renderer + builder threading (data-model.md §New builder input; research Decisions 2/3/5)

- [X] T006 [P] Write failing renderer tests in `backend/tests/agent/test_sentiment_section.py`: `_sentiment_section(report)` renders label, narrative, narrative-risk (when present), and each dated source under the `### External context — sentiment & narrative` heading; a `NO_SIGNAL`/`unavailable` report prints the explicit status and fabricates NO narrative (FR-003); template-only/budget-exhausted state is reflected as-is; output uses NO `captured_at`/wall-clock (FR-007); every rendered string passes `validate_no_directive_language` (FR-006).
- [X] T007 Implement the pure `_sentiment_section(report: SentimentReport) -> str` renderer in `backend/src/agent/advisor_prompt.py`, consuming only content-addressed fields (label, label_basis, narrative, narrative_source, narrative_risk, budget_state, source_classes_present/omitted, sources, resolution), guarding the no-signal/unavailable states, and passing all copy through `validate_no_directive_language` (makes T006 pass).
- [X] T008 Thread an optional `sentiment_by_ticker: dict[str, SentimentReport] | None = None` kwarg through `_candidate_summary_block`, `_holding_block`, `build_screen_advisor_prompt`, and `build_portfolio_advisor_prompt` in `backend/src/agent/advisor_prompt.py`, calling `_sentiment_section` only when a report exists for that ticker and appending NOTHING when absent (FR-008 byte-identical); keep the builders pure (no store I/O). (Depends on T007.)
- [X] T009 Extend the shared task-instruction copy in `_task_instruction` / `_batch_task_instruction` (and the holding equivalent `_holding_task_instruction`) in `backend/src/agent/advisor_prompt.py` to state that embedded sentiment is **external context that MUST NOT overwrite any computed gate, rank, price level, or size** (FR-004/FR-005), keeping it non-directive. (Depends on T008.)

**Checkpoint**: Store resolves reports by ticker; the renderer and builder plumbing exist and are
proven pure. User stories can now be wired in parallel.

---

## Phase 3: User Story 1 — Sentiment inside the screener-results export (Priority: P1) 🎯 MVP

**Goal**: Each screen candidate with a captured `SentimentReport` carries its embedded sentiment
section inside its block in the `POST /strategies/{slug}/advisor-prompt` output; candidates without
one are byte-identical to today.

**Independent Test**: Capture sentiment for ≥1 candidate, export the screen prompt, confirm that
candidate's block contains the labeled sentiment section separated from its gate/level lines,
candidates without a report are unchanged, re-export is byte-identical, and no directive words appear
(quickstart §2).

### Tests for User Story 1 ⚠️ (write first, must FAIL before T012)

- [X] T010 [P] [US1] Write failing API test in `backend/tests/api/test_screen_advisor_prompt_sentiment.py`: with the seeded store fixture, `POST /strategies/midterm_52w_high_momentum/advisor-prompt` embeds the sentiment section in the captured candidate's block; candidates with no report produce a block byte-identical to the T002 baseline (FR-008); a second identical POST returns byte-identical `prompt` (FR-007); response still carries `data_as_of` + `disclaimer` (FR-015).
- [X] T011 [P] [US1] Write failing fail-soft + no-generation test in `backend/tests/api/test_screen_advisor_prompt_sentiment.py`: a raising/unreadable stored report for one ticker omits only that ticker's section and does not break the export (FR-010); the export path never calls source collection / scorer / narrative generation (FR-009) — assert via a spy/monkeypatch that those are not invoked.

### Implementation for User Story 1

- [X] T012 [US1] In `screen_advisor_prompt` (`backend/src/api/strategies.py`), resolve `sentiment_by_ticker` by best-effort `store.latest_for_ticker(ticker)` per screened candidate (try/except → `None` on error, FR-010), and pass the mapping into `build_screen_advisor_prompt`; do not trigger any generation. (Makes T010/T011 pass.)
- [X] T013 [US1] Verify the single-candidate export (`GET /analyze/{ticker}/advisor-prompt` via `build_advisor_prompt` in `backend/src/api/analyze.py`) still passes and optionally inherits the section through the shared block builder without regression; add/confirm coverage in `backend/tests/api/`.

**Checkpoint**: US1 fully functional and independently testable — the MVP.

---

## Phase 4: User Story 2 — Sentiment inside the portfolio-report export (Priority: P1)

**Goal**: Each holding with a captured `SentimentReport` carries its embedded sentiment section
inside its holding block in `POST /portfolio/holdings/advisor-prompt`; holdings without one are
byte-identical to today.

**Independent Test**: With ≥1 holding that has captured sentiment, export the portfolio prompt and
confirm the section appears in the matching holding block, separated from cost-basis/level/risk
lines, under the same determinism + no-directive + absent-fallback rules as US1 (quickstart §3).

### Tests for User Story 2 ⚠️ (write first, must FAIL before T016)

- [X] T014 [P] [US2] Write failing API test in `backend/tests/api/test_portfolio_advisor_prompt_sentiment.py`: with the seeded store, `POST /portfolio/holdings/advisor-prompt` embeds the section in the captured holding's block; holdings with no report are byte-identical to the T002 holding baseline (FR-008); re-export is byte-identical (FR-007); `data_as_of` + `disclaimer` present (FR-015).
- [X] T015 [P] [US2] Write failing fail-soft + no-generation test in the same file: one bad stored report omits only that holding's section (FR-010) and no paid generation is triggered by export (FR-009).

### Implementation for User Story 2

- [X] T016 [US2] In `portfolio_holdings_advisor_prompt` (`backend/src/api/portfolio.py`), resolve `sentiment_by_ticker` via best-effort `store.latest_for_ticker` per holding and pass it into `build_portfolio_advisor_prompt`; no generation side effects. (Makes T014/T015 pass.)
- [X] T017 [US2] Confirm the single-holding export (`holding_advisor_prompt` → `build_holding_advisor_prompt` in `backend/src/api/portfolio.py`) still passes; thread the mapping into `_holding_block` there too if the inherited section is desired, and cover in `backend/tests/api/`.

**Checkpoint**: US1 AND US2 both work independently against the enriched exports.

---

## Phase 5: User Story 3 — New watchlist export in the same format (Priority: P2)

**Goal**: A net-new `POST /portfolio/watchlist/advisor-prompt` produces one prompt in the
screener-results format over the watched names — strategy declaration once, per-name computed block
with embedded captured sentiment, one shared honesty footer — with an empty watchlist yielding a
clear "no watched names" state.

**Independent Test**: With ≥1 watched name, export the watchlist prompt and confirm each name shows
strategy context + current computed numbers + (when captured) its sentiment section in the screen
layout, honesty caveats appear once, re-export is byte-identical, no directive language; an empty
list yields `watched_count: 0` with a clear no-names body (quickstart §4).

### Tests for User Story 3 ⚠️ (write first, must FAIL before T020/T021)

- [X] T018 [P] [US3] Write failing builder test in `backend/tests/agent/test_watchlist_advisor_prompt.py`: `build_watchlist_advisor_prompt` emits the strategy declaration once, a per-name computed block (reusing `_candidate_summary_block`/`_strategy_context`) with the embedded `_sentiment_section` when present, and one shared honesty footer; empty `tickers` yields a clear "no watched names" body; output is deterministic (no wall-clock) and non-directive (FR-006/FR-007/FR-011/FR-013).
- [X] T019 [P] [US3] Write failing API/contract test in `backend/tests/api/test_watchlist_advisor_prompt.py` per `contracts/watchlist-advisor-prompt.md`: `POST /portfolio/watchlist/advisor-prompt` returns `{strategy, watched_count, personal_use_directive, prompt, data_as_of, disclaimer}`; unknown `strategy_slug` → 422; empty `tickers` → 200 with `watched_count: 0`; unresolvable ticker still appears with a "not priceable / no coverage" note; re-export byte-identical (FR-014); no new paid generation (FR-009).

### Implementation for User Story 3

- [X] T020 [US3] Implement `build_watchlist_advisor_prompt(strategy, results, *, gate_names, directive, survivorship, sentiment_by_ticker=None, ...)` in `backend/src/agent/advisor_prompt.py`, reusing `_strategy_context`, `_candidate_summary_block`, the shared honesty block, and `_sentiment_section`, and producing the explicit "no watched names" body when there are no results (makes T018 pass). (Depends on T007/T008.)
- [X] T021 [US3] Add `WatchlistAdvisorPromptRequest` / `WatchlistAdvisorPromptResponse` models and the `POST /portfolio/watchlist/advisor-prompt` handler in `backend/src/api/portfolio.py`: validate `strategy_slug` (422 on unknown), compute each ticker via `compute_candidate_result(ticker, strategy, as_of)` (best-effort per ticker), resolve `sentiment_by_ticker` via `store.latest_for_ticker`, force `personal_use_directive` OFF in hosted mode, and return with `data_as_of` + `disclaimer` (makes T019 pass). (Depends on T020.)

### Frontend for User Story 3

- [X] T022 [P] [US3] Add the watchlist-export client call (`POST /portfolio/watchlist/advisor-prompt`) in `frontend/src/lib/api.ts`, mirroring the existing screen advisor-prompt client.
- [X] T023 [US3] Add `frontend/src/components/CopyWatchlistAdvisorPrompt.tsx` mirroring `CopyScreenAdvisorPrompt` (reusing the copy plumbing in `frontend/src/lib/advisorPrompt.ts`), posting the watched tickers + active strategy slug and handling the empty-watchlist state. (Depends on T022.)
- [X] T024 [US3] Wire the "Copy watchlist advisor prompt" action into `frontend/src/app/watchlist/page.tsx`. (Depends on T023.)

**Checkpoint**: All three exports (screen, portfolio, watchlist) are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Cross-surface guarantees (no-directive lint, determinism, cost, no baseline drift) and
the quickstart verification.

- [X] T025 [P] Extend the Playwright no-directive copy lint to cover the rendered `prompt` of all three exports (screen, portfolio, watchlist) in `frontend/tests/` (SC-005/FR-006).
- [X] T026 [P] Add a determinism regression test asserting byte-identical re-export across all three prompts on an unchanged snapshot + captured sentiment in `backend/tests/api/` (SC-003/FR-007), and a source-traceability assertion that every embedded sentiment claim maps to a listed dated source (SC-005).
- [X] T027 [P] Add a no-baseline-drift test confirming no strategy rule/default/citation/indicator/gate/backtest artifact changed (diff strategy files + backtest baselines against pre-feature) — `backend/tests/api/test_017_no_baseline_change.py` (FR-017/SC-008).
- [X] T028 Run `specs/017-export-sentiment-narrative/quickstart.md` end-to-end (capture → 3 exports → confirm embedding, absent-fallback, empty-watchlist state, and that `period_spend_usd` does not advance across repeated exports — SC-006/FR-009), then run the full backend + frontend suites and confirm all green. **Result**: backend `pytest backend/tests` 675 passed; frontend Vitest 79 passed; Playwright `no-directive-copy.spec.ts` 16/16 passed (incl. the 3 new/updated screen/portfolio/watchlist export-preview lints). The determinism + no-generation + absent-fallback + empty-watchlist + budget-non-advance guarantees are covered by `test_017_export_determinism.py`, the per-story `*_sentiment.py` tests, and the sentiment budget tests. Four **pre-existing, out-of-scope** Playwright failures were observed in feature-015/016 specs; none touch a feature-017 surface (FR-017). Two were a stale-lint gap (`us7-risk-presentation`, `validation-surface-sweep` older lint helpers didn't exclude the 016 `[data-transaction-record]` "buy/sell" bookkeeping UI) — **fixed** by adding the exclusion to match the canonical `no-directive-copy.spec.ts` (both now green, 3/3). The remaining two (`cockpit-home` "Mid-Term Value Composite", `us3-shariah-filter` "User-marked count") are live-data/timing flakes left as-is per owner decision.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS all user stories.** T005 depends on T004; T007 on T006; T008 on T007; T009 on T008.
- **US1 (Phase 3)** and **US2 (Phase 4)**: both P1; depend only on Foundational. Independent of each other — can run in parallel.
- **US3 (Phase 5)**: P2; depends on Foundational (T007/T008 for the shared renderer). Independent of US1/US2. Frontend T022→T023→T024 chain within the story.
- **Polish (Phase 6)**: Depends on the user stories whose surfaces it verifies (T025–T028 after US1–US3).

### User Story Dependencies

- **US1 (P1)**: after Foundational. No dependency on US2/US3.
- **US2 (P1)**: after Foundational. No dependency on US1/US3.
- **US3 (P2)**: after Foundational. Net-new path; no dependency on US1/US2 (sequenced after per plan priority, but independently testable).

### Within Each User Story

- Tests (T010/T011, T014/T015, T018/T019) written first and FAIL before their implementation tasks.
- Backend model/builder before endpoint; endpoint before frontend (US3).

### Parallel Opportunities

- Setup: T002, T003 in parallel.
- Foundational: T004 (store tests) and T006 (renderer tests) in parallel — different files; then T005 and T007 in parallel.
- US1 vs US2: both P1, fully independent — a second developer can run Phase 4 alongside Phase 3.
- Within a story, the two test tasks marked [P] run together; US3 frontend T022 [P] can start once the contract (T019) shape is fixed.
- Polish: T025, T026, T027 in parallel.

---

## Parallel Example: Foundational Phase

```bash
# Write the two failing test files together (different files):
Task: "Store latest_for_ticker + migration tests in backend/tests/sentiment/test_store_latest_for_ticker.py"  # T004
Task: "Renderer tests in backend/tests/agent/test_sentiment_section.py"                                        # T006

# Then implement together:
Task: "Store ticker column + latest_for_ticker in backend/src/sentiment/store.py"      # T005
Task: "_sentiment_section renderer in backend/src/agent/advisor_prompt.py"             # T007
```

## Parallel Example: P1 stories side-by-side (after Foundational)

```bash
# Developer A — US1:
Task: "Screen export sentiment API tests in backend/tests/api/test_screen_advisor_prompt_sentiment.py"   # T010/T011
# Developer B — US2:
Task: "Portfolio export sentiment API tests in backend/tests/api/test_portfolio_advisor_prompt_sentiment.py"  # T014/T015
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (store lookup + renderer + threading — CRITICAL) →
3. Phase 3 US1 → **STOP and VALIDATE** the screen export embeds sentiment, stays byte-identical
when absent, and re-exports identically → demo.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 (screen export) → test independently → MVP.
3. US2 (portfolio export) → test independently.
4. US3 (watchlist export incl. frontend) → test independently.
5. Polish (lints, determinism, no-drift, quickstart) → ship.

Each story adds a surface without changing any strategy/gate/backtest output (FR-017/SC-008).

---

## Notes

- [P] = different files, no dependency on an incomplete task.
- All backend changes are additive and concentrated in `advisor_prompt.py`, `sentiment/store.py`,
  `api/strategies.py`, `api/portfolio.py`; frontend adds one component + one action button.
- Determinism rests on the renderer never reading `captured_at` / wall-clock (T007) and the
  absent-fallback appending nothing (T008).
- Verify each test task FAILS before its implementation task.
- Commit after each task or logical group.
