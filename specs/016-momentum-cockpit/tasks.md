---
description: "Task list for feature 016-momentum-cockpit implementation"
---

# Tasks: Momentum Cockpit — Candidate Lifecycle Pipeline + Portfolio-Aware Fit

**Input**: Design documents from `specs/016-momentum-cockpit/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (all present)

**Tests**: Included. Constitution Principle IV (Test-First for Financial Logic) is
non-negotiable for this feature — `score_fit`, the `available_cash` sizing constraint, and
`compute_realized_pnl` (FIFO) each land golden-fixture/contract/regression tests **before**
the logic. UI-only and presentation tasks do not require test-first.

**Organization**: Grouped by user story (spec.md priorities) so each story is an independently
testable increment. Momentum is the only fully-served strategy; value/short-term stay in place
and green (reversibility invariant, verified in Polish).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 (Setup/Foundational/Polish carry no story label)
- All paths are repo-relative from `E:\screener`

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Flags + package/test scaffolding that later phases hang off of.

- [X] T001 [P] Add the Feature-016 flag block to [backend/src/lib/flags.py](../../backend/src/lib/flags.py): `pipeline_enabled()` (default **OFF**) and `fit_reward_to_risk_floor()` (default `1.5`), following the existing env-flag idiom; reuse the existing `personal_use_directive()`. No available-cash flag, no `fit_weight_*` flags.
- [X] T002 [P] Create the new backend package + test scaffolding: `backend/src/pipeline/__init__.py`, `backend/tests/pipeline/__init__.py` (empty package markers so `pipeline/fit.py` and its tests import cleanly).

**Checkpoint**: Flags resolve to today's behavior (board gated OFF); new package importable.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared frontend persisted-state groundwork consumed by US2 (available cash) and US3 (pipeline stage/ack). MUST complete before those stories.

**⚠️ CRITICAL**: No user story work that touches persisted owner state can begin until T003 is complete.

- [X] T003 Persist migration **v6 → v7** in [frontend/src/lib/store.ts](../../frontend/src/lib/store.ts): add the frontend-owned `pipeline` key (`Record<string, { manual_stage?: "staged" | "exited"; acknowledged_ready_at?: string; ready_since?: string }>` keyed by `${strategy}-${ticker}`), add `Portfolio.available_cash?: number` seeded from any dormant `cash_balance_override` (then retire the override), and add the **derived** effective `total_capital = available_cash + Σ holding market value` when cash is set (not stored). Keep the migration a no-op default otherwise so `exportSnapshot`/`normalizeStoredState` round-trip unchanged. Backend never parses `pipeline`.

**Checkpoint**: Store round-trips through sync with the new keys; existing state upgrades cleanly.

---

## Phase 3: User Story 1 — See what is ready AND fits my portfolio right now (Priority: P1) 🎯 MVP

**Goal**: A batch `POST /pipeline/board` (momentum-hardwired) that amortizes one universe snapshot + one `aggregate_exposure`, runs each watched ticker through `compute_candidate_result` → `size_position` → pure `score_fit`, and a reworked cockpit home that shows the fit-ranked list with inline sizing, cumulative-heat preview, and sector-clustering flag.

**Independent Test**: With a few momentum tickers watched, holdings imported, and capital set, open the home page and confirm the ready-and-fit list is present, ordered by fit, shows per-item sizing + binding constraint + heat headroom, and marks where cumulative heat would bind — without navigating elsewhere.

### Tests for User Story 1 (write FIRST, ensure they FAIL) ⚠️

- [X] T004 [P] [US1] Golden-fixture test for the pure fit function in `backend/tests/pipeline/test_fit.py`: given `FitFacts` inputs, assert the deterministic weighted `score`, the `fit_band` (`strong_fit`/`partial_fit`/`poor_fit`/`blocked`), `failed_facts`, and the neutral `rationale` from the fixed fact→phrase map (no directive verbs). Cover all-pass, single-fail, and all-blocked cases + stable tie-break.
- [X] T005 [P] [US1] Contract test `backend/tests/contract/test_pipeline_board.py` per [contracts/pipeline-board.md](contracts/pipeline-board.md): (1) 404 when `pipeline_enabled()` OFF; (2) 422 for a non-momentum slug; (3) 200 shape + `items[]` + top-level regime/heat + `data_as_of`/`disclaimer`; (4) per-ticker fail-soft (unknown ticker → `skipped_reason` set, `fit`/`sizing_preview` null, rest render); (5) facts wired from real `size_position` + one `aggregate_exposure`; (6) determinism; (7) no `directive_label` under hosted mode.

### Implementation for User Story 1

- [X] T006 [P] [US1] Create `backend/src/models/pipeline.py` per [data-model.md](data-model.md): `FitFacts`, `FitResult` (with `directive_label` pydantic `exclude`-if-None), `PipelineBoardItem`, `PipelineBoardResponse` (regime/heat/available_cash/`data_as_of`/`disclaimer` envelope), `PipelineBoardRequest` (`strategy_slug` default `midterm_52w_high_momentum`).
- [X] T007 [US1] Implement the pure `score_fit(facts) -> FitResult` in `backend/src/pipeline/fit.py`: **hardcoded documented constant** weights, deterministic 0–100 internal score (sort-only), band derivation, `failed_facts`, neutral fact→phrase rationale map, and the gated `directive_label` vocabulary (`consider_entry`/`hold_off`/`size_down`/`pass`) — set only when `personal_use_directive()` AND not hosted. No I/O (facts passed in). Makes T004 pass.
- [X] T008 [US1] Refactor `compute_candidate_result` in [backend/src/api/analyze.py](../../backend/src/api/analyze.py) to optionally accept **one prebuilt universe snapshot** per batch (so the board builds the snapshot once), preserving today's single-call behavior when none is passed.
- [X] T009 [US1] Implement the batch router `backend/src/api/pipeline.py` — `POST /pipeline/board`: gate on `pipeline_enabled()` (404 off), reject non-momentum slug (422), build the universe snapshot once + `aggregate_exposure` once, derive holdings server-side via `_assemble_holdings`, loop tickers through `compute_candidate_result` → `size_position` → `score_fit` with **per-ticker fail-soft** (`skipped_reason`), assemble `PipelineBoardResponse` (regime, heat ceiling/headroom, `available_cash` echo, envelope). Makes T005 pass.
- [X] T010 [US1] Register the pipeline router in [backend/src/api/app.py](../../backend/src/api/app.py) behind the existing owner-secret dependency + CORS pin.
- [X] T011 [P] [US1] Add `fetchPipelineBoard` + widened Zod schemas (`PipelineBoardResponse`/`Item`, `FitResult` with optional `directive_label`) to [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts); schemas must widen without breaking older payloads.
- [X] T012 [P] [US1] Add the pure cumulative-heat + sector-clustering helpers to `frontend/src/lib/pipeline.ts` (running heat down the fit-ranked list → index past which the heat ceiling binds; combined per-sector exposure preview).
- [X] T013 [P] [US1] Create cockpit components `frontend/src/components/cockpit/HeatGauge.tsx` and `frontend/src/components/cockpit/ReadyFitList.tsx` (fit-ranked rows with suggested shares, binding constraint, heat headroom, cumulative-heat marker, sector-clustering note).
- [X] T014 [US1] Rework [frontend/src/app/page.tsx](../../frontend/src/app/page.tsx) into the cockpit home: status strip + retained regime/data-freshness/market-events panels + `HeatGauge` + `ReadyFitList`; **graceful 404 fallback** to today's panels when the board is unavailable (no build-time env flag); remove the non-momentum strategy home cards (FR-012).
- [X] T015 [US1] Strip nav links to value/short-term/compare from [frontend/src/components/AppShell.tsx](../../frontend/src/components/AppShell.tsx) so the product surface is momentum-only (code/registry/tests untouched — reversibility verified in Polish).
- [X] T016 [US1] Playwright e2e `frontend/tests/e2e/` covering the reworked home: ready-and-fit list present + fit-ordered + per-item sizing/heat, cumulative-heat marker, and the **no-directive language lint** + `data_as_of`/`disclaimer` presence on the new home.

**Checkpoint**: US1 fully functional — cockpit answers "what is ready AND fits" from the home page alone (SC-001, SC-002).

---

## Phase 4: User Story 2 — Enter available cash and have sizing respect it (Priority: P1)

**Goal**: Owner enters available cash; total capital derives = cash + holdings MV; `size_position` gains an optional `available_cash` hard limit reported as `binding_constraint = "available_cash"`. Absent ⇒ byte-identical.

**Independent Test**: On the portfolio page, enter available cash → total capital derives as cash + holdings MV; set cash low → a candidate's suggested size is capped by cash and labeled cash-limited; set cash to zero → size zero, reason available_cash.

### Tests for User Story 2 (write FIRST, ensure they FAIL) ⚠️

- [X] T017 [P] [US2] Test `backend/tests/portfolio/test_sizing_available_cash.py` per [contracts/sizing-available-cash.md](contracts/sizing-available-cash.md): (1) absent `available_cash` ⇒ **byte-identical** to today's `SizingResponse` over existing cases; (2) binds — `shares × entry ≤ available_cash`, `binding_constraint == "available_cash"`; (3) zero cash ⇒ `suggested_shares == 0` + `available_cash` reason; (4) does not override a tighter risk/position/sector/heat constraint; (5) binding-constraint vocabulary test extended with `available_cash`.

### Implementation for User Story 2

- [X] T018 [US2] Extend [backend/src/models/portfolio.py](../../backend/src/models/portfolio.py): add `SizingRequest.available_cash: Decimal | None = None`, add `PortfolioHoldingsRequest.available_cash: Decimal | None = None`, and document `"available_cash"` in the `binding_constraint` vocabulary (no field-shape change).
- [X] T019 [US2] Implement the cash cap in `size_position` at [backend/src/portfolio/sizing.py](../../backend/src/portfolio/sizing.py): when `available_cash` present, cap `suggested_shares` so `shares × entry ≤ available_cash`, and set `binding_constraint = "available_cash"` **only when cash is the tightest** limit. Makes T017 pass.
- [X] T020 [US2] Thread `available_cash` through the sizing + holdings endpoints ([backend/src/api/sizing.py](../../backend/src/api/sizing.py) and per-holding sizing in [backend/src/api/portfolio.py](../../backend/src/api/portfolio.py)) so both single-sizing and portfolio-page recommended sizes respect cash.
- [X] T021 [P] [US2] Widen the sizing/holdings Zod schemas in [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts) for the optional `available_cash` request field and the `"available_cash"` binding-constraint value.
- [X] T022 [US2] Cash-first inputs on [frontend/src/app/portfolio/page.tsx](../../frontend/src/app/portfolio/page.tsx): an **Available cash** field → **derived Total capital** display (cash + holdings MV); thread `available_cash` into holdings/sizing requests; graceful degradation when holdings quotes are unavailable. Reads/writes `Portfolio.available_cash` from the T003 store.

**Checkpoint**: US2 works independently on the portfolio page (SC-003, SC-004); board (US1) also honors cash when set.

---

## Phase 5: User Story 3 — Readiness alerts + stage visibility (Priority: P2)

**Goal**: "Newly ready" badges + "ready for N days" counter, a holdings-needing-attention list, and a cross-surface `PipelineStageBadge` (derived-first stage).

**Independent Test**: Watch a candidate, cause readiness to change, reopen the cockpit → "newly ready" badge + day counter appear and clear on acknowledge; a holding whose level status changes appears in a "needs attention" list.

### Tests for User Story 3 ⚠️

- [X] T023 [P] [US3] Vitest unit test `frontend/tests/unit/` for the pure `derivePipelineStage` selector: assert precedence **holdings-derived (owned/managing) > exited > ready > staged > watching**, incl. the `ready`↔`owned` stale-board no-flicker case and `managing` escalation (level `status != "holding"` or `risk.over_risk`).

### Implementation for User Story 3

- [X] T024 [US3] Implement the pure `derivePipelineStage` selector in `frontend/src/lib/pipeline.ts` (precedence from [data-model.md](data-model.md); manual `staged`/`exited` only, derived stages always outrank). Makes T023 pass.
- [X] T025 [P] [US3] Create cockpit components `frontend/src/components/cockpit/PipelineStageBadge.tsx`, `WatchingList.tsx`, `AttentionList.tsx`, and `TransitionAlert.tsx` ("newly ready" + "ready for N days", clears on acknowledge; holdings-attention rows link into the portfolio).
- [X] T026 [US3] Render `PipelineStageBadge` wherever a ticker appears: [frontend/src/components/CandidateRow.tsx](../../frontend/src/components/CandidateRow.tsx) (screen results / watchlist / candidate detail reuse) — FR-011.
- [X] T027 [US3] Include the `pipeline` key (manual stage + ready acknowledgements) in the sync payload with a change-detection guard in [frontend/src/components/PortfolioSync.tsx](../../frontend/src/components/PortfolioSync.tsx) (backend stays opaque, via existing `PUT /portfolio/state`).
- [X] T028 [US3] Wire the alerts + attention sections into the cockpit home [frontend/src/app/page.tsx](../../frontend/src/app/page.tsx): `WatchingList`, `AttentionList`, `TransitionAlert`, with acknowledge-writes-back to the `pipeline` store; empty sections render as onboarding prompts (FR-014).

**Checkpoint**: US3 adds daily-driver alerts + stage visibility on top of the US1 cockpit.

---

## Phase 6: User Story 4 — Record buy/sell transactions in-app + win/loss (Priority: P2)

**Goal**: `POST /portfolio/transactions` + `DELETE /portfolio/transactions/{id}` reuse the 013 import validator + `_assemble_holdings`; a new pure `portfolio/pnl.py` computes FIFO realized P&L (+ win rate) and unrealized mark-to-market; additive/optional ⇒ byte-identical when no closed lots.

**Independent Test**: Record a buy then a partial sell in-app → holdings aggregate identically to an equivalent import; realized P&L (with win/loss) + unrealized P&L figures appear and are correct.

### Tests for User Story 4 (write FIRST, ensure they FAIL) ⚠️

- [X] T029 [P] [US4] Golden-fixture test `backend/tests/portfolio/test_pnl.py` per [contracts/portfolio-pnl.md](contracts/portfolio-pnl.md): (1) FIFO multi-lot + partial sell matches oldest lots, hand-computed `realized_pnl`/`outcome`/`win_rate`; (2) fees subtracted on matched shares; (3) win/loss/flat classification around break-even; (4) buy-only ⇒ `realized_pnl` None/0, **byte-identical** totals; (5) missing-quote unrealized degradation flagged, others unaffected; (6) informational isolation (no sizing/level/board change).
- [X] T030 [P] [US4] Contract test `backend/tests/contract/test_portfolio_transactions.py` per [contracts/portfolio-transactions.md](contracts/portfolio-transactions.md): (1) validation reuse (invalid manual row rejected like an invalid import row); (2) aggregation parity with import — SC-010; (3) retention of raw transactions across a state round-trip; (4) delete re-aggregates, unknown id → 404; (5) envelope; (6) `POST /portfolio/import` still works (regression).

### Implementation for User Story 4

- [X] T031 [P] [US4] Create pure `backend/src/portfolio/pnl.py`: `compute_realized_pnl(transactions) -> RealizedPnl` (FIFO per ticker → `RealizedTrade` round-trips with `proceeds − cost_basis − fees`, `outcome`, `holding_days`; aggregates + `win_rate`) and unrealized mark-to-market helper (graceful missing-quote degradation). Makes T029 pass.
- [X] T032 [US4] Extend [backend/src/models/portfolio.py](../../backend/src/models/portfolio.py): add `PortfolioTotals` optional `realized_pnl`/`unrealized_pnl`/`total_pnl`/`win_rate`/`closed_trade_count`/`winning_trade_count` (None/0 ⇒ byte-identical) and the new `RealizedTrade` model.
- [X] T033 [US4] Add `POST /portfolio/transactions` + `DELETE /portfolio/transactions/{id}` to [backend/src/api/portfolio.py](../../backend/src/api/portfolio.py) reusing the import validator + `_assemble_holdings`, retaining raw transactions in the owner blob, returning `ImportResult`-style summaries (404 on unknown delete id). Makes T030 pass.
- [X] T034 [US4] Surface P&L in the holdings/totals response in [backend/src/api/portfolio.py](../../backend/src/api/portfolio.py) by calling `compute_realized_pnl` + unrealized helper (informational only; never feeds sizing/levels/board).
- [X] T035 [P] [US4] Add transaction mutations (`recordTransactions`, `deleteTransaction`) + P&L Zod schemas to [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts).
- [X] T036 [US4] Portfolio page [frontend/src/app/portfolio/page.tsx](../../frontend/src/app/portfolio/page.tsx): record-transaction form + editable transaction list (correct/delete), a P&L summary card (realized/unrealized/total + win rate, neutral labels), and a realized-trades table; keep the existing Sheet import as the secondary bulk path (FR-022).

**Checkpoint**: US4 delivers in-app transaction entry + win/loss (SC-010, SC-011); byte-identical when no closed lots.

---

## Phase 7: User Story 5 — Optional decision framing for personal use (Priority: P3)

**Goal**: An optional `directive_label` on fit results, present **only** when `personal_use_directive()` is on AND not hosted; neutral-only otherwise. (Vocabulary/gating built in T007; this phase verifies + renders it.)

**Independent Test**: Toggle personal-use directive framing on/off → the optional label appears only when on, and never in hosted mode.

### Tests for User Story 5 ⚠️

- [X] T037 [P] [US5] Test in `backend/tests/contract/test_pipeline_board.py` (or a focused `test_fit_directive.py`): `directive_label` present when `personal_use_directive()` on and not hosted; **absent** when the flag is off; **never present** under hosted mode regardless of the flag (leakage-detectable).

### Implementation for User Story 5

- [X] T038 [US5] Render the optional `directive_label` alongside the neutral band in `frontend/src/components/cockpit/ReadyFitList.tsx` **only** when present in the payload (schema already optional from T011); no directive verbs in the neutral/hosted path.

**Checkpoint**: US5 personal-use framing works and is provably absent on the default/hosted path (SC-006).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Reversibility invariant, byte-identical/off-path guarantees, and full-suite validation.

- [X] T039 [P] Reversibility regression test `backend/tests/strategies/` (or `backend/tests/validation/`) asserting the value + short-term strategy registry entries load and their existing suites remain green despite UI removal (SC-009, D10 invariant). → `backend/tests/strategies/test_reversibility_registry.py`.
- [X] T040 [P] Flag-off byte-identical assertion: with `pipeline_enabled()` OFF, `POST /pipeline/board` 404s and existing endpoint outputs are unchanged (SC-005) — add to `backend/tests/contract/` or `backend/tests/api/`. → `backend/tests/contract/test_pipeline_flag_off.py`.
- [X] T041 [P] Update [specs/016-momentum-cockpit/quickstart.md](quickstart.md) manual-verification steps if any path drifted during implementation; confirm the deploy notes (baked snapshot + BFF proxy + owner-secret + flags) still hold.
- [X] T042 Run the full backend (pytest from repo root) + frontend (Vitest + Playwright) suites; confirm 0 silently-skipped financial-logic tests and green baseline before commit. (Hardened the brittle `test_sector_relative_cap_changes_hard_output`; scoped the no-directive lint to exempt the factual in-app transaction-record buy/sell labels.)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2 / T003)**: depends on Setup; **blocks** US2 and US3 (persisted-state consumers). US1 and US4 backend work can begin without it.
- **User Stories (Phases 3–7)**: after their prerequisites; independently testable.
- **Polish (Phase 8)**: after all targeted stories.

### User Story Dependencies

- **US1 (P1)**: after Setup. Independent MVP. (T003 not strictly required for the backend board; the cockpit home consumes US1 output.)
- **US2 (P1)**: after Setup + T003. Independent on the portfolio page; enriches US1 when cash is set.
- **US3 (P2)**: after Setup + T003. Layers onto the US1 cockpit but testable via its own selector/components.
- **US4 (P2)**: after Setup. Backend + portfolio-page only; independent of US1/US3.
- **US5 (P3)**: after US1 (T007 built the gating; T011 the optional schema).

### Within Each User Story

- Tests (financial logic) written and FAILING before implementation: T004/T005 → T006–T010; T017 → T018–T020; T029/T030 → T031–T034; T037 → T038.
- Models before services before endpoints; core before integration; UI after its API/schema.

### Parallel Opportunities

- Setup: T001 ∥ T002.
- US1 tests: T004 ∥ T005. US1 impl: T006, T011, T012, T013 are parallelizable; T007–T010 are sequential backend-core.
- US2: T017 first; T021 ∥ backend T018–T020.
- US4: T029 ∥ T030; T031 ∥ T035.
- Across stories once T003 lands: US1, US2, US4 can proceed on separate files in parallel.
- Polish: T039 ∥ T040 ∥ T041.

---

## Parallel Example: User Story 1

```bash
# Tests first (must FAIL):
Task: "Golden-fixture fit test in backend/tests/pipeline/test_fit.py"
Task: "Board contract test in backend/tests/contract/test_pipeline_board.py"

# Then parallelizable implementation:
Task: "models/pipeline.py entities in backend/src/models/pipeline.py"
Task: "fetchPipelineBoard + Zod in frontend/src/lib/api.ts"
Task: "cumulative-heat helper in frontend/src/lib/pipeline.ts"
Task: "HeatGauge + ReadyFitList in frontend/src/components/cockpit/"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → 2. US1 tests (T004–T005, failing) → 3. US1 impl (T006–T016) →
4. **STOP & VALIDATE**: cockpit answers ready-AND-fit from home alone → 5. demo.

### Incremental Delivery

Setup → **US1 (MVP)** → US2 (cash-first sizing) → US3 (alerts/stages) → US4 (transactions + P&L) → US5 (directive framing) → Polish. Each story is byte-identical-when-off / additive, so nothing regresses prior stories.

### Guardrails held throughout

- `pipeline_enabled()` default OFF ⇒ board 404s, home degrades (SC-005).
- Determinism: same snapshot + same portfolio ⇒ identical board (SC-007); ties break on a stable key.
- Neutral/hosted path zero-directive (SC-006); `directive_label` a separate gated field, never present hosted.
- `data_as_of` + `disclaimer` on every new response (FR-018).
- Value/short-term code/registry/tests stay green — reversibility (SC-009, T039).

---

## Notes

- [P] = different files, no incomplete-task dependency.
- Verify each financial-logic test FAILS before implementing.
- Commit after each task or logical group; the working tree must never serve a partial board.
- No new external data source, no new auth surface, no build-time env flag.
