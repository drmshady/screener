---
description: "Task list for feature 019 — Portfolio Position Cards & Transaction Separation"
---

# Tasks: Portfolio Position Cards & Transaction Separation

**Input**: Design documents from `/specs/019-portfolio-position-cards/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md, contracts/

**Tests**: Included. The instruction mapper is financial logic and requires test-first golden-fixture + determinism tests (Constitution IV, plan.md Constitution Check IV). Frontend render/degrade (Vitest) and no-directive/page-split (Playwright) gates are required by the spec (FR-008, FR-012) and quickstart §2/§4.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- All file paths are repo-relative from `E:\screener\`

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`
- This feature adds **no new endpoint, store, or entity** — one new pure backend module + one additive response field, plus a frontend page split and two new components.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the reused pipelines this feature synthesizes over are present and green before building on them.

- [X] T001 Verify feature branch `019-portfolio-position-cards` is checked out and backend + frontend suites are green on a clean checkout (`cd backend; pytest -q` and `cd frontend; npm run test`), establishing the byte-identical baseline this presentation-only feature must preserve (FR-013). **Done (Phase 1).** Branch confirmed. Backend baseline: **707 passed / 2 skipped / 8 failed + 1 collection error**; all 9 failures trace to a single root cause — the baked local snapshot `data_as_of` is ~1 month stale (`2026-06-18` vs `2026-07-18`) so `run_strategy("midterm_52w_high_momentum")` returns 0 candidates (empty-screen `IndexError` in `tests/contract/test_openapi.py::_live_candidate_ticker` at collection; stale-window assertions in `test_perf`, `test_midterm_backtest`, `test_midterm_gate_mode`, `test_midterm_modifications` ×2, `test_midterm_reference_tickers` ×2, `test_surface_sweep_api`). NOT a code bug and NOT introduced by 019 — production data advances via the GitHub Actions `daily-refresh.yml` cron, not the local tree. Accepted as the known-stale baseline; presentation-only 019 work does not depend on fresh data.
- [X] T002 [P] Confirm the reused backend building blocks exist and are importable: `backend/src/portfolio/aggregation.py` (net-quantity open/closed), `backend/src/portfolio/holding_levels.py`, `backend/src/portfolio/holding_risk.py`, `backend/src/portfolio/pnl.py` (`compute_realized_pnl`), and the `_assemble_holdings` path in `backend/src/api/portfolio.py`. **Done (Phase 1).** All present/importable. Mapper field names captured: `LevelBlock.status ∈ {holding, stop_breached, target_reached, gains_protected, insufficient_data}`, `LevelBlock.levels_state ∈ {ok, insufficient_data}`, `LevelBlock.distance_to_stop_pct: float | None`; `PortfolioTotals.heat_headroom_pct: float` (and `heat_ceiling_pct`). `compute_realized_pnl(transactions) -> RealizedPnl`.
- [X] T003 [P] Confirm the reused frontend components exist and their props: `frontend/src/components/ImportTransactions.tsx`, `frontend/src/components/SentimentReport.tsx`, `frontend/src/components/EventsBadge.tsx`, `frontend/src/components/cockpit/PipelineStageBadge.tsx`, and the current transaction UI in `frontend/src/app/portfolio/page.tsx`; note the `syncFromServer`/`loadHoldings` data flow in `frontend/src/lib/api.ts`. **Done (Phase 1).** All present. Data flow: `frontend/src/app/portfolio/page.tsx` → `syncFromServer` calls `fetchHoldings`/`recordTransactions`/`deleteTransaction` in `frontend/src/lib/api.ts`; holdings validated by `PortfolioHoldingsResponseSchema`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The single-owner directive carve-out predicate and the additive response wiring are prerequisites shared by US1 (verb display) and the frontend schema. Must complete before US1 backend behavior is meaningful.

**⚠️ CRITICAL**: No user story work that depends on the `instruction` field or `directive_enabled` can begin until this phase is complete.

- [X] T004 Add a shared single-owner directive carve-out predicate in `backend/src/lib/flags.py` (personal-use flag ON **and** owner-secret set **and** not multi-user), factored so both the feature-018 `brief_directive_enabled()` logic and the new card gate call one private predicate; do **not** reuse the hosted-force-OFF `personal_use_directive()` (research Decision 3, FR-008). Preserve existing `brief_directive_enabled()` behavior byte-for-byte. **Done.** Extracted the inline logic into private `_single_owner_directive_carveout()` (unchanged three-check body: not `_brief_multi_user()`, `hosting.owner_secret()` set, `SCREENER_PERSONAL_USE_DIRECTIVE` truthy). `brief_directive_enabled()` now delegates to it (byte-for-byte behavior — pure extract-method), and new public `card_directive_enabled()` gates on the same predicate. Verified: both return `False` by default.
- [X] T005 Add the additive, optional `InstructionBlock` model and the top-level `directive_enabled` boolean to the `/portfolio/holdings` response model in `backend/src/models/portfolio.py` per data-model.md (`status_label` always present; `directive` `hold|trim|sell|null`; `rationale`; `inputs` echo of deciding facts). Fields MUST be optional/back-compatible so existing consumers stay byte-identical when absent. **Done.** Added `InstructionInputs` (`level_status`, `distance_to_stop_pct?`, `heat_headroom_pct?`, `stage?`) and `InstructionBlock` (`status_label` required; `directive: Literal["hold","trim","sell"] | None = None`; `rationale`; `inputs`). Wired `PortfolioHolding.instruction: InstructionBlock | None = None` and `PortfolioHoldingsResponse.directive_enabled: bool = False`. Verified: a response built without the new fields validates and dumps `directive_enabled=false`, `instruction` omittable ⇒ back-compatible.

**Checkpoint**: Carve-out predicate + response schema ready — US1 backend derivation can now be wired in.

---

## Phase 3: User Story 1 - Position card with status, levels, news, and a call (Priority: P1) 🎯 MVP

**Goal**: For every open holding, the Portfolio page shows one card with status/stage, stop-loss + target, current price + unrealized P&L, recent news/events (source + as-of or explicit "nothing new"), auto-loaded AI sentiment, and a Hold/Trim/Sell call (or neutral status when the carve-out is off).

**Independent Test**: With ≥1 open holding, load `/portfolio` and verify a card renders showing status, stop-loss, target, recent news/events (or "nothing new"), and one of Hold/Trim/Sell (verb when carve-out on; neutral status otherwise).

### Tests for User Story 1 (write FIRST, ensure they FAIL before implementation) ⚠️

- [X] T006 [P] [US1] Write golden-fixture unit tests for `derive_instruction` in `backend/tests/portfolio/test_instruction.py` covering all precedence branches: **sell** (`current_condition.status == "stop_breached"`), **trim** (`|distance_to_stop_pct| <= 0.03` near-stop OR `heat_headroom_pct <= 0`), **hold** (healthy / `target_reached` / `gains_protected`), and **levels unavailable** (`levels_state == "insufficient_data"` → no verb, `status_label` set) per research Decision 2. Must be RED before T009. **Done.** 11 golden cases incl. the 3% near-stop boundary, levels-unavailable-beats-heat precedence, and neutral-when-disabled. Confirmed RED (ModuleNotFoundError) before T009, GREEN after.
- [X] T007 [P] [US1] Write a determinism test in `backend/tests/portfolio/test_instruction_determinism.py` asserting identical inputs → identical `InstructionBlock`, and that the AI sentiment score is **not** an accepted/consulted input (FR-007). Must be RED before T009. **Done.** Asserts identical inputs → identical `model_dump()`, verb independence from stage, and that passing `sentiment_score=` raises `TypeError` (structural FR-007 enforcement — the mapper signature cannot accept sentiment).
- [X] T008 [P] [US1] Write contract tests in `backend/tests/api/test_portfolio_holdings_instruction.py`: (a) neutral default with carve-out OFF → per-holding `directive` is null/omitted, `status_label` present, `directive_enabled=false`; (b) carve-out ON → `directive` verb present and `directive_enabled=true`; (c) response is additive/back-compatible (existing fields unchanged). Must be RED before T010. **Done.** Stubs `_assemble_holdings` + monkeypatches `portfolio_api.card_directive_enabled`; all three assertions covered.

### Implementation for User Story 1 (backend)

- [X] T009 [US1] Implement the pure `derive_instruction(facts) -> InstructionBlock` in `backend/src/portfolio/instruction.py` using existing constants only (near-level 0.03, `portfolio_heat_ceiling()`), no new indicator/threshold (FR-007, FR-013); precedence Sell → Trim → Hold → levels-unavailable. Make T006/T007 GREEN. **Done.** Keyword-only pure function; module constant `NEAR_LEVEL_PCT = 0.03` (reuses the existing frontend threshold, not a new indicator). Levels-unavailable checked first as a guard so an insufficient-levels holding never gets a verb even under a heat breach. Verb gated on `directive_enabled`; `status_label` + `rationale` always present.
- [X] T010 [US1] Wire the instruction into the `_assemble_holdings` path in `backend/src/api/portfolio.py`: attach per-holding `instruction` (built from that holding's level status, `distance_to_stop_pct`, `totals.heat_headroom_pct`, and stage) and set top-level `directive_enabled` from the T004 carve-out predicate; omit/null the verb when the carve-out is off. Make T008 GREEN. No new endpoint (research Decision 1). **Done.** Added `_attach_instructions(holdings, totals, directive_enabled)` called from the `/holdings` endpoint (keeps `_assemble_holdings` byte-identical for the advisor-prompt routes that share it, FR-013); `directive_enabled = card_directive_enabled()` set on the response. Stage passed as `None` (browser-local; refined frontend-side). 204 backend portfolio+api tests green.
- [X] T011 [US1] Extend the holdings response schema in `frontend/src/lib/api.ts` with the optional `instruction` (InstructionBlock) and top-level `directive_enabled`, tolerant of their absence (back-compat with older responses). **Done.** Added `InstructionInputsSchema`/`InstructionBlockSchema` (+ `InstructionBlock` type), `PortfolioHoldingSchema.instruction` (nullable/optional), and `PortfolioHoldingsResponseSchema.directive_enabled` (`optional().default(false)`).
- [X] T012 [P] [US1] Create `frontend/src/components/PositionCard.tsx` rendering: ticker/company, quantity + cost basis, current price + unrealized P&L, status/stage (`cockpit/PipelineStageBadge` + level/breach status), current stop (`current_condition`) + target and trailing stop, recent news/events via `EventsBadge` with source + as-of (explicit "nothing new" when empty), auto-loaded sentiment via `SentimentReport` (origin `"holding"`, lazy/background per SC-005), and the instruction — Hold/Trim/Sell verb when `directive_enabled`, else the neutral `status_label` (FR-004/005/006/008). Card MUST still render with an explicit "Levels unavailable" state when levels are insufficient (edge case), and carry `data_as_of`/staleness + disclaimer (FR-012). **Done.** Verb chip (sell=danger/trim=warning/hold=success) only when `directiveEnabled && instruction.directive`, else neutral `status_label` chip. Levels-unavailable renders `data-testid="levels-unavailable"`; empty news → `events-nothing-new`; sentiment embedded via `SentimentReport initialSelections=[{ticker, origin:'holding'}]`; footer carries `AsOfBadge` + disclaimer. `EventsBadge` renders only when a `candidate` prop is supplied (holdings response has no events facts) — graceful "Nothing new" otherwise.
- [X] T013 [P] [US1] Write Vitest render + degrade tests in `frontend/tests/PositionCard.test.tsx`: card renders levels/status/instruction without waiting on sentiment/news (SC-005); "Levels unavailable" path renders the card; empty news → "nothing new"; capped/absent sentiment → template narrative not blank/error; `directive_enabled=false` → neutral status, no verb (FR-008). **Done** at `frontend/tests/unit/PositionCard.test.tsx` (repo vitest include glob is `tests/unit/**`). 6 tests; `SentimentReport` stubbed so the shell is synchronously testable (SC-005). Full suite: 85 passed / 17 files.
- [X] T014 [US1] Render the `PositionCard` grid on `frontend/src/app/portfolio/page.tsx` for open holdings only (see US3 for the `net_quantity > 0` filter), preserving the existing `data_as_of` + disclaimer shell. **Done.** New "Positions" `md:grid-cols-2` section fed by an `openPositionCards` memo (open holdings mapped to fetched `importedDetails`); captured `directive_enabled` + `disclaimer` from the `/holdings` response into new state (reset on empty). Existing ledger/forms left in place (US2/T017 relocates them). `tsc --noEmit` clean for all 019 files (remaining tsc errors are pre-existing unrelated fixture drift).

**Checkpoint**: US1 fully functional — cards render with status, levels, news, sentiment, and a call; testable independently of the page split and summary.

---

## Phase 4: User Story 2 - Transactions on their own page (Priority: P1)

**Goal**: All buy/sell recording, Sheet import, delete controls, and the transaction ledger live on a dedicated `/transactions` page; the Portfolio page has none of them, only a link.

**Independent Test**: Navigate to `/transactions` and confirm the full chronological ledger + add/import/delete controls; confirm `/portfolio` has no transaction-entry UI, only a link to `/transactions`.

### Tests for User Story 2 ⚠️

- [X] T015 [P] [US2] Write a Playwright test in `frontend/tests/e2e/transactions-split.spec.ts`: transaction record/import/delete controls and the ledger are **present** on `/transactions` and **absent** from `/portfolio`; `/portfolio` exposes a one-click link to `/transactions` (FR-001/FR-002, SC-003). RED before T016–T018. **Done.** Three tests: (a) `/transactions` shows the Record-a-Transaction form + Import-from-Google-Sheet heading + a seeded-transaction ledger row with a Delete control; (b) `/portfolio` has a `/transactions` link and **none** of the transaction headings/controls; (c) the Primary nav exposes a Transactions link. Seeds a NVDA buy via `screener-storage` localStorage init + `isolatePortfolioState`. RED by construction (route absent + controls still on `/portfolio` before T016/T017). Not executed against live servers here (heavy dev+backend spin-up); the ledger/controls asserted are client-side from the store, and full e2e is covered by T026.

### Implementation for User Story 2

- [X] T016 [US2] Create `frontend/src/app/transactions/page.tsx` and **relocate** (not redesign) the existing transaction UI from `frontend/src/app/portfolio/page.tsx`: `ImportTransactions`, the "Record a Transaction" form, the ledger table (chronological, including rows for now-closed positions), the realized-trades detail, and per-holding Remove controls — reusing the existing `syncFromServer`/`loadHoldings` write path unchanged (research Decision 4). **Done.** New `/transactions` page carries `ImportTransactions`, the Record form + chronological ledger + Delete, the Imported-Holdings ledger table (net shares incl. closed, levels/risk summaries, per-holding Remove, sentiment-run + `CopyHoldingAdvisorPrompt`), the alerts + totals + realized-trades detail, and the holdings sentiment report — all moved verbatim. Reads the same server-owned `transactions` list via its own `syncFromServer`/`loadHoldings` so returning to `/portfolio` reflects changes (US2 AC3). Extracted `computeImportedHoldings`/`ImportedHolding` into shared `frontend/src/lib/importedHoldings.ts` (used by both pages; behavior identical).
- [X] T017 [US2] Remove all transaction-entry/ledger/import/delete UI from `frontend/src/app/portfolio/page.tsx` and add a one-click link to `/transactions` (FR-002). **Done.** Stripped `ImportTransactions`, the Record form + ledger, the whole Imported-Holdings section (table/Remove/totals/pnl/realized/alerts/sentiment-run), plus the now-unused imports/state/handlers (`syncFromServer`, `handleImported`, `handleRecordTransaction`, `handleDeleteTransaction`, `handleRemoveImportedHolding`, `holdingAlerts`, `realizedTrades`, txn form state, level/risk render helpers). Kept card review (US1) + the manual-holdings management + capital settings + sector exposure, and `loadHoldings`/`importedTotals`/`directiveEnabled`/`importedDisclaimer` (feed the cards + cash-first capital math). Added a "Go to Transactions" link section. tsc clean for 019 files; eslint 0 errors (one pre-existing carried-over `useCallback` deps warning).
- [X] T018 [US2] Add a Transactions nav link in `frontend/src/components/AppShell.tsx`. **Done.** Inserted `{ href: '/transactions', label: 'Transactions' }` in `NAV_LINKS` between Portfolio and Settings.

**Checkpoint**: US1 + US2 both work — cards on `/portfolio`, all transaction bookkeeping on `/transactions`; adding/deleting a transaction there reflects on `/portfolio` immediately (US2 AC3, via the shared server-owned transaction list).

---

## Phase 5: User Story 3 - Closed positions leave the Portfolio page (Priority: P2)

**Goal**: A holding at zero net shares shows no card on `/portfolio`; its transactions remain on `/transactions`; a later repurchase makes a new card appear.

**Independent Test**: Sell 100% of a holding → its card disappears from `/portfolio`; its buy/sell rows remain on `/transactions`; repurchase → new open-position card.

### Tests for User Story 3 ⚠️

- [X] T019 [P] [US3] Write a Vitest test in `frontend/tests/portfolio-open-filter.test.tsx` asserting the Portfolio card list includes only holdings with `net_quantity > 0` and excludes zero-net holdings; a repurchase (net back above 0) reintroduces a card (FR-003/FR-011, SC-002). RED before T020. **Done.** Placed at `frontend/tests/unit/portfolio-open-filter.test.tsx` (the actual Vitest include glob is `tests/unit/**/*.test.{ts,tsx}` — the literal `tests/` path would not be collected). Tests the derivation seam the page uses — `computeImportedHoldings(txns).filter(h => h.status === 'open')`: (a) mixed set yields only the net-positive tickers, (b) a fully-sold holding drops off, (c) a repurchase reintroduces the card. GREEN on the existing filter (see T020).

### Implementation for User Story 3

- [X] T020 [US3] Apply the open-position filter (`net_quantity > 0` only) to the card list in `frontend/src/app/portfolio/page.tsx`, relying on the existing aggregation's net-quantity output — no backend change (data-model.md, research Decision 4). Make T019 GREEN. **Done — no code change required.** The `openPositionCards` memo already filters `h.status === 'open'` (i.e. `net_quantity > 0`, from `computeImportedHoldings`), introduced in T014 as an explicit forward-reference to US3 ("see US3 for the `net_quantity > 0` filter"). Verified the predicate matches the requirement exactly; T019 passes against it. Full Vitest suite 88/88 green.

**Checkpoint**: US1–US3 independently functional — closed positions drop off Portfolio while staying auditable on Transactions.

---

## Phase 6: User Story 4 - Realized win/loss summary (Priority: P2)

**Goal**: The Portfolio page shows a scoreboard of closed positions — count won/lost, win rate %, total realized P&L — with an explicit empty state.

**Independent Test**: With ≥1 fully closed position, verify winner/loser counts, win rate, and total realized P&L, mathematically consistent with the closed trades; with none, verify the "no realized history yet" state.

### Tests for User Story 4 ⚠️

- [X] T021 [P] [US4] Write Vitest tests in `frontend/tests/RealizedSummary.test.tsx`: populated state renders count won, count lost, win rate %, and total realized P&L from `totals` (`winning_trade_count`, `closed_trade_count`, `win_rate`, `realized_pnl`) consistent with the underlying trades (SC-004); zero-closed state renders "No realized history yet" (FR-009). RED before T022. **Done.** Placed at `frontend/tests/unit/RealizedSummary.test.tsx` (Vitest include glob is `tests/unit/**`). 3 tests: (a) populated — won `winning_trade_count`, lost = `closed − won`, win rate = `win_rate*100`%, total = `formatMoney(realized_pnl)`, + disclaimer present; (b) zero-closed → `realized-empty` "No realized history yet" and no scoreboard figures; (c) `totals=null` → empty state. Confirmed RED (module-not-found) before T022; fixed one assertion (shared `formatMoney` renders `$1234.50`, no thousands separator).

### Implementation for User Story 4

- [X] T022 [P] [US4] Create `frontend/src/components/RealizedSummary.tsx` reading the existing `PortfolioTotals` realized fields (no new computation; data-model.md) with the explicit empty state, carrying `data_as_of` + disclaimer (FR-012). Make T021 GREEN. **Done.** Reads `closed_trade_count`/`winning_trade_count` (lost = closed − won), `win_rate`, `realized_pnl` directly — no computation. `closed > 0` → won/lost/win-rate/total scoreboard; else the `realized-empty` state (FR-009). Footer carries `AsOfBadge` + disclaimer (FR-012); zero directive language. Prop typed to a loose `RealizedTotalsLike` (all-optional realized fields) so both the full `PortfolioTotals` and the page's inline totals shape are assignable without coupling. 3/3 GREEN.
- [X] T023 [US4] Render `RealizedSummary` on `frontend/src/app/portfolio/page.tsx` alongside the card grid. **Done.** Rendered between the Positions card grid and the Transactions link, fed by `importedTotals` + `importedAsOf` + `importedDisclaimer` (falls back to `COPY.GLOBAL.DISCLAIMER`). tsc clean for 019 files; full Vitest 91/91 green.

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Cross-story disclosure, determinism, and no-regression gates.

- [X] T024 [P] Add a Playwright no-directive lint in `frontend/tests/e2e/portfolio-disclosure.spec.ts`: on `/portfolio` with `directive_enabled=false`, no directive verbs (Buy/Sell/Trim/Hold) appear and `data_as_of` + disclaimer are present on every card and the summary (FR-008/FR-012). **Done.** Three tests seed one open NVDA buy in `screener-storage` + mock `/portfolio/holdings` (carve-out OFF, `directive_enabled=false`, but the payload deliberately carries `instruction.directive:"sell"` to prove the **frontend gate** — not the payload — suppresses the verb): (a) the verb chip `instruction-directive` has **count 0** while the neutral `instruction-status` reads "Holding" (FR-008, section never dropped); (b) every `position-card` carries `card-disclaimer` (the response disclaimer) + an `AsOfBadge` ("Data as of:") in its footer (FR-012); (c) the `realized-summary` renders won/lost/win-rate from totals (2 closed, 1 won ⇒ 1 lost, 50%) + `realized-disclaimer` (FR-009/FR-012). Fully route-mocked (no live-data dependency). tsc clean.
- [ ] T025 [P] Run the full backend suite including momentum **and** value tests to confirm byte-identical compute paths (FR-013): `cd backend; pytest -q`; confirm no indicator/gate/sizing/backtest baseline changed.
- [ ] T026 Run frontend `npm run lint` and `npm run test`, then the quickstart.md §3 end-to-end manual checks (SC-001–SC-005) and §4 Playwright gates (`npm run test:e2e -- portfolio transactions`).
- [X] T027 [P] Update `CLAUDE.md` "Active feature" pointer to 019 and confirm `specs/019-portfolio-position-cards/plan.md` references are current. **Done.** Added a `## Active feature: 019-portfolio-position-cards` section (presentation-only; US1–US4; carve-out gate; FR-007/008/012/013 preserved) and demoted 018 to `## Prior feature`. The SPECKIT plan-pointer block already named 019 active; plan.md path confirmed current.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS** the US1 backend verb wiring and the frontend schema extension.
- **User Stories (Phase 3–6)**: All depend on Foundational.
  - US1 (P1) and US2 (P1) are independent of each other and can proceed in parallel.
  - US3 (P2) depends on the Portfolio card grid existing (T014, US1) to apply its filter.
  - US4 (P2) is additive to the Portfolio page (T014 area) but otherwise independent.
- **Polish (Phase 7)**: Depends on all targeted user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Needs Foundational (T004–T005). No dependency on other stories.
- **US2 (P1)**: Needs Setup; largely independent of US1 (touches the same `portfolio/page.tsx` file for the transaction-UI removal, so coordinate T017 with T014).
- **US3 (P2)**: Builds on US1's card grid (T014). Independently testable via the net-quantity filter.
- **US4 (P2)**: Additive to the Portfolio page; independent of US2/US3.

### Within Each User Story

- Tests written and FAILING before implementation (T006–T008 before T009–T010; T013/T015/T019/T021 before their implementations).
- Backend model/predicate before the endpoint wiring; frontend schema before components; components before page wiring.

### Parallel Opportunities

- Setup T002 and T003 run in parallel.
- US1 tests T006, T007, T008 run in parallel (different files).
- `PositionCard.tsx` (T012) and its Vitest (T013) develop alongside; `RealizedSummary.tsx` (T022) and its Vitest (T021) likewise.
- Polish T024, T025, T027 run in parallel.
- **File-conflict note**: T014, T017, T020, T023 all edit `frontend/src/app/portfolio/page.tsx` — do **not** run these in parallel; sequence them.

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (must fail first):
Task: "Golden-fixture tests for derive_instruction in backend/tests/portfolio/test_instruction.py"
Task: "Determinism test in backend/tests/portfolio/test_instruction_determinism.py"
Task: "Holdings contract tests in backend/tests/api/test_portfolio_holdings_instruction.py"

# After backend impl, build the card component and its test in parallel:
Task: "Create frontend/src/components/PositionCard.tsx"
Task: "Vitest render/degrade in frontend/tests/PositionCard.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 + minimal US2)

1. Phase 1 Setup → Phase 2 Foundational (carve-out predicate + additive schema).
2. Phase 3 US1 → **STOP and VALIDATE**: cards render with status, levels, news, sentiment, and a call.
3. Phase 4 US2 (page split) so the Portfolio page is a clean card surface.
4. Deploy/demo the decision surface.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → test independently → demo (MVP card view).
3. US2 → test independently → demo (page split).
4. US3 → test independently → demo (closed positions drop off).
5. US4 → test independently → demo (realized scoreboard).
6. Polish → disclosure/determinism/no-regression gates green.

---

## Notes

- **No new endpoint, store, or entity** — one new pure backend module (`instruction.py`), one additive response field (`InstructionBlock` + `directive_enabled`), a frontend page split, and two new components (research §"Summary of new vs reused").
- The AI sentiment score is **context only**, never an input to the instruction (FR-007) — enforced by T007.
- Directive verbs ride the single-owner carve-out (personal-use ON + owner-secret set + not multi-user); neutral status is the default and the instruction section is never dropped (FR-008).
- Determinism, `data_as_of`/staleness + disclaimer on every card and the summary (FR-012), and byte-identical compute paths (FR-013) preserved end-to-end.
- [P] = different files, no dependencies. Watch the shared `portfolio/page.tsx` edits (T014/T017/T020/T023).
