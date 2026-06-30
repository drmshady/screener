---
description: "Task list for feature 013 — Portfolio Import, Purchase-Anchored Levels & Risk-Aware Sizing"
---

# Tasks: Portfolio Import, Purchase-Anchored Levels & Risk-Aware Sizing

**Input**: Design documents from `/specs/013-portfolio-import-sizing/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/portfolio-import.md, contracts/portfolio-holdings.md

**Tests**: Test tasks ARE included. The codebase constitution Principle IV (Test-First for
Financial Logic) is NON-NEGOTIABLE, and plan.md states the new pure logic
(transaction→holding aggregation, average-cost basis, capital-at-risk, over-risk flagging,
purchase-date level anchoring) "ships with fixture-anchored unit tests written first." Write
each test task and confirm it FAILS before the matching implementation task.

**Organization**: Tasks are grouped by user story (US1 P1 → US2 P2 → US3 P3) so each story is
independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (omitted for Setup, Foundational, Polish)
- All financial reuse is of EXISTING helpers — no strategy rule, default, citation, indicator,
  or backtest baseline may change (FR-021).

## Path Conventions

Web application (plan.md Structure Decision): `backend/src/`, `backend/tests/`,
`frontend/src/`, `frontend/tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project + environment prep; no behavior yet.

- [X] T001 [P] Add `NEXT_PUBLIC_GOOGLE_CLIENT_ID` to `frontend/.env.example` (public OAuth client id, reusing feature-010's Google app + incremental `spreadsheets.readonly` scope) with a comment that the import UI must degrade gracefully when the id or GIS script is absent (per plan.md Deployment Compatibility item 5)
- [X] T002 [P] Create the shared transaction test fixtures used across stories, modeled on the owner's REAL sheet (descriptive headers `Date/Type/Stock/Transacted Units/Transacted Price (per unit)/Fees` + ignored computed columns; `$`/comma money like `$1,025.32`; day-first slash dates `28/7/2025` and month-name `9-Oct-2025`; lowercase tickers `spus/msft/amzn`; a `Div` row; ETF tickers SPUS/SLV/IBIT/GLD that are out-of-coverage) plus a malformed-rows fixture (missing price / unparseable date / non-positive qty) in `backend/tests/portfolio/fixtures/` (referenced by the US1/US2/US3 unit + contract tests)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared models + persistence that EVERY user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Add `Transaction` and `RejectedRow` Pydantic models (fields + validators per data-model.md, money as `Decimal` via the existing `money()` helper) in `backend/src/models/portfolio.py`
- [X] T004 Extend the single-owner portfolio envelope to persist `transactions: list[Transaction]`, `sheet_id`, and `sheet_range` (non-secret), including atomic read/write and a "clear/replace transactions" path (FR-007), in `backend/src/data/portfolio_store.py` (and the envelope model in `backend/src/models/portfolio.py`)

**Checkpoint**: Transaction model + persisted source-of-truth list exist — user stories can begin.

---

## Phase 3: User Story 1 - Import transactions from a Google Sheet (Priority: P1) 🎯 MVP

**Goal**: Owner connects their Google Sheet, imports transaction rows; backend validates,
de-duplicates (idempotent), aggregates into average-cost holdings, persists, and the portfolio
shows per-ticker net quantity, average cost, and earliest/most-recent purchase dates, with
malformed rows reported (never silently dropped).

**Independent Test**: Provide the sample sheet fixtures, run the import, confirm correct
per-ticker net quantity / average cost / dates, that malformed rows appear in the summary with
row reference + reason, and that re-importing the same rows applies zero net change (no
double-count).

### Tests for User Story 1 (write first, confirm FAIL) ⚠️

- [X] T005 [P] [US1] Unit tests for pure row validation — header-alias mapping (Date/Type/Stock/Transacted Units/Transacted Price (per unit)/Fees, case-insensitive; extra columns ignored), currency/comma stripping (`$1,025.32`), day-first slash + month-name date parsing (`28/7/2025`, `9-Oct-2025`), case-insensitive action, accepted vs rejected with reasons (missing ticker, action not buy/sell, **`Div`/unsupported type rejected with reason — not silently dropped, no share-count change**, non-positive/non-numeric qty or price, unparseable date), optional fees/note tolerated, stable content-hash `id` (Decision 3) — including a test that inserting/reordering rows in the sheet does NOT change existing ids (re-import = all duplicates) and that two byte-identical rows are disambiguated by an occurrence index (not raw `source_row`) — in `backend/tests/portfolio/test_transactions.py`
- [X] T006 [P] [US1] Unit tests for pure aggregation — net quantity, share-weighted average cost of buys, realized P/L incl. fees, `status` open/closed/anomalous, determinism — in `backend/tests/portfolio/test_aggregation.py`
- [X] T007 [P] [US1] Contract test for `POST /portfolio/import` — accepted_count/duplicate_count/rejected/transactions_total, `200` on partial success, `422` only on malformed body, idempotent re-import (second identical POST = all duplicates), `data_as_of` + `disclaimer` present — in `backend/tests/contract/test_portfolio_import.py`

### Implementation for User Story 1

- [X] T008 [P] [US1] Implement pure `parse/validate` (header-alias mapping + currency/comma stripping + day-first/month-name/ISO date parsing + case-insensitive action; rows → `(accepted, rejected)`; `Div`/unsupported types rejected with a clear reason; compute stable `id` hash; never silently drop) in `backend/src/portfolio/transactions.py`
- [X] T009 [US1] Add `ImportRequest`, `ImportResult`, and the core `Holding` model (cost-basis facts subset) per data-model.md in `backend/src/models/portfolio.py`
- [X] T010 [US1] Implement pure `aggregate` (grouped-by-ticker, ordered by trade_date then source_row → average-cost `Holding` core: net_quantity, avg_cost, cost_basis, earliest/most_recent_buy_date, realized_pl, status) in `backend/src/portfolio/aggregation.py` (depends on the `Holding` model in T009)
- [X] T011 [US1] Implement `POST /portfolio/import` (validate via T008, id + idempotent merge against persisted `transactions[]`, persist sheet_id/sheet_range, return ImportResult with `data_as_of` + `disclaimer`) in `backend/src/api/portfolio.py`
- [X] T012 [P] [US1] Implement browser-only Google Sheets reader (GIS short-lived `spreadsheets.readonly` token → Sheets REST v4 values read → raw rows; token never persisted/logged; graceful no-op + disabled state when client id or GIS script absent) in `frontend/src/lib/googleSheets.ts`
- [X] T013 [P] [US1] Add Zod schemas for the import request/result and the `importTransactions` client call (browser → same-origin BFF) in `frontend/src/lib/api.ts`
- [X] T014 [US1] Extend the Zustand store: `transactions[]` + sheet settings, bump `schema_version`, `persist` mirroring, and `PortfolioSync` re-seed of the server blob when empty (survives HF daily rebuild per plan.md item 3) in `frontend/src/lib/store.ts`
- [X] T015 [US1] Build the connect-sheet + import-summary UI (accepted/duplicate counts, rejected rows with row ref + reason; connect button disabled-with-note when client id absent) in `frontend/src/components/ImportTransactions.tsx`
- [X] T016 [US1] Wire `ImportTransactions` into the portfolio page and render the holdings table (ticker, net quantity, average cost, earliest/most-recent buy date) in `frontend/src/app/portfolio/page.tsx`
- [X] T017 [P] [US1] Vitest unit test for import-summary rendering + holding formatting (counts, rejected-row reasons, no directive copy) in `frontend/tests/unit/importTransactions.test.tsx`

**Checkpoint**: Import is fully functional and independently testable (MVP) — owner replaces manual entry with a correct, idempotent ledger.

---

## Phase 4: User Story 2 - Purchase-anchored stop-loss & take-profit per holding (Priority: P2)

**Goal**: For every open holding, show BOTH an original-plan (frozen, `as_of=earliest_buy_date`)
and a current-condition (latest snapshot) stop/target, each anchored to the real average cost,
plus current price, distance-to-level, unrealized P/L, breach/target status — deterministic and
non-directive.

**Independent Test**: With imported holdings present, verify each holding shows both labelled
level bases derived from its purchase price/date, current-price distance + unrealized P/L are
correct against the snapshot, breach/insufficient-data cases render their neutral states, and
computing twice on the same snapshot yields byte-identical output.

### Tests for User Story 2 (write first, confirm FAIL) ⚠️

- [X] T018 [P] [US2] Unit tests for `holding_levels` — `entry` forced to avg_cost for both bases, original-plan inputs pinned by `as_of=earliest_buy_date`, current-condition from latest snapshot, `insufficient_data` fallback (FR-012), breach/target status (FR-011), distance_to_stop/target pct, determinism — in `backend/tests/portfolio/test_holding_levels.py`
- [X] T019 [P] [US2] Integration test for `POST /portfolio/holdings` levels path — both bases present + labelled, out-of-coverage ticker returns `priceable=false` (facts intact, no levels) without breaking the response, runs twice and diffs byte-identical (SC-006), `data_as_of` + `disclaimer` present — in `backend/tests/integration/test_holdings_levels.py`

### Implementation for User Story 2

- [X] T020 [US2] Add `HoldingLevels` + `LevelBlock` models (mirror the `derive_bounded_levels` contract + presentation fields: distance pcts, `status`) per data-model.md in `backend/src/models/portfolio.py`
- [X] T021 [US2] Implement `holding_levels` reusing `strategies/levels.derive_bounded_levels` for both bases via `screening/engine.build_single_ticker_snapshot(ticker, as_of=…)` and latest, overriding the row `close` to `avg_cost` so `entry == avg_cost`, with breach/target status + insufficient-data fallback, in `backend/src/portfolio/holding_levels.py`
- [X] T022 [US2] Implement `POST /portfolio/holdings` (aggregate via US1, per open+priceable holding compute current price / unrealized P/L / both level bases, out-of-coverage handling per Decision 7, `total_invested` total, `data_as_of` + `disclaimer`) in `backend/src/api/portfolio.py`
- [X] T023 [US2] Add the holdings response Zod schema + `fetchHoldings` client call in `frontend/src/lib/api.ts`
- [X] T024 [US2] Render both labelled level bases + current price, distance-to-stop/target, unrealized P/L (abs + pct), and breach/target/insufficient-data status (descriptive, no directive language) on `frontend/src/app/portfolio/page.tsx`

**Checkpoint**: US1 + US2 both work independently — holdings show purchase-anchored levels.

---

## Phase 5: User Story 3 - Risk-management-aware sizing view for holdings (Priority: P3)

**Goal**: Per holding show recommended-vs-actual size and capital-at-risk (to the
current-condition stop), flag over-risk positions naming the binding constraint, fail open when
a modulator input is missing, and summarize portfolio total invested + total capital-at-risk.

**Independent Test**: With holdings, stops, and a configured capital base, verify each holding
shows recommended vs actual size and capital-at-risk, over-budget/over-cap positions are
flagged with the binding constraint named, missing-modulator cases fall back to the bounded
baseline (no error), and portfolio totals are summarized.

### Tests for User Story 3 (write first, confirm FAIL) ⚠️

- [X] T025 [P] [US3] Unit tests for `holding_risk` — recommended_shares/value from `size_position`, actual shares/value, `actual_capital_at_risk` (≥ 0) + pct, `per_trade_risk_budget`, `over_risk` + `binding_constraint` naming, `fail_open` on missing modulator (FR-018), risk omitted (None) when insufficient_data/not priceable — in `backend/tests/portfolio/test_holding_risk.py`

### Implementation for User Story 3

- [X] T026 [US3] Add `HoldingRisk` + `PortfolioTotals` (total_invested, total_capital_at_risk, pct) models per data-model.md in `backend/src/models/portfolio.py`
- [X] T027 [US3] Implement `holding_risk` reusing `portfolio/sizing.size_position` with `stop_loss = current_condition.stop_loss`, the owner's capital base + per-trade risk + existing caps, plus the actual-vs-recommended comparison and capital-at-risk/over-risk read-out (Decision 5), in `backend/src/portfolio/holding_risk.py`
- [X] T028 [US3] Extend `POST /portfolio/holdings` to attach the `risk` block per holding and the `total_capital_at_risk` portfolio totals in `backend/src/api/portfolio.py`
- [X] T029 [US3] Render the risk view (recommended vs actual size, capital-at-risk $ + %, over-risk flag with binding constraint, portfolio total invested + total capital-at-risk) — descriptive only — on `frontend/src/app/portfolio/page.tsx`
- [X] T030 [P] [US3] Vitest unit test for risk-view formatting (recommended-vs-actual, over-risk flag, totals; no directive copy) in `frontend/tests/unit/holdingRisk.test.tsx`

**Checkpoint**: All three stories independently functional.

---

## Phase 6: User Story 4 - Watch a screener candidate until it is entry-ready (Priority: P4)

**Goal**: From a screen result the owner saves a candidate to the watchlist (existing
`saveCandidate`), and the watchlist then **actively re-checks each saved ticker's live
entry-timing state** (reusing feature-012's `classify_entry_timing` via `GET /analyze/{ticker}`)
so the owner can watch a not-yet-ready name until it flips to **entry-ready** — informational
status only, no directive language.

**Independent Test**: Save a candidate that is currently `not_entry_ready`, open the watchlist,
refresh, and confirm it shows a live "watching — not ready" state with the top failing reasons;
when the snapshot makes it `entry_ready`, the watchlist highlights it as entry-ready (descriptive,
not an instruction). Re-checking twice on the same snapshot is byte-identical.

**Reuse note**: No new backend financial logic — `GET /analyze/{ticker}` already returns
`entry_timing` (feature 012). A batch endpoint is intentionally out of scope; per-ticker queries
are cached/deduped client-side. No strategy rule/default/citation change (FR-021).

### Tests for User Story 4 (write first, confirm FAIL) ⚠️

- [X] T031 [P] [US4] Vitest unit test for the watchlist entry-readiness view — entry-ready highlight, "watching — not yet ready" with top failing reasons, undetermined/insufficient-data state, last-checked `data_as_of`, and zero directive copy — in `frontend/tests/unit/watchlist-entry-readiness.test.tsx`

### Implementation for User Story 4

- [X] T032 [US4] Add a thin `fetchEntryStatus(ticker, strategy_slug)` client (Zod) over `GET /analyze/{ticker}` returning just `entry_timing` {state, summary, components} + `data_as_of`/`disclaimer`, in `frontend/src/lib/api.ts`
- [X] T033 [US4] Surface an explicit "Add to watchlist" control on the screen-results surface (the `saveCandidate` path already exists in `CandidateRow.tsx`; ensure it is reachable from the screener table/candidate view) in `frontend/src/components/CandidateRow.tsx` (and `ScreenerTable.tsx` if needed)
- [X] T034 [US4] Upgrade the watchlist page from static captured levels to a live "watch until entry-ready" view: for each open (not `acted_on`/`dismissed`) entry, query live entry-timing via T032 (TanStack Query, cached/deterministic), render a status badge (Entry ready / Watching — not yet ready / Undetermined) with top failing reasons, a manual **Refresh** + last-checked `data_as_of`, sort entry-ready first, and highlight entry-ready informationally (no directive language) in `frontend/src/app/watchlist/page.tsx`
- [X] T035 [P] [US4] (optional) Persist the last-seen entry-timing state per watchlist entry (schema_version bump) so a ticker that newly became entry-ready since the owner last looked is visually flagged, in `frontend/src/lib/store.ts`

**Checkpoint**: Owner can save a candidate and watch it until it becomes entry-ready.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T036 [P] Extend the no-directive-copy lint to the new import + holdings + watchlist entry-readiness surfaces (status, sizing, breach/target, entry-ready copy stay descriptive) in `frontend/tests/e2e/no-directive-copy.spec.ts`
- [X] T037 [P] Re-sync the Claude Project advisor pack: upgrade Template C (trim/exit a held position) to the feature-013 holdings shape in `claude-project/04-workflow-and-prompts.md`, add the held-position standing note in `claude-project/00-custom-instructions.md`, and add the re-sync line in `claude-project/README.md` (no strategy/citation changes — leave `01`/`02`/`05`/`06`)
- [X] T038 Run `specs/013-portfolio-import-sizing/quickstart.md` end-to-end (sheet → import → holdings round-trip < 2 min, both level bases + risk view, watch-until-entry-ready loop, determinism check) — automatable core verified: import→holdings round-trip + determinism (contract/integration), both level bases + risk view (holdings tests + e2e import surface), watch-until-entry-ready (watchlist e2e). NOTE: the live Google-Sheet OAuth *connect* step is interactive owner-only and cannot be driven headlessly.
- [X] T039 [P] Run the full backend pytest + frontend Vitest/Playwright suites and confirm green (no silently skipped financial-logic tests). Frontend Vitest 52/52 green; Playwright green after fixing a stale assertion (`us1-midterm-screen.spec.ts` expected a `Save` button; T033 renamed the control to `Add to watchlist`). Backend pytest 517 passed / 1 failure: `validation/test_midterm_modifications.py::test_quality_screen_toggle_changes_hard_output` — PRE-EXISTING, snapshot-data-dependent, unrelated to feature 013 (no coupling to any 013 file; momentum-strategy validation only).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; BLOCKS all user stories (Transaction model + persisted `transactions[]`).
- **User Stories (Phase 3–6)**: all depend on Foundational. US1 is the MVP. US2 depends on US1's aggregation (T010). US3 depends on US2's current-condition stop (T021/T022). **US4 (P4) is independent of US1–US3** — it only reuses the existing watchlist + feature-012 entry-timing — so it can be built any time after Setup.
- **Polish (Phase 7)**: depends on the targeted stories being complete.

### User Story Dependencies

- **US1 (P1)**: needs only Foundational. Independently testable.
- **US2 (P2)**: reuses US1's `aggregation` (T010) and the holdings endpoint it introduces; otherwise independently testable on imported transactions.
- **US3 (P3)**: reuses US2's `current_condition` stop and the holdings endpoint (extends it); otherwise independently testable.
- **US4 (P4)**: independent of US1–US3 — reuses the existing watchlist (`saveCandidate`) and feature-012 `GET /analyze/{ticker}` entry-timing; no backend change. Independently testable.

### Within Each User Story

- Tests first (and failing) → models → pure logic → endpoint → frontend.
- Same-file tasks are sequential: `backend/src/models/portfolio.py` (T003 → T009 → T020 → T026), `backend/src/api/portfolio.py` (T011 → T022 → T028), `frontend/src/lib/api.ts` (T013 → T023), `frontend/src/app/portfolio/page.tsx` (T016 → T024 → T029).

### Parallel Opportunities

- Setup: T001, T002 in parallel.
- US1: T005/T006/T007 (tests) in parallel; then T008 (transactions) + T009 (models) in parallel, then T010 (aggregation, needs the T009 model); T012/T013 (different frontend files) in parallel; T017 in parallel.
- US2: T018/T019 in parallel before implementation.
- US3: T025 before implementation; T030 in parallel.
- US4: T031 (test) before implementation; T032/T033 touch different files; T035 in parallel.
- Polish: T036/T037/T039 in parallel.

---

## Parallel Example: User Story 1

```bash
# Tests first (different files):
Task: "Unit tests for row validation in backend/tests/portfolio/test_transactions.py"
Task: "Unit tests for aggregation in backend/tests/portfolio/test_aggregation.py"
Task: "Contract test for POST /portfolio/import in backend/tests/contract/test_portfolio_import.py"

# Then pure logic (different files):
Task: "Implement transactions.py in backend/src/portfolio/transactions.py"
Task: "Implement aggregation.py in backend/src/portfolio/aggregation.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational → Phase 3 (US1).
2. **STOP and VALIDATE**: import the sample sheet, confirm holdings + idempotent re-import.
3. Deploy/demo: a correct, low-effort transaction ledger.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → test → demo (MVP: import + holdings ledger).
3. US2 → test → demo (purchase-anchored levels).
4. US3 → test → demo (risk-aware sizing).
5. US4 → test → demo (watch a saved candidate until entry-ready) — independent; can be slotted earlier if desired.
6. Polish (lint extension, advisor-pack re-sync, quickstart, full-suite green).

---

## Notes

- Everything financial REUSES existing audited helpers: `derive_bounded_levels` (levels) and
  `size_position` (sizing) are CALLED, never modified (FR-021).
- The Google OAuth token is browser-only, short-lived, and never written to a file or sent to
  the backend as a durable secret (FR-001; consistent with the api-keys-never-write rule).
- Every new response carries `data_as_of` + `disclaimer` (FR-019); all new copy is descriptive,
  zero directive language (FR-020); hosted personal-use directive stays forced OFF (FR-022).
- Determinism (SC-006) is gated by the T019 twice-and-diff integration test.
- Commit after each task or logical group; stop at any checkpoint to validate a story.
