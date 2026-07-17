---
description: "Task list for feature 018 — Daily AI Portfolio Brief (Email Digest)"
---

# Tasks: Daily AI Portfolio Brief (Email Digest)

**Input**: Design documents from `specs/018-daily-portfolio-brief/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED. Plan Principle IV mandates test-first for the two new pure units (the
five-item recommendation ranker and the renderer), the no-directive lint, the directive
carve-out truth table, contract tests, and CI-automation tests. Write each test first and
confirm it FAILS before the matching implementation task.

**Organization**: Tasks are grouped by user story (P1 → P2 → P3) so each story is an
independently testable, deliverable increment over the single assembled email.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 (setup, foundational, and polish tasks carry no story label)
- All paths are relative to the repo root (`e:\screener`).

## Path Conventions

- Backend package: `backend/src/brief/` (new), `backend/src/models/brief.py` (new),
  `backend/src/data/brief_store.py` (new), `backend/src/api/brief.py` (new),
  `backend/src/lib/flags.py` (extended).
- Tests: `backend/tests/brief/`, `backend/tests/contract/`, `backend/tests/automation/`.
- CI: `.github/workflows/daily-refresh.yml` (extended).
- Run pytest from repo root with `py -3.12 -m pytest ... -q` (Windows dev convention).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new package/test skeletons so all later tasks have a home.

- [X] T001 Create the `brief/` package skeleton: `backend/src/brief/__init__.py` and empty module stubs `backend/src/brief/assemble.py`, `backend/src/brief/recommend.py`, `backend/src/brief/render.py`, `backend/src/brief/email.py`.
- [X] T002 [P] Create test package dirs: `backend/tests/brief/__init__.py` and confirm `backend/tests/contract/` and `backend/tests/automation/` exist (create `__init__.py` if missing).
- [X] T003 [P] Document the runtime env config (`SCREENER_BRIEF_*`, `SCREENER_PERSONAL_USE_DIRECTIVE`) in `specs/018-daily-portfolio-brief/quickstart.md` cross-check — verify the accessor names match data-model.md §Configuration before coding flags.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared entities, flags, store, email edge, and router skeleton that ALL three
user stories build on. Directive-gating and idempotency infra live here because every story
composes into one email.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [X] T004 [P] Create all Pydantic v2 entities in `backend/src/models/brief.py`: `BriefModel` (with the enforced `len(recommendations) == 5` construction invariant and `generated_at` excluded from the determinism hash), `PortfolioStatusSection`, `HoldingLine`, `AttentionItem` (reason_code enum + severity), `NewsItem`, `MarketContextLine`, `RecommendationItem` (subject_kind + source_signal enums), `BriefDeliveryRecord`, `BriefRunResponse`, `BriefStatusResponse` — per data-model.md.
- [X] T005 [P] Add `brief_enabled()` (default OFF) plus the SMTP/recipient env accessors (`SCREENER_BRIEF_SMTP_HOST/PORT/USER/PASSWORD`, `SCREENER_BRIEF_RECIPIENT`) to `backend/src/lib/flags.py` — runtime env only, never logged (FR-015).
- [X] T006 [P] Write the directive carve-out truth-table test in `backend/tests/brief/test_directive_carveout.py` (all combinations of personal-use flag × owner-secret set × multi-user → expected `brief_directive_enabled()` result). Confirm it FAILS.
- [X] T007 Add `brief_directive_enabled()` to `backend/src/lib/flags.py` — returns True only when `SCREENER_PERSONAL_USE_DIRECTIVE=1` AND `owner_secret()` is set AND not multi-user; leave `personal_use_directive()` untouched (research Decision 4). Makes T006 pass.
- [X] T008 [P] Write the Delivery Run Record store test in `backend/tests/brief/test_brief_store.py` (save/load `brief_runs.json`, session-keyed at-most-one `delivered`, `content_hash` stability). Confirm it FAILS.
- [X] T009 Implement `backend/src/data/brief_store.py` (load/save under `SCREENER_DATA_DIR`, `last_delivered_for_session`, idempotency check, SHA-256 `content_hash` over determinism-relevant fields excluding `generated_at`). Makes T008 pass.
- [X] T010 [P] Write the email-transport test in `backend/tests/brief/test_email.py` (injectable stub transport: successful send, bounded retry on failure, hard recipient==`SCREENER_BRIEF_RECIPIENT` guard, no plaintext password in any log). Confirm it FAILS.
- [X] T011 Implement `backend/src/brief/email.py` (stdlib `smtplib.SMTP` STARTTLS + `email.message.EmailMessage`, injectable transport, bounded retry per research Decision 6, owner-only recipient guard per FR-009). Makes T010 pass.
- [X] T012 [P] Write contract tests in `backend/tests/contract/test_brief_run.py` and `backend/tests/contract/test_brief_status.py` (flag-off ⇒ 404; owner-secret dependency enforced; `BriefRunResponse`/`BriefStatusResponse` shapes; `data_as_of` + `disclaimer` present). Confirm they FAIL.
- [X] T013 Implement the `backend/src/api/brief.py` router skeleton and register it in `backend/src/api/app.py`: `GET /brief/status` (returns enabled + last_run), `POST /brief/run` behind the owner-secret dependency with flag-off 404, session idempotency short-circuit (reuses T009), non-trading-day skip recording a `skipped` record (FR-011), and a `dry_run` flag. Assemble/render/send are stubbed here and wired per story. Makes T012 pass.

**Checkpoint**: Endpoints resolve, gating/idempotency/status work, email edge and store are unit-tested. User stories can now proceed.

---

## Phase 3: User Story 1 - Daily portfolio status arrives in my inbox (Priority: P1) 🎯 MVP

**Goal**: One deterministic email per completed session with total value, overall + per-holding
P&L, risk exposure/heat, and the holdings-needing-attention list — plus `data_as_of` and the
non-advice disclaimer — delivered end-to-end to the owner's inbox.

**Independent Test**: With an imported portfolio and `SCREENER_BRIEF_ENABLED=1`, POST
`/brief/run` (dry_run) and confirm the returned brief has portfolio value, overall + per-holding
P&L, risk/heat, an attention list, `data_as_of`, and the disclaimer; run twice ⇒ identical
`content_hash`; empty portfolio ⇒ explicit "portfolio is empty" (never a silent failure).

### Tests for User Story 1 ⚠️ (write first, confirm FAIL)

- [X] T014 [P] [US1] Portfolio-section assemble test in `backend/tests/brief/test_assemble_portfolio.py` — reuses a fixture portfolio; asserts totals/P&L/heat mapping, `is_empty` path (US1 AC3), and deterministic attention ordering (risk/heat breach → stop proximity → stage change).
- [X] T015 [P] [US1] Renderer determinism + disclosures test in `backend/tests/brief/test_render_portfolio.py` — same snapshot ⇒ identical `content_hash` (SC-005, `generated_at` excluded); `data_as_of` + `disclaimer` always present (FR-008); active staleness/integrity warnings surfaced verbatim.
- [X] T016 [P] [US1] End-to-end run test in `backend/tests/brief/test_brief_run_us1.py` — POST `/brief/run` (dry_run) returns a `delivered` (or dry) record whose brief carries the full status section; empty-portfolio case delivers explicit empty copy; second call for same session is idempotent (FR-010).

### Implementation for User Story 1

- [X] T017 [US1] Implement the portfolio section in `backend/src/brief/assemble.py` — reuse `api/portfolio._assemble_holdings` → `PortfolioTotals` and build `PortfolioStatusSection` (value, realized/unrealized/total P&L, win_rate, heat/headroom, per-holding lines) with fail-soft + `is_empty` (research Decision 8; no new financial logic, FR-002).
- [X] T018 [US1] Implement the attention list in `backend/src/brief/assemble.py` — derive `AttentionItem`s from `portfolio/holding_risk.py` + `portfolio_heat_ceiling()` + the feature-016 pipeline stage in the blob, ordered by the documented precedence (severity-tie-broken, deterministic).
- [X] T019 [US1] Add a deterministic baseline fill-to-five in `backend/src/brief/recommend.py` — portfolio-level "no action indicated"/heat-headroom items so `BriefModel` satisfies the exactly-five invariant and the email is sendable now (US3 replaces the ranking tiers). Documented as the fill tier.
- [X] T020 [US1] Implement the portfolio + disclosures render path in `backend/src/brief/render.py` — deterministic text + minimal HTML for status/attention, `data_as_of`, `DISCLAIMER_TEXT`, warnings; excludes `generated_at` from the hash.
- [X] T021 [US1] Wire `POST /brief/run` in `backend/src/api/brief.py`: assemble → render → `email.send` (unless dry_run) → write `BriefDeliveryRecord` with `content_hash`; honor idempotency, non-trading-day skip, and empty portfolio; return `BriefRunResponse`.

**Checkpoint**: A reliable daily portfolio-status email is delivered and deterministic — MVP shippable.

---

## Phase 4: User Story 2 - News and sentiment that may affect my stocks (Priority: P2)

**Goal**: Add the news/sentiment section (items over held + watched tickers, each tied to its
ticker(s) with source + as-of, over the since-last-brief window) plus a concise market-context
line — without changing delivery.

**Independent Test**: For an owner holding a ticker with recent coverage, run the loop and
confirm the brief lists relevant news/sentiment items mapped to holdings (each with source +
as-of), a "nothing material" statement on a quiet day, and a market-context line with source +
as-of.

### Tests for User Story 2 ⚠️ (write first, confirm FAIL)

- [X] T022 [P] [US2] News assemble test in `backend/tests/brief/test_assemble_news.py` — held + watched ticker mapping, since-last-delivered-record window (widening across gaps, Decision 7), empty ⇒ "nothing material" (US2 AC2), budget-cap degrade-to-template path (edge case).
- [X] T023 [P] [US2] Market-context assemble test in `backend/tests/brief/test_assemble_market_context.py` — regime + market-events summary carries a concrete verdict, source, and as-of (US2 AC3), never a bare "Unknown".
- [X] T024 [P] [US2] News + market-context render test in `backend/tests/brief/test_render_news.py` — section renders deterministically, each item shows source + as-of, quiet-day copy present, still no directive language.

### Implementation for User Story 2

- [X] T025 [US2] Implement the news section in `backend/src/brief/assemble.py` — reuse feature-014 `sentiment/composite.py` + captured store + `api/sentiment.generate_and_capture` over held + watched tickers; compute the window from the last delivered record (`brief_store`); populate `list[NewsItem]` with source + as-of; degrade to template on budget cap.
- [X] T026 [US2] Implement the market-context line in `backend/src/brief/assemble.py` — reuse `regime/calculator.current_regime_response()` + `events/service.EventsService` → `MarketContextLine` with source + as-of.
- [X] T027 [US2] Extend `backend/src/brief/render.py` to render the news + market-context sections (including the "nothing material" fallback) and fold their as-of dates into the brief-level `data_as_of`.

**Checkpoint**: US1 + US2 both work; the email now carries status + news + market context.

---

## Phase 5: User Story 3 - Five clear recommendations (Priority: P3)

**Goal**: End the brief with exactly five prioritized, fact-grounded recommendations selected by
the deterministic rule-based ranker (attention → news/sentiment materiality → portfolio fill),
worded per the directive/neutral gating, each with the required disclosures.

**Independent Test**: Run the loop for an owner with holdings and news; confirm exactly five
priority-ordered items, each tied to a specific ticker or portfolio action with a one-line
fact-grounded reason; neutral framing when the carve-out is off (no directive verbs), direct
wording with citations when the carve-out holds.

### Tests for User Story 3 ⚠️ (write first, confirm FAIL)

- [X] T028 [P] [US3] Recommendation-ranking table test in `backend/tests/brief/test_recommend.py` — asserts precedence tiers, exactly-five (SC-003) regardless of portfolio size / news volume (US3 AC4), no fabricated signals (reasons grounded in brief facts), and deterministic `(severity desc, ticker asc)` tie-break (FR-013).
- [X] T029 [P] [US3] Recommendation render test in `backend/tests/brief/test_render_recommendations.py` — no-directive lint on the neutral path (SC-004, "candidate for review"/"consider reviewing", zero directive verbs); when carve-out ON, direct wording is allowed AND each item carries citation(s) + data_as_of + non-advice disclosure (FR-007).

### Implementation for User Story 3

- [X] T030 [US3] Implement the full ranker in `backend/src/brief/recommend.py` — replace the US1 baseline with the three documented-constant tiers (holdings-attention `risk/heat_breach` → `stop_proximity` → `stage_change`, then news/sentiment materiality over held→watched, then portfolio-level fill to exactly five), deterministic tie-break, `source_signal` tagged per item (data-model §RecommendationItem invariant).
- [X] T031 [US3] Implement recommendation wording in `backend/src/brief/render.py` gated by `brief_directive_enabled()` — neutral by default (FR-006), directive with citations when the carve-out holds (FR-007), never dropping the section (FR-007a).
- [X] T032 [US3] Wire recommendations + `directive` flag into `assemble.py`/`BriefModel` and record `directive` on the `BriefDeliveryRecord`; populate brief-level `citations` from the strategy registry for directive items.

**Checkpoint**: All three stories independently functional; the complete brief ships.

---

## Phase 6: Polish & Cross-Cutting Concerns (CI trigger, hardening, verification)

**Purpose**: The unattended trigger, secret hygiene, and full-suite/determinism verification.

- [X] T033 [P] Add the post-rebuild trigger step to `.github/workflows/daily-refresh.yml` — after a successful Factory-rebuild, call `POST /brief/run` with `SCREENER_OWNER_SECRET`, gated on the publish step's `published == 'true'` output (research Decision 3; `force_rebuild` ⇒ published=true); a brief-send failure is surfaced (FR-012) but MUST NOT fail/roll back the publish job.
- [X] T034 [P] Emit the `published` step output from the publish step (`publish_chain.ps1` guard outcome) so the trigger step can distinguish a real publish from a guard `noop` — per research Decision 3.
- [X] T035 [P] Add the CI-automation test in `backend/tests/automation/test_brief_trigger.py` — idempotency across a re-triggered session (FR-010) and non-trading-day skip (FR-011, SC-008), mirroring the feature-011 automation tests.
- [X] T036 [P] Verify `scripts/secret_scan.ps1` stays clean and confirm no `SCREENER_BRIEF_*` secret or app password is written to any artifact or logged in plaintext (FR-015).
- [X] T037 Run the full backend suite from repo root (`py -3.12 -m pytest backend/tests/brief backend/tests/contract backend/tests/automation` plus the existing suites) — all green, zero silent skips; assert same snapshot + portfolio ⇒ identical `content_hash` (SC-005).
- [X] T038 [P] Walk `specs/018-daily-portfolio-brief/quickstart.md` manual verification (local dry-run, `GET /brief/status`, disable path) and note the optional in-app enable/disable + last-run status control (reuses settings blob + `GET /brief/status`).
- [X] T039 [P] Update the active-feature pointer in `CLAUDE.md` and add/refresh the relevant deploy memory (HF Space runtime secrets `SCREENER_BRIEF_*`, code-only `force_rebuild` deploy).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **User Stories (Phases 3–5)**: All depend on Foundational. US1 is the MVP; US2 and US3
  build on the assemble/render surface US1 establishes but are independently testable. Follow
  priority order P1 → P2 → P3 for a single implementer.
- **Polish (Phase 6)**: Depends on the user stories being complete (T033–T035 need the working
  `POST /brief/run`).

### User Story Dependencies

- **US1 (P1)**: Only Foundational. Delivers the status email end-to-end (uses the baseline
  fill-to-five so the exactly-five invariant holds before US3).
- **US2 (P2)**: Foundational; extends `assemble.py`/`render.py`. Independently testable via the
  news + market-context sections.
- **US3 (P3)**: Foundational; replaces the US1 baseline ranker and adds directive wording.
  Reuses US1's attention list and US2's news signals for its top tiers.

### Within Each User Story

- Tests (T014–T016, T022–T024, T028–T029) are written FIRST and must FAIL before implementation.
- `assemble.py` (data) before `render.py` (presentation) before router wiring.
- Story complete before moving to the next priority.

### Parallel Opportunities

- Setup: T002, T003 in parallel.
- Foundational: T004, T005, T006, T008, T010, T012 in parallel (distinct files); T007/T009/T011
  follow their tests; T013 last (registers router).
- Within a story, the `[P]` test tasks run together; implementation tasks touching the same file
  (`assemble.py`, `render.py`) are sequential.
- Polish: T033–T036, T038, T039 largely parallel; T037 after the suite is stable.

---

## Parallel Example: User Story 1

```bash
# Write US1 tests together (all must FAIL first):
Task: "Portfolio-section assemble test in backend/tests/brief/test_assemble_portfolio.py"
Task: "Renderer determinism + disclosures test in backend/tests/brief/test_render_portfolio.py"
Task: "End-to-end run test in backend/tests/brief/test_brief_run_us1.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational (endpoints, models, store, email edge, gating).
2. Phase 3 US1 → **STOP and VALIDATE**: enable the flag, dry-run `/brief/run`, confirm the
   status email content + determinism + empty-portfolio path.
3. Deploy via the existing Daily Refresh workflow (`force_rebuild=true`) — MVP shippable.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → deterministic status email (MVP).
3. US2 → add news + market context.
4. US3 → add the five ranked recommendations + directive carve-out.
5. Polish → wire the CI trigger, harden secrets, verify determinism end-to-end.

---

## Notes

- No new screening rule, gate, indicator, citation, sizing model, or backtest baseline (FR-002)
  — the brief is pure synthesis + delivery over existing outputs (research Decision 8).
- `brief_enabled()` default OFF ⇒ `POST /brief/run` 404s, CI step is a no-op, no email — byte
  identical to feature 017 until turned on.
- Determinism: `generated_at` is the only field excluded from `content_hash`; everything else is
  a pure function of snapshot + portfolio (FR-013/SC-005).
- Secrets (`SCREENER_BRIEF_*`, app password, recipient) are runtime env only — never committed,
  never logged (FR-015); secret scan must stay clean.
- Idempotency is keyed on the target session, so at-most-once holds even if `brief_runs.json`
  is ephemeral across a factory rebuild (research Decision 2).
