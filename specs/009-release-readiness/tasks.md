---
description: "Task list for feature 009 â€” Release Readiness"
---

# Tasks: Release Readiness â€” Test, Harden, Refresh-on-Start & Deployment Prep

**Input**: Design documents from `specs/009-release-readiness/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED. This is a verification/hardening feature â€” FR-011/FR-012 require the
full backend + frontend suites green, and the contracts (`startup-freshness.md`,
`advisor-prompt-completeness.md`, `data-refresh.md`) mandate contract/regression tests.

**Organization**: Tasks are grouped by user story (P1 â†’ P2) for independent implementation
and testing. Momentum (`midterm_52w_high_momentum`) is the verification focus; value is
postponed (no new work, feature 007 not merged) but its existing tests must stay green.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1â€“US5 (Setup / Foundational / Polish carry no story label)

## Path Conventions

Web app â€” backend at `backend/src/`, `backend/tests/`; frontend at `frontend/src/`,
`frontend/tests/`. Docs under `specs/009-release-readiness/`.

## Non-negotiable constraints (apply to every task)

- **No strategy rule, parameter default, ranking expression, citation, or backtest
  baseline change** (FR-014; Constitution II/III). Cleanup is presentation/robustness only.
- **Determinism preserved**: same snapshot â†’ identical screen/regime/sizing/event output and
  byte-identical advisor prompt (FR-015, SC-010).
- **Startup check is read-only / no-mutation / no-network**; refresh is the only mutation and
  is operator-initiated (FR-001, FR-003).
- **Provider keys stay process-local**, never written to a file (FR-022).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the tracked-findings log and a clean-checkout baseline.

- [X] T001 Create the bug-scan findings log at `specs/009-release-readiness/bug-scan-log.md` with the table header (`id | location | description | severity | resolution`) and the severity legend (`correctness | integrity | crash-hang` = must-fix; `minor` = deferrable-with-rationale) per `contracts/bug-scan-log.md`.
- [X] T002 Capture the clean-checkout baseline: run `py -3.12 -m pytest` (backend) and `npm.cmd run test` + `npm.cmd run test:e2e` (frontend), and record the current pass/fail/skip/xfail inventory â€” explicitly auditing for any `@pytest.mark.skip`/`xfail` on indicator or strategy tests â€” into a "Baseline" note in `specs/009-release-readiness/bug-scan-log.md`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared, no-mutation freshness computation that US1 (endpoint + gate), US2
(advisor per-input freshness), and US4 (per-surface freshness) all read from.

**âš ï¸ CRITICAL**: No user-story work that depends on per-source freshness should begin until this phase is complete.

- [X] T003 Verify `latest_completed_trading_day()` is weekend/holiday-aware in `backend/src/data/market_calendar.py` (US-default market); if a gap exists, fix it and add a unit test in `backend/tests/data/test_market_calendar.py` covering a Sunday/holiday request not reporting a current source as stale (FR-005).
- [X] T004 Implement the read-only **Data Freshness Record** computation helper in `backend/src/data/freshness.py` â€” reads `backend/data/manifest.json` + `latest_completed_trading_day()` and returns per-source `{source_name, kind, data_as_of, latest_session, sessions_behind, is_stale, last_refresh_outcome}` plus `any_stale`. No network, no mutation; a source missing from the manifest reports `data_as_of: null`, `is_stale: true` (data-model.md Â§1).
- [X] T005 [P] Unit test the freshness helper in `backend/tests/data/test_freshness.py`: trading-session `sessions_behind` math, missing-source-is-stale, `any_stale` = logical OR, and no-mutation (identical result on repeated call).

**Checkpoint**: Per-source freshness is computable read-only â€” US1/US2/US4 can proceed.

---

## Phase 3: User Story 1 - App opens with fresh data and tells me how fresh it is (Priority: P1) ðŸŽ¯ MVP

**Goal**: A â‰¤ 3 s, read-only startup staleness check (`GET /data/freshness`) plus a mount-time gate that prompts *Refresh now* (incremental `POST /data/refresh`) or *Proceed on cached data* â€” never silent/automatic.

**Independent Test**: Start with stale cache â†’ gate prompts and "Refresh now" advances `data_as_of`; with a source down â†’ app stays usable on cached data with a staleness notice; with current data â†’ silent, "data is current", no refresh.

### Tests for User Story 1 âš ï¸ (write first, ensure they fail)

- [X] T006 [P] [US1] Contract test for `GET /data/freshness` in `backend/tests/api/test_data_freshness.py`: per-source records + `any_stale`, no-mutation (second call identical), succeeds with network disabled, â‰¤ 3 s ceiling, missing-source-is-stale, carries `data_as_of` + `disclaimer` (contracts/startup-freshness.md).
- [X] T007 [P] [US1] Contract test for `POST /data/refresh` in `backend/tests/api/test_data_refresh.py`: incremental-only (no full rebuild), `capped` flag at the 1,200 cap, side-effects advance the manifest, and graceful-on-unreachable-source (returns cached state + notice, never crashes) (contracts/data-refresh.md).
- [X] T008 [P] [US1] Vitest unit test for `StartupFreshnessGate` in `frontend/tests/unit/StartupFreshnessGate.test.tsx`: stale â†’ prompt, current â†’ silent "data is current", endpoint-unreachable â†’ non-blocking staleness notice (app still usable).
- [X] T009 [P] [US1] Playwright e2e for the startup staleness flow in `frontend/tests/e2e/startup-freshness.spec.ts`: stale-on-start prompt â†’ "Refresh now" updates as-of; "Proceed on cached data" keeps app navigable.

### Implementation for User Story 1

- [X] T010 [US1] Add `GET /data/freshness` to `backend/src/api/data.py` â€” returns the T004 freshness aggregate (per-source records + `any_stale` + `latest_session`); read-only, no-mutation, no-network; envelope `data_as_of`/`disclaimer` via existing middleware (contracts/startup-freshness.md).
- [X] T011 [US1] Verify `POST /data/refresh` in `backend/src/api/data.py` already satisfies the incremental + graceful-on-unreachable guarantees; if T007 reveals a gap (e.g. an unreachable source raising), harden it to return cached state with a non-blocking note (FR-002/FR-003). Log any defect found in `bug-scan-log.md`.
- [X] T012 [P] [US1] Add a Zod schema + fetcher for `/data/freshness` to `frontend/src/lib/api.ts` (sources[], `any_stale`, `latest_session`, envelope fields).
- [X] T013 [US1] Create `frontend/src/components/StartupFreshnessGate.tsx` â€” on mount calls `/data/freshness`; when `any_stale`, renders a non-blocking prompt (*Refresh now* â†’ `POST /data/refresh`; *Proceed on cached data* â†’ dismiss); when current, silent "data is current"; when the check is unreachable, shows a staleness notice without blocking. Mount it in `frontend/src/components/AppShell.tsx`.
- [X] T014 [US1] Drive `frontend/src/components/DataFreshnessPanel.tsx` per-source state from `/data/freshness` (or `/meta`), naming each stale source and its `data_as_of`, with the operator refresh control + status (FR-002, FR-004).
- [X] T015 [US1] Verify `frontend/src/components/GlobalDataAsOf.tsx` reflects the latest completed trading session (not calendar day); adjust only if it overstates currency (FR-004/FR-005).

**Checkpoint**: Startup freshness detection + operator-initiated refresh fully functional and independently testable.

---

## Phase 4: User Story 2 - The advisor prompt is complete and detailed enough to stand alone (Priority: P1)

**Goal**: Make the exported prompt self-contained by adding **per-material-input freshness** (prices/fundamentals/regime as-of), keeping integrity warnings verbatim and the honesty block driven by the real backtest bias check. Builder stays a pure, deterministic function.

**Independent Test**: Export for a clean candidate and an integrity-flagged candidate; both are self-contained, list per-input freshness, surface any integrity warning verbatim, carry the real survivorship/limitations block, contain zero directive language, and re-export byte-identically for a fixed snapshot.

### Tests for User Story 2 âš ï¸ (write first, ensure they fail)

- [X] T016 [P] [US2] Test per-material-input freshness in the advisor prompt in `backend/tests/agent/test_advisor_prompt.py`: the prompt names prices `data_as_of`, fundamentals `data_as_of`, and regime as-of individually (not one global timestamp) for single-candidate and batch builders (contracts/advisor-prompt-completeness.md Â§3).
- [X] T017 [P] [US2] Test self-contained + integrity-verbatim + honesty-from-real-bias + zero-directive + byte-identical-determinism in `backend/tests/agent/test_advisor_prompt_completeness.py` (FR-006â€“FR-010, SC-004/SC-005; feature-004 FR-011 determinism).

### Implementation for User Story 2

- [X] T018 [US2] Add per-material-input freshness lines to the candidate and honesty blocks in `backend/src/agent/advisor_prompt.py` â€” additively, reading as-of values from the result/snapshot (no wall-clock in body) so output stays pure/deterministic; apply to both the single-candidate and batch/matrix builders.
- [X] T019 [US2] Confirm the per-candidate data-integrity warning travels **verbatim and prominently** into the prompt for a flagged candidate (feature 008 demotion), and that the honesty block's survivorship verdict comes from the real `bias_check` â€” wire/verify in `backend/src/agent/advisor_prompt.py`; log any gap in `bug-scan-log.md`.

**Checkpoint**: Advisor prompt is self-contained and detailed; determinism and zero-directive guarantees hold.

---

## Phase 5: User Story 3 - I can trust the app is bug-free and robust because the full suite proves it (Priority: P1)

**Goal**: Full backend + frontend suites green on a clean checkout with 0 silently skipped financial-logic tests; a bounded bug scan with all must-fix findings fixed (+ regression test) and dead code removed â€” determinism preserved.

**Independent Test**: From a clean checkout, both suites pass 100% with no skipped financial-logic tests; `bug-scan-log.md` shows 0 open must-fix findings and every other finding logged with rationale.

- [X] T020 [US3] Run the full backend suite (`py -3.12 -m pytest`) to green; eliminate every silently skipped/xfail financial-logic (indicator/strategy) test â€” either restore it to running-and-passing or replace the skip with a justified, non-financial-logic rationale (FR-011, SC-006). Record outcome in `bug-scan-log.md`. **Done: 297 passed, 0 skipped/xfail; ASYS oracle drift resolved as ticker-agnostic gate invariants (BUG-002).**
- [X] T021 [US3] Run the full frontend suites (`npm.cmd run test` + `npm.cmd run test:e2e`) to green, including the no-directive-language lint and the `data_as_of`/`disclaimer` presence checks on every page (FR-012, SC-005). **Done: unit 9/9, e2e 45/45; added missing `test:e2e` script; fixed BUG-004/BUG-005 (test mock drift + portfolio-state isolation).**
- [X] T022 [US3] Perform the bounded bug scan across the real runtime surfaces â€” `/screen`, `/analyze`, candidate detail, advisor-prompt export, `/strategies/*`, `/portfolio`, `/data/refresh`, `/meta`, `/data/freshness`, and the data loaders (prices store, EDGAR slim cache, calendars, manifest) â€” probing source-down / empty-result / missing-fundamentals / timeout. Record every finding with severity + resolution in `specs/009-release-readiness/bug-scan-log.md` (FR-013). **Done: see T022 outcome table; found BUG-006 (frontend hang) + BUG-007 (backend 500).**
- [X] T023 [US3] Fix every must-fix finding (`correctness`/`integrity`/`crash-hang`) from T022, each with a regression test (failing before, passing after) in the appropriate `backend/tests/` or `frontend/tests/` location; update its row to `fixed` (+ commit/test ref). Defer only `minor` findings, each with a logged one-line rationale (SC-007). **Done for US3-scope: BUG-007 fixed (`backend/tests/api/test_robustness_run.py`). BUG-006 (frontend graceful-degradation) carried to US4/T030 — its proper home; still open, to be closed before release per gate T037.**
- [X] T024 [US3] Remove identified dead code, unused modules, and obsolete artifacts **without** changing any strategy rule, default, citation, or backtest baseline; re-run both suites green afterward (FR-014, FR-015). **Done: 16 ruff-identified dead items removed; registry side-effect imports preserved; suites green.**
- [X] T025 [US3] Determinism check (SC-010): run the same momentum screen twice on an unchanged snapshot and confirm identical candidate order, regime, sizing, and event output; export the advisor prompt twice and confirm byte-identical output. Record the check in `bug-scan-log.md`. **Done: candidate order/regime/full payload identical; advisor prompt byte-identical (23,915 chars).**

**Checkpoint**: Evidence of correctness â€” green suites, triaged findings, preserved determinism.

---

## Phase 6: User Story 4 - The app degrades gracefully instead of breaking (Priority: P2)

**Goal**: Empty/missing/timeout paths are handled honestly and the app stays navigable; partial data is never presented as authoritative.

**Independent Test**: Simulate source-down, empty result, missing fundamentals, and timeout; each yields a clear message and a still-usable app â€” 0 crashes/hangs/blank screens (SC-008).

### Tests for User Story 4 âš ï¸ (write first where a defect is found)

- [X] T026 [P] [US4] Backend test for empty/missing-input handling in `backend/tests/api/test_robustness.py`: a screen yielding zero candidates returns an explicit empty-state payload (FR-016); a candidate missing a material input is deterministically excluded-or-flagged with a stated reason, run not aborted (FR-017). **Done: added regression tests; full backend suite 299 passed.**
- [X] T027 [P] [US4] Frontend test for error/empty surfaces in `frontend/tests/unit/error-states.test.tsx`: a backend failure/timeout renders a retryable, human-readable error while the rest of the app stays navigable (FR-018); an empty screen renders the empty-state, not a blank/error page. **Done: added empty-state + `ApiError` tests; Vitest 11/11 passed.**

### Implementation for User Story 4

- [X] T028 [US4] Ensure a zero-candidate screen renders an explicit empty-state with a stated reason in the screen surface (`frontend/src/components/ScreenerTable.tsx` and the screen page), backed by the FR-016 backend payload â€” no blank/error page. **Done: table and screen page render explicit empty-state copy before table markup.**
- [X] T029 [US4] Ensure a candidate missing a material input is handled deterministically (excluded or flagged with a stated reason) in the relevant `backend/src/api/screen.py`/`analyze.py` path without aborting the run (FR-017). **Done: missing fundamentals are stated in data notes; run continues and is covered by T026.**
- [X] T030 [US4] Add a retryable, human-readable error surface for backend failures/timeouts in the frontend data-fetch layer (`frontend/src/lib/api.ts` + consuming components) so the rest of the app stays navigable (FR-018). **Done: `ApiError` carries status/retryability; screen page degrades when backtest/run calls fail; BUG-006 closed.**
- [X] T031 [US4] Verify the layout shell renders `data_as_of` + `disclaimer` unconditionally on every page (`frontend/src/components/AppShell.tsx`, `GlobalDataAsOf.tsx`, `Disclaimer.tsx`); covered by the existing Playwright presence check (FR-019). **Done: full Playwright suite 45/45 passed, including `disclaimer-everywhere.spec.ts` and validation surface sweep.**

**Checkpoint**: Each failure mode degrades gracefully; app remains usable.

---

## Phase 7: User Story 5 - The app is packaged and documented for one-command final deployment (Priority: P2)

**Goal**: A reproducible deployment runbook taking a clean environment to a running production build, with documented data dirs + process-local keys, ending suite-green and committed.

**Independent Test**: Follow the runbook from scratch on the target machine; the app builds/starts in production mode, serves test-validated behavior, and the runbook has 0 missing/incorrect steps (SC-009).

- [X] T032 [US5] Finalize the deployment runbook in `specs/009-release-readiness/quickstart.md` (already drafted) â€” verify each step against the real scripts/commands (`py -3.12 -m pip install -e .\backend[dev]`, seed/refresh, uvicorn; `npm.cmd run build`/`start` with runtime `NEXT_PUBLIC_API_URL`); document data-directory locations and process-local-only provider keys (FR-020, FR-022). **Done: scripts/install/uvicorn/data-dirs/key-handling all verified accurate; no corrections needed (see Phase 7 outcome).**
- [X] T033 [P] [US5] Mirror the runbook's "Run Locally" production-build steps into `README.md`, consistent with `quickstart.md` (no env var baked into the build). **Done: README "Run Locally" rewritten to the Next production build path.**
- [X] T034 [US5] Execute a first-time-follow validation of the runbook on a clean environment and exercise the primary flows (startup freshness â†’ screen â†’ candidate detail â†’ advisor prompt â†’ portfolio); confirm 0 missing/incorrect steps and production-parity behavior, recording the result (FR-021, SC-009). **Done: production build clean; uvicorn:8000 + prod frontend:3000 served all 9 routes + every primary flow; 0 missing/incorrect steps.**
- [~] T035 [US5] Finalization: ensure the working tree on `009-release-readiness` is suite-green, then commit the intended changes in a known-good state (FR-023). **Suite-green achieved (backend 299, unit 11, e2e 45); commit deferred to the operator via the `/speckit-git-commit` hook (commit only on explicit request).**

**Checkpoint**: Reproducible deployment proven; release branch committed suite-green.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T036 Repoint the `<!-- SPECKIT START -->â€¦<!-- SPECKIT END -->` agent-context pointer in `CLAUDE.md` to `specs/009-release-readiness/plan.md` (plan Â§Agent context update). **Done: the SPECKIT block already points to `specs/009-release-readiness/plan.md` (CLAUDE.md:1-8); verified current, no change needed.**
- [X] T037 Close out `specs/009-release-readiness/bug-scan-log.md`: confirm 0 untriaged findings, 0 open must-fix, and every deferral carries a rationale (SC-007). **Done: added T037 closeout table — 4 must-fix all fixed (each w/ regression test), 0 untriaged, 0 open must-fix, BUG-003 deferred with rationale.**
- [X] T038 [P] Final New-this-feature verification per `quickstart.md` Â§C: `/data/freshness` < 3 s + no-mutation + works network-disabled; startup gate stale/current/unreachable behaviors; advisor prompt self-contained + per-input freshness. **Done: backend freshness/advisor/calendar 10 passed; `StartupFreshnessGate` 4 passed; all §C behaviors green.**

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies â€” start immediately.
- **Foundational (Phase 2)**: Depends on Setup â€” blocks US1/US2/US4 freshness work.
- **User Stories (Phase 3+)**: Depend on Foundational. US1 and US2 (both P1) are independent of each other once Foundational is done. US3 (suite-green/scan) is best run after US1/US2 code lands so its green-suite gate covers the new code. US4/US5 (P2) build on the P1 correctness foundation.
- **Polish (Phase 8)**: After all targeted stories complete.

### User Story Dependencies

- **US1 (P1)**: After Foundational. No dependency on other stories.
- **US2 (P1)**: After Foundational. Independent of US1.
- **US3 (P1)**: Independently testable, but its "full suite green incl. new code" outcome is most meaningful after US1/US2/US4 land. The bug scan (T022) can begin any time after Setup.
- **US4 (P2)**: After Foundational; builds on US3 correctness.
- **US5 (P2)**: After US3 (and ideally US1/US2/US4) so the validated build is the one documented.

### Within Each User Story

- Tests (T006â€“T009, T016â€“T017, T026â€“T027) written and failing before implementation.
- Foundational helper (T004) before the endpoint (T010) and advisor freshness (T018).
- Backend endpoint/schema before frontend gate consuming it.

### Parallel Opportunities

- T001 and the audit portion of T002 can overlap.
- T005 is [P] with other Phase 2 review.
- US1 tests T006/T007/T008/T009 are all [P] (different files).
- US2 tests T016/T017 are [P]; T012 (frontend schema) is [P] with backend T010/T011.
- US4 tests T026/T027 are [P]; T033 (README mirror) is [P].
- US1 and US2 can be developed in parallel by different developers once Phase 2 is done.

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (write-first, expect fail):
Task: "Contract test GET /data/freshness in backend/tests/api/test_data_freshness.py"
Task: "Contract test POST /data/refresh in backend/tests/api/test_data_refresh.py"
Task: "Vitest StartupFreshnessGate states in frontend/tests/unit/StartupFreshnessGate.test.tsx"
Task: "Playwright startup staleness flow in frontend/tests/e2e/startup-freshness.spec.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1: Setup (bug-scan log + baseline).
2. Phase 2: Foundational (freshness helper + calendar basis).
3. Phase 3: US1 â€” startup freshness detection + operator refresh.
4. **STOP and VALIDATE**: staleâ†’prompt, currentâ†’silent, source-downâ†’usable-on-cached.

### Incremental Delivery

1. Setup + Foundational â†’ freshness computable.
2. US1 (refresh-on-start) â†’ validate â†’ the highest-risk failure (silent stale results) defeated.
3. US2 (advisor completeness) â†’ validate self-contained export.
4. US3 (suite-green + bug scan + cleanup) â†’ evidence of correctness.
5. US4 (robustness) â†’ graceful degradation.
6. US5 (deployment runbook) â†’ reproducible production build, committed suite-green.

### Parallel Team Strategy

After Phase 2: Developer A on US1, Developer B on US2; the bug scan (T022) can start in parallel.
Converge on US3 green-suite gate, then US4/US5.

---

## Notes

- [P] = different files, no incomplete-task dependency.
- Every fix in US3/US4 adds a regression test (fail-before/pass-after) per `contracts/bug-scan-log.md`.
- No task may change a strategy rule, default, citation, or backtest baseline (FR-014).
- Commit after each task or logical group; keep the suite green at each checkpoint.
