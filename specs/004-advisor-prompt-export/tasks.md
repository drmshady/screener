---
description: "Task list for Advisor Prompt Export"
---

# Tasks: Advisor Prompt Export

**Input**: Design documents from `specs/004-advisor-prompt-export/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — the constitution's Principle IV (Test-First for Financial
Logic) and the plan mandate fixture/oracle-anchored tests written before the
implementation they cover.

**Organization**: Tasks are grouped by user story. US1 (complete prompt) and US3
(honesty) are both P1; US1 is the MVP slice and US3 makes it constitutionally
honest. US2 (self-containment) and US4 (personal-use scope) are P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- File paths are exact and relative to repo root.

## Path Conventions

Web app: backend at `backend/src`, `backend/tests`; frontend at `frontend/src`,
`frontend/tests`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new package locations the feature lives in.

- [x] T001 Create the backend agent package with `backend/src/agent/__init__.py`
- [x] T002 [P] Create the backend test package directory `backend/tests/agent/` with an `__init__.py` and a `conftest.py` that reuses the existing frozen-snapshot session fixture (import from `backend/tests/validation/conftest.py` or the shared fixture) so all agent tests run read-only against the pinned snapshot

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared inputs and the no-duplicate-computation refactor every story
depends on.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [x] T003 Refactor `backend/src/api/analyze.py`: extract the candidate-result computation (single-ticker snapshot → `prepare_universe_gates` → `evaluate` → `derive_levels`, plus `would_be_selected` and `data_notes`) into a shared, importable helper `compute_candidate_result(ticker, strategy, as_of)` and have `analyze_ticker` call it. This guarantees the prompt and the analyze surface use one computation path (SC-005). Existing analyze tests must still pass.
- [x] T004 [P] Implement `personal_use_directive()` in `backend/src/lib/flags.py`, resolving env `SCREENER_PERSONAL_USE_DIRECTIVE` (default `False`), following the existing `SCREENER_*` operator-override idiom used in `midterm_52w_high_momentum.py`
- [x] T005 [P] In `backend/src/agent/advisor_prompt.py`, add input gatherers only (no section rendering yet): `_load_survivorship_status()` reading `bias_check.survivorship_bias` from `backend/data/backtests/midterm_52w_high_momentum.json` (returns passed flag + note, or an "unconfirmed" marker if missing/unreadable), and `_strategy_declaration(slug)` returning the registry `Strategy` object
- [x] T006 [P] Add the `AdvisorPromptResponse` model (fields: `ticker`, `strategy`, `personal_use_directive`, `prompt`, `data_as_of`, `disclaimer`) to `backend/src/models/strategy.py` per `contracts/advisor-prompt-endpoint.md`

**Checkpoint**: Inputs + shared computation ready — story work can begin.

---

## Phase 3: User Story 1 - Copy a complete advisor prompt (Priority: P1) 🎯 MVP

**Goal**: One control produces a copy-ready prompt containing the candidate's
result (identity, levels, gate breakdown, regime), the as-of date, and the
disclaimer — every number sourced from the app.

**Independent Test**: Open a matched candidate, click "Copy advisor prompt,"
paste into a text editor; confirm ticker, all gates with status, the four price
levels, regime, as-of date, and disclaimer are present with no gaps, and the
numbers equal the analyze surface.

### Tests for User Story 1 ⚠️ (write first, must fail)

- [x] T007 [P] [US1] Builder test in `backend/tests/agent/test_advisor_prompt_builder.py`: for a known snapshot ticker, `build_advisor_prompt(...)` output contains the candidate identity, every gate from `gate_results` with its status, entry/stop/tighter-stop/take-profit and reward:risk, the regime line, `data_as_of`, and the disclaimer (FR-002/003/004/005/009)
- [x] T008 [P] [US1] Determinism test in the same file: building twice for the same ticker+as_of yields a byte-identical `prompt`, and the body contains no wall-clock timestamp (FR-011, SC-004)
- [x] T009 [P] [US1] Grounded-numbers test in `backend/tests/agent/test_advisor_prompt_endpoint.py`: every numeric value in the prompt equals the corresponding value from `GET /analyze/{ticker}` for the same inputs (SC-005)
- [x] T010 [P] [US1] Endpoint contract test in the same file: `GET /analyze/{ticker}/advisor-prompt` returns 200 with the `AdvisorPromptResponse` shape; 404 when levels are underivable; 400 for an unsupported `strategy` (per `contracts/advisor-prompt-endpoint.md`)

### Implementation for User Story 1

- [x] T011 [US1] Implement the candidate-result, gate-breakdown, and regime sections plus the as-of/disclaimer footer in `build_advisor_prompt(...)` in `backend/src/agent/advisor_prompt.py` (use a neutral placeholder task line for now; US4 makes it flag-aware)
- [x] T012 [US1] Add `GET /analyze/{ticker}/advisor-prompt` to `backend/src/api/analyze.py` calling `compute_candidate_result` (T003) then `build_advisor_prompt`, returning `AdvisorPromptResponse`; 404 on underivable levels, 400 on unsupported strategy
- [x] T013 [P] [US1] Add `frontend/src/lib/advisorPrompt.ts`: a Zod-validated fetch of the endpoint plus a clipboard helper
- [x] T014 [P] [US1] Add `frontend/src/components/CopyAdvisorPrompt.tsx`: a "Copy advisor prompt" button with a collapsible preview and a copied-confirmation state
- [x] T015 [US1] Mount `CopyAdvisorPrompt` on each strategy-match card in `frontend/src/app/candidate/[ticker]/page.tsx` and on the analyzed ticker in `frontend/src/app/analyze/page.tsx` (FR-015)
- [x] T016 [US1] Frontend e2e `frontend/tests/e2e/advisor-prompt-copy.spec.ts`: clicking the button on a candidate copies a non-empty prompt containing the ticker and the disclaimer

**Checkpoint**: A complete, grounded, copyable prompt works end-to-end (MVP).

---

## Phase 4: User Story 3 - The prompt is honest about limitations (Priority: P1)

**Goal**: Every prompt carries the honesty block — survivorship status (failing
today), fail-open/skipped-gate notes, freshness — so it can never hand the
advisor clean-looking numbers while hiding the bias.

**Independent Test**: Generate prompts for several candidates; each contains the
survivorship caveat, the as-of date, and a note for any gate skipped/passed
through for that candidate.

### Tests for User Story 3 ⚠️ (write first, must fail)

- [x] T017 [P] [US3] Honesty test in `backend/tests/agent/test_advisor_prompt_builder.py`: while `bias_check.survivorship_bias.passed` is false, the prompt states historical performance is optimistic and why (no delisted tickers) (FR-007, SC-003)
- [x] T018 [P] [US3] Fail-open test in the same file: for a candidate with a skipped/passed-through gate, the prompt distinguishes it from a genuine pass; and the prompt always carries `data_as_of` + disclaimer (FR-008, FR-009)
- [x] T019 [P] [US3] Artifact-missing test in the same file: when the backtest artifact is absent/unreadable, the honesty block states the bias status is unconfirmed and never implies it is clean

### Implementation for User Story 3

- [x] T020 [US3] Implement the honesty block in `build_advisor_prompt(...)`: survivorship status + note from `_load_survivorship_status()` (T005), per-candidate skipped/passed-through gate notes derived from `gate_results`, the data-freshness/stale-source note, and the personal-use scope reminder
- [x] T021 [US3] Ensure the honesty block is unconditional (rendered for every prompt regardless of flag) and ordered last per `contracts/advisor-prompt.schema.md`

**Checkpoint**: The MVP prompt is now constitutionally honest (Principle III/V disclosure).

---

## Phase 5: User Story 2 - Self-contained prompt (Priority: P2)

**Goal**: The prompt carries its own strategy context — name, George & Hwang
(2004) citation, timeframe, holding period, gate list, and all modifications
with citations — sourced from the live declaration so it never drifts and works
in a fresh chat.

**Independent Test**: Paste a prompt into an AI chat with no preloaded knowledge;
it correctly names the strategy, cites George & Hwang (2004), and references the
gates without asking for missing context.

### Tests for User Story 2 ⚠️ (write first, must fail)

- [x] T022 [P] [US2] Self-containment test in `backend/tests/agent/test_advisor_prompt_builder.py`: the prompt contains the strategy name, citation, timeframe, holding period, gate list, and every modification in `Strategy.modifications` together with each modification's own citation (FR-006, SC-002)
- [x] T023 [P] [US2] Declaration-drift test in the same file: iterating `registry.get(slug).modifications`, every declared modification name appears in the prompt (so adding a modification fails this test until the prompt includes it) (FR-012)

### Implementation for User Story 2

- [x] T024 [US2] Implement the strategy-context section in `build_advisor_prompt(...)`, rendering from the live `Strategy` declaration (T005) — name, citation, timeframe, `holding_period_days`, the gate list, and `modifications` (name + citation each); no hand-maintained strategy text

**Checkpoint**: The prompt is fully self-contained and drift-proof.

---

## Phase 6: User Story 4 - Personal-use scope is enforced (Priority: P2)

**Goal**: Directive (take/pass/size) framing appears only when the personal-use
flag is on; off → neutral framing with zero directive language, preserving the
app's no-directive-copy guarantee.

**Independent Test**: Flag on → prompt asks for a directive call. Flag off →
prompt asks for neutral analysis and contains no "buy/sell/recommended" language.

### Tests for User Story 4 ⚠️ (write first, must fail)

- [x] T025 [P] [US4] Flag test in `backend/tests/agent/test_advisor_prompt_flag.py`: with the flag off, the prompt task line uses neutral framing and contains none of {buy, sell, recommended, strong buy} (case-insensitive); with the flag on, it uses directive framing (FR-013, SC-006)
- [x] T026 [P] [US4] Endpoint echo test in `backend/tests/agent/test_advisor_prompt_endpoint.py`: the response `personal_use_directive` field reflects the resolved flag

### Implementation for User Story 4

- [x] T027 [US4] Make the task-instruction section flag-aware in `build_advisor_prompt(...)` using `personal_use_directive()` (T004): directive framing when on, neutral when off; thread the flag into `AdvisorPromptResponse.personal_use_directive` in the endpoint (T012)
- [x] T028 [US4] In `CopyAdvisorPrompt.tsx`, render the preview with a `data-personal-use-prompt` marker only when `personal_use_directive` is true, so the directive text is confined to one clearly-marked element
- [x] T029 [US4] Extend `frontend/tests/e2e/no-directive-copy.spec.ts` to (a) assert the page is directive-free with the flag off, and (b) scope the exemption to the `data-personal-use-prompt` element when on (FR-014)
- [x] T030 [US4] Governance prerequisite: DONE — constitution amended to v1.1.0 (2026-06-13) adding the Personal-use directive exception to Principle V (flag-gated, OFF by default, auto-reverts for shared/hosted, disclosure preserved). The `SCREENER_PERSONAL_USE_DIRECTIVE` flag is now sanctioned for personal use; default stays OFF.

**Checkpoint**: Directive mode is available, bounded, and compliant-by-default.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T031 [P] Update `claude-project/04-workflow-and-prompts.md` to note Template A is now generated in-app ("Copy advisor prompt"), and that the generated prompt is self-contained
- [x] T032 [P] Add the new env flag `SCREENER_PERSONAL_USE_DIRECTIVE` to the relevant settings/quickstart docs
- [x] T033 Run `specs/004-advisor-prompt-export/quickstart.md` end-to-end to validate generate + verify steps
- [ ] T034 Run the full regression floor: `python -m pytest backend/tests`, `npm --prefix frontend run test`, `npx --prefix frontend playwright test` — all green before merge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; BLOCKS all stories. T003 (refactor) blocks the endpoint tasks; T004/T005/T006 are [P].
- **US1 (Phase 3)**: depends on Foundational. MVP.
- **US3 (Phase 4)**: depends on US1 (extends `build_advisor_prompt`).
- **US2 (Phase 5)**: depends on US1; independent of US3.
- **US4 (Phase 6)**: depends on US1; independent of US2/US3.
- **Polish (Phase 7)**: depends on all targeted stories.

### Within Each User Story

- Tests written first and FAIL before implementation (Principle IV).
- Builder section rendering before endpoint/frontend wiring that surfaces it.
- `build_advisor_prompt` is edited by US1/US2/US3/US4 — those edits touch the
  same file and must be sequenced (US1 → US3 → US2 → US4), not parallelized.

### Parallel Opportunities

- T004, T005, T006 (Foundational) run in parallel.
- Within US1: tests T007–T010 in parallel; frontend T013/T014 in parallel.
- US2 and US4 can be worked in parallel with US3 *only if* the shared
  `build_advisor_prompt` edits are coordinated; otherwise sequence them.

---

## Implementation Strategy

### MVP First

1. Phase 1 Setup → Phase 2 Foundational.
2. Phase 3 (US1) → STOP and VALIDATE: a complete, grounded, copyable prompt.
3. Phase 4 (US3) immediately after — honesty is a P1 correctness property, not
   optional; do not ship the MVP externally without it.

### Incremental Delivery

US1 (+US3) → demo → US2 (self-containment) → US4 (personal-use directive, gated
behind the flag and the constitutional amendment) → polish.

---

## Notes

- [P] = different files, no dependencies.
- The four stories all extend one file (`advisor_prompt.py`); respect the
  US1 → US3 → US2 → US4 ordering on that file.
- Directive framing (US4) stays default-off until the Principle V amendment
  (T030) lands.
- Re-run `backend/tests/agent` after any strategy change — the drift test (T023)
  guards against the prompt going stale.
