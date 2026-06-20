---
description: "Task list for feature 011 — Automated Daily Refresh, Realistic Risk Levels & Smarter Sizing"
---

# Tasks: Automated Daily Refresh, Realistic Risk Levels & Smarter Sizing

**Input**: Design documents from `specs/011-auto-refresh-risk-sizing/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — the plan, quickstart, and contracts mandate test-first
property tests (FR-007/008/009/010/012), risk + fair-value sizing tests
(FR-013–017), a fair-value golden-fixture test (FR-018, Principle IV), the
method-comparison regeneration test (FR-019), and the automation guard/abort tests.
Per the constitution's Test-First-for-Financial-Logic principle, every test task
MUST be written and MUST FAIL before its implementation task lands.

**Organization**: Grouped by user story. US1 (automation) is fully independent.
US2 (levels) → US3 (sizing, depends on US2's stop + the fair-value estimate). US4
(comparison harness) chooses the numeric defaults for US2/US3 and gates the
one-time backtest re-baseline.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4 (Setup, Foundational, Polish carry no story label)
- Exact file paths are included in every task.

## Path Conventions

Web app: `backend/src/`, `backend/tests/`, `frontend/src/`, plus CI automation at
repo root (`.github/workflows/`, `scripts/`, `tools/`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Configuration plumbing and scaffolding all stories build on.

- [X] T001 [P] Add documented, env-overridable config readers in `backend/src/lib/flags.py` for the new level/sizing knobs — `risk_distance_atr_lo`, `risk_distance_atr_hi`, `reward_ceiling_z`, `reward_ceiling_use_fair_value` (bool), `risk_per_trade_fraction` (`f`) — each with a documented default + range comment, following the existing flag-reader idiom. Reuse the existing `take_profit_r_multiple`. Placeholder defaults (to be finalized by US4/T035).
- [X] T002 [P] Create the `tools/` directory with an empty `tools/__init__.py` and a `tools/README.md` stub describing the FR-019 method-comparison harness (filled in US4).
- [X] T003 [P] Create `.github/workflows/` directory and add a `.github/workflows/.gitkeep` (the daily-refresh workflow lands in US1/T009).

**Checkpoint**: Config knobs and target directories exist; no behavior changed yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared response-model fields and the shared level helper that US2 and
US3 both depend on. **No user-story implementation may begin until this completes.**

**⚠️ CRITICAL**: Blocks US2, US3, US4.

- [X] T004 Extend the level response model in `backend/src/models/strategy.py` with the new metadata fields from data-model.md — `risk_distance`, `reward_distance`, `reward_ceiling_basis` (enum), `bounds_applied` (list), `levels_state` (enum `ok`|`insufficient_data`), `rationale` (str) — all optional/backward-compatible so existing `entry`/`stop_loss`/`tighter_stop_loss`/`take_profit` consumers keep working.
- [X] T005 [P] Extend `SizingRequest`/`SizingResponse` in `backend/src/models/portfolio.py`: request gains `stop_loss` and the optional conviction inputs (`fair_value` + `trust_flag`, and/or the inverse-vol / strategy-rank inputs the adopted signal needs); response gains `risk_per_trade_target`, `risk_per_share`, `conviction_signal` (enum), `conviction_adjustment` (enum|null), `binding_constraint` (enum), `caps_respected` (bool), `conviction_used` (bool), `reasoning` (str) per data-model.md.
- [X] T006 [P] Add a `FairValueEstimate` shape (`fair_value`, `basis`, `source_as_of`, `provenance`, `trust_flag`, `margin_of_safety`) in `backend/src/models/strategy.py` (or `provenance.py`) per data-model.md, with the trust-flag enum (`trusted`|`unavailable`|`stale`|`out_of_range`).
- [X] T007 Create a shared, pure level-derivation helper module `backend/src/strategies/levels.py` exposing a `derive_bounded_levels(...)` function signature (no logic yet — raises/returns insufficient_data stub) so both `midterm_52w_high_momentum.derive_levels` and `midterm_value_composite.derive_levels` can delegate to one implementation in US2. Document the contract from `contracts/risk-levels.md` in the docstring.

**Checkpoint**: Models carry the new fields; the shared level helper seam exists. Stories can now proceed.

---

## Phase 3: User Story 1 - Fresh hosted data every trading day, no manual steps (Priority: P1) 🎯 MVP

**Goal**: Move the manual `scripts/publish.ps1` chain into an unattended GitHub
Actions cron so the hosted `data_as_of` advances every trading day with zero owner
action; abort-before-publish on any failure; idempotent no-op on non-trading days.

**Independent Test**: Trigger `workflow_dispatch`; the Space rebuilds and hosted
`data_as_of` advances. A weekend run logs a no-op. A deliberately broken step
aborts before publish, leaves the last snapshot live, and notifies the owner.

### Tests for User Story 1 ⚠️ (write first, must FAIL)

- [X] T008 [P] [US1] Add an automation-guard test in `backend/tests/automation/test_daily_refresh_guard.py` asserting the new-session resolver returns a no-op decision when the latest completed trading session is not newer than the published `data_as_of` (non-trading-day / no-new-session → no build/push), and a proceed decision when it is newer (FR-005, contract `daily-automation.md`).

### Implementation for User Story 1

- [X] T009 [US1] Add `.github/workflows/daily-refresh.yml` — scheduled cron after the US close on weekdays (UTC) + `workflow_dispatch`; steps in order: new-session guard → `python scripts/ingest_daily.py` (incremental only) → data-integrity harness (`scripts/run_integrity_harness.py`) → secret scan (`scripts/secret_scan.ps1`) → docker build (only if snapshot changed) → push GHCR → HF Factory-rebuild (`POST .../restart?factory=true`). Secrets referenced ONLY via `${{ secrets.* }}`. Abort-before-publish on any failed step (FR-001/002/003, contract `daily-automation.md`).
- [X] T010 [US1] Refactor `scripts/publish.ps1` to factor the shared publish steps (guard → ingest_daily → integrity → secret-scan → build → push → factory-rebuild) into one codepath the workflow and local runs both invoke, so CI and local don't drift (research Decision 5). Keep `-FullStooq` (heavy bundle) OFF the daily path.
- [X] T011 [US1] Implement the trading-day / new-session guard helper (used by T009/T010) that resolves the latest completed session from the existing calendar and compares it to the published `data_as_of`, short-circuiting the whole pipeline on no-new-session (FR-005). Place it where the publish chain can import it (e.g. `scripts/ingest_daily.py` or a small `scripts/_session_guard.py`); satisfy T008.
- [X] T012 [US1] Wire the failure-notification path in `.github/workflows/daily-refresh.yml` (Actions failure notification / email to the owner) that fires on any aborted step with the failing-step detail (FR-004), and confirm a successful run advances `data_as_of` while a no-op leaves it unchanged.
- [X] T013 [P] [US1] Add CI efficiency: enable pip + docker layer caching in the workflow and gate the image rebuild on the snapshot actually having changed (research Decision 5 efficiency clause); document the separate, infrequent Stooq-bundle job (`workflow_dispatch`/quarterly) in `tools/README.md` or a workflow comment.

**Checkpoint**: US1 is independently shippable — the hosted instance self-refreshes daily with safe failure handling, untouched by US2/US3.

---

## Phase 4: User Story 2 - Realistic stop-loss and take-profit (Priority: P1)

**Goal**: Replace the unbounded `take_profit = entry + R·(entry − stop)` with a
bounded, volatility-/horizon-aware derivation (clamped risk distance + reward
ceiling), an `insufficient_data` fallback, and a neutral rationale — shared by both
mid-term strategies. **Screening rules/gates/citations unchanged.**

**Independent Test**: On a real snapshot, 100% of candidates show
`0 < stop_loss < entry < take_profit` within the documented bounds, 0 targets beyond
the ceiling; a far-below-SMA-200 name gets a bounded risk distance; recompute is
byte-identical; each candidate carries a zero-directive rationale.

### Tests for User Story 2 ⚠️ (write first, must FAIL)

- [ ] T014 [P] [US2] Property test in `backend/tests/strategies/test_levels_realism.py`: across a real frozen snapshot, every `levels_state == "ok"` row satisfies `0 < stop_loss < entry < take_profit`, `risk_distance ∈ [lo·atr, hi·atr]`, `reward_distance` within bound, `take_profit ≤ reward ceiling` (FR-007/008/009, SC-003).
- [ ] T015 [P] [US2] Test in `backend/tests/strategies/test_levels_realism.py` (or a sibling) for the far-below-SMA-200 case (Acceptance #2): a name whose 200-day line sits far below price yields a clamped risk distance, not a blown-up R-multiple target.
- [ ] T016 [P] [US2] Test for the insufficient-data fallback in `backend/tests/strategies/test_levels_insufficient.py`: missing ATR / SMA-200 / swing-low → `levels_state == "insufficient_data"` with `stop_loss == take_profit == None`, never a degenerate number (FR-010).
- [ ] T017 [P] [US2] Determinism + rationale test in `backend/tests/strategies/test_levels_determinism.py`: recompute on a fixed row is byte-identical (FR-012/SC-006) and the `rationale` is present, names the stop rule + binding ceiling, and contains zero directive language (FR-011, Acceptance #4).

### Implementation for User Story 2

- [ ] T018 [US2] Implement `derive_bounded_levels(...)` in `backend/src/strategies/levels.py` per `contracts/risk-levels.md`: entry = close; existing technical stop then clamp `risk_distance` into `[lo·atr, hi·atr]` + low-price fraction cap (`stop_loss > 0`); `take_profit = entry + R·risk_distance` capped at the reward ceiling = `min(volatility_horizon_limit, fair_value_if_trusted, measured_move_if_used)` recording `reward_ceiling_basis` and `bounds_applied`; `insufficient_data` state on missing inputs; build the neutral rationale. Pure + deterministic. Satisfies T014–T017.
- [ ] T019 [US2] Repoint `derive_levels` in `backend/src/strategies/midterm_52w_high_momentum.py` (currently L477) to delegate to `derive_bounded_levels`, passing the optional trusted fair-value estimate (None for now until US3 supplies it). Keep the existing return keys; add the new metadata. **Do not touch `rules()`/gates/citation.**
- [ ] T020 [US2] Repoint `derive_levels` in `backend/src/strategies/midterm_value_composite.py` (currently L415) to the same shared helper so both mid-term strategies derive realistic levels identically. Selection logic unchanged.
- [ ] T021 [US2] Surface the new level metadata through `backend/src/api/analyze.py` (and any compare endpoint that returns levels) without changing the route shape — the response gains fields, existing consumers keep working; confirm `data_as_of` + `disclaimer` still ride every response.

**Checkpoint**: Both mid-term strategies emit bounded, rationale-carrying levels; suite green; selection output unchanged.

---

## Phase 5: User Story 3 - Smarter, fair-value-aware position sizing (Priority: P2)

**Goal**: Replace cap-fill `size_position` with risk-per-trade sizing (capital
fraction risked to the US2 stop) as the backbone, modulated by the **US4-adopted
conviction signal** (fair-value margin of safety / inverse-volatility /
strategy-rank / none — fair value is one candidate, not assumed), still
hard-bounded by the per-position/per-sector caps, failing open when the adopted
modulator's input is unavailable.

**Independent Test**: With fixed capital + caps, size decreases as the stop widens
and (where fair value is available) as the discount-to-fair-value shrinks; no
suggestion ever breaches a cap; missing fair value falls back without error; every
result names its binding constraint with zero directive language.

### Tests for User Story 3 ⚠️ (write first, must FAIL)

- [ ] T022 [P] [US3] Golden-fixture test for the adopted fair-value model in `backend/tests/indicators/test_fair_value.py` — exact numeric output on fixed point-in-time inputs (Principle IV, test-first), plus trust-flag transitions: present/fresh/in-range → `trusted`; missing → `unavailable`; old as-of → `stale`; implausible/negative → `out_of_range` (FR-018, contract `fair-value.md`).
- [ ] T023 [P] [US3] Risk-target sizing test in `backend/tests/portfolio/test_sizing_risk.py`: `target_shares = floor(f·capital / (entry − stop_loss))`; two candidates identical except a wider stop → the wider-stop one is sized strictly smaller (FR-013, SC-004).
- [ ] T024 [P] [US3] Cap hard-bound test in `backend/tests/portfolio/test_sizing_caps.py`: no suggestion breaches the per-position or per-sector cap (incl. the cap-binds-tighter-than-risk case → cap wins, `binding_constraint` reflects it); the existing zero-room "cannot size without breaching cap" branch is preserved (FR-014, SC-004).
- [ ] T025 [P] [US3] Conviction-modulation + fail-open test in `backend/tests/portfolio/test_sizing_modulation.py`, parameterized over the candidate modulators: for fair value, trusted deeper-discount candidate sized ≥ the otherwise-identical smaller-margin one (Acceptance #3); for inverse-vol, lower-vol sized ≥ higher-vol; for strategy-rank, higher-rank sized ≥ lower-rank; in all cases a missing/untrusted modulator input → risk-based-within-caps, `fair_value_used`/modulation flag `false`, no error (FR-015/016, SC-005); deterministic; rationale zero-directive and names the binding constraint (FR-017).

### Implementation for User Story 3

- [ ] T026 [US3] Implement the candidate fair-value estimate as a pure function in `backend/src/indicators/fair_value.py` (new computed model — e.g. Graham number / earnings-power / residual income, per US4 selection) consuming `FundamentalsLoader.value_metrics_as_of` inputs (`backend/src/data/fundamentals.py:259`) + close; returns the `FairValueEstimate` shape with provenance/citation + trust flag; `None`/`unavailable` when inputs missing. Satisfies T022. (Needed because fair value is a candidate modulator AND can feed the US2 reward ceiling; if US4 instead adopts basis (a) valuation-yields, implement that mapping here using `backend/src/indicators/valuation.py`. If US4 adopts a non-fair-value modulator, this still ships for the reward-ceiling option but may be unused by sizing.)
- [ ] T027 [US3] Implement `size_position` v2 in `backend/src/portfolio/sizing.py` (currently L13) per `contracts/sizing.md`: risk-per-trade target → the **US4-adopted conviction modulation** (fair value / inverse-vol via existing volatility inputs / strategy-rank / none), applied only when its input is trusted → cap clamp via existing `backend/src/portfolio/exposure.py` `aggregate_exposure` (never breach) → fail-open → set `binding_constraint` + neutral `reasoning`. Keep the modulator behind the config flag so the chosen one is the default but the others remain reproducible. Satisfies T023–T025.
- [ ] T028 [US3] Wire the fair-value estimate into the screen/analyze path so `derive_bounded_levels` (T018) receives a trusted fair value for the reward ceiling AND `size_position` receives `fair_value` + `trust_flag` — via `backend/src/api/analyze.py` / `backend/src/api/portfolio.py`. Confirm fail-open when the estimate is untrusted.
- [ ] T029 [US3] Surface fair-value + trust flag and the sizing binding-constraint/rationale through `backend/src/api/portfolio.py` response without changing the route shape; `data_as_of` + `disclaimer` preserved.

**Checkpoint**: Sizing is risk- and value-aware, caps never breached, fail-open verified; US1+US2+US3 all independently functional.

---

## Phase 6: User Story 4 - Investigation & honest validation before adopting any default (Priority: P3)

**Goal**: A deterministic, frozen-snapshot comparison harness that reports
per-method realism/robustness/coverage + the backtest-baseline delta, justifies
each adopted default, and gates the one-time controlled backtest re-baseline.

**Independent Test**: Run the harness on a frozen snapshot → it reports per-method
metrics + the selected default + the backtest delta deterministically; re-run yields
identical bytes; shipped defaults equal the artifact's `selected_default`.

### Tests for User Story 4 ⚠️ (write first, must FAIL)

- [ ] T030 [P] [US4] Regeneration test in `backend/tests/tools/test_compare_methods.py`: the harness regenerates byte-identically on the frozen snapshot (SC-007), the report contains a populated `backtest_baseline_delta` section, and it flags when shipped defaults diverge from `selected_default` (FR-019, contract `method-comparison.md`).
- [ ] T031 [P] [US4] Modeled-exit determinism test in `backend/tests/backtests/test_modeled_exits.py`: level-driven intrabar exits (stop-checked-before-target, gap-at-open handling) are deterministic on a fixed snapshot and preserve point-in-time inputs (FR-020, research Decision 4) — written before the runner change.

### Implementation for User Story 4

- [ ] T032 [US4] Implement level-driven modeled exits in `backend/src/backtests/runner.py`, **behind a flag/param defaulting OFF**, that walk each holding bar-by-bar exiting on the US2 stop/target (stop before target intrabar; gap-fills at open; else horizon exit as today). Deterministic, point-in-time preserved. Satisfies T031. Old fixed-horizon baseline stays the default until the gated re-baseline (T038).
- [ ] T033 [US4] Implement the comparison harness `tools/compare_methods.py` (CLI `--snapshot <frozen-id>`) emitting the deterministic report per `contracts/method-comparison.md`: per-method realism (degenerate rate, risk/reward distance distributions vs price/ATR/horizon, over-ceiling count; for sizing: size dispersion, cap-bind rate, wider-stop→smaller monotonicity), robustness, fair-value coverage/trust rate, **a head-to-head of the candidate sizing-conviction modulators (fair value / inverse-vol / strategy-rank / none)**, `backtest_baseline_delta` (using T032), and `selected_default` per dimension. Satisfies T030.
- [ ] T034 [US4] Run `tools/compare_methods.py` on a frozen snapshot and record the chosen defaults — risk-distance band `[lo,hi]·ATR`, `reward_ceiling_z`, R-multiple, fair-value basis (a vs b), `risk_per_trade_fraction` `f`, **the adopted sizing-conviction modulator**, and its modulation curve — into the artifact + `research.md` Decision 6 (replace the provisional values).

**Checkpoint**: The artifact exists, is reproducible, and justifies every default; the modeled-exit machinery is ready but not yet baselined.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Adopt the justified defaults, perform the gated re-baseline, finish the
frontend surfaces, and verify all guarantees.

- [ ] T035 Apply the US4-justified numeric defaults to `backend/src/lib/flags.py` (T001 placeholders → final values) and confirm shipped defaults equal the artifact's `selected_default` (T030 catches divergence).
- [ ] T036 [P] Render the per-candidate level rationale + fair-value estimate + trust flag in the relevant `frontend/src/components/` candidate view (neutral, zero-directive); ensure `data_as_of`/`disclaimer` stay rendered.
- [ ] T037 [P] Render the sizing binding-constraint rationale in the `frontend/src/components/` sizing view (zero-directive), and EXTEND the Playwright no-directive lint to cover the new level + sizing copy; add a Vitest rationale-rendering test under `frontend/tests/`.
- [ ] T038 **GATED re-baseline (FR-020)** — ONLY if the T033/T034 artifact shows the level-driven modeled exits are an improvement: run `python backend/src/backtests/runner.py --strategy midterm_52w_high_momentum` with modeled exits enabled, commit the regenerated `backend/data/backtests/*.json` + `backend/backtests/<slug>/*` as a deliberate one-time re-baseline, with the constitution reproducibility re-check noted in the commit message. If NOT an improvement, keep the old baseline and record that decision. Never silent.
- [ ] T039 [P] Update `quickstart.md` Decision-6 references and `CLAUDE.md`/`MEMORY.md` if the adopted fair-value basis or defaults changed materially; ensure the SPECKIT pointer still targets this plan.
- [ ] T040 Run the full suites from repo root — `py -3.12 -m pytest backend` and `cd frontend; npm.cmd run test; npm.cmd run test:e2e` — and confirm SC-003 (100% non-degenerate levels within bounds, 0 over-ceiling), SC-004 (wider-stop→smaller, no cap breach), SC-005 (fail-open), SC-006 (byte-identical recompute), SC-008 (green suites incl. value tests, `data_as_of`+`disclaimer` everywhere, zero directive language, no secret in repo/artifact).
- [ ] T041 Run `scripts/secret_scan.ps1` and confirm no secret appears in the repo, the workflow YAML, or any baked artifact (FR-002a/006, SC-008); confirm hosted directive mode stays forced OFF (FR-021).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS US2/US3/US4 (US1 only needs T003).
- **US1 (Phase 3)**: Independent — needs only Setup (T003). Can run fully in parallel with everything else.
- **US2 (Phase 4)**: Needs Foundational (T004, T007).
- **US3 (Phase 5)**: Needs Foundational (T005, T006) AND US2's stop (T018) — the realistic stop feeds risk-per-share. Fair value (T026) feeds both US3 sizing and the US2 reward ceiling (T018 accepts it optionally; T028 wires it).
- **US4 (Phase 6)**: Needs US2 (T018) + US3 (T027) implemented to compare them, and the modeled-exit runner (T032).
- **Polish (Phase 7)**: T035 needs US4 (T034). T038 is gated on T033/T034. T040/T041 need all stories.

### User Story Dependencies

- **US1 (P1)**: No dependency on US2/US3/US4 — the MVP, deliverable on its own.
- **US2 (P1)**: Independent of US1; precedes US3.
- **US3 (P2)**: Depends on US2 (stop) + the fair-value estimate.
- **US4 (P3)**: Depends on US2 + US3 to evaluate them; gates the re-baseline.

### Within Each User Story

- Tests are written first and MUST FAIL before implementation (constitution Principle IV).
- Models/helpers before services; services before endpoints; core before frontend wiring.

### Parallel Opportunities

- Setup: T001, T002, T003 all [P].
- Foundational: T005, T006 [P] (different model concerns); T004 + T007 sequential-ish but distinct files.
- **US1 can be built entirely in parallel with US2** by a second contributor once Setup is done.
- US2 tests T014–T017 all [P]; US3 tests T022–T025 all [P]; US4 tests T030–T031 [P].
- Frontend polish T036, T037 [P].

---

## Parallel Example: User Story 2 tests

```bash
# Write all US2 level tests together (they must fail first):
Task: "Property realism test in backend/tests/strategies/test_levels_realism.py"
Task: "Far-below-SMA-200 clamp test in backend/tests/strategies/test_levels_realism.py"
Task: "Insufficient-data fallback test in backend/tests/strategies/test_levels_insufficient.py"
Task: "Determinism + rationale test in backend/tests/strategies/test_levels_determinism.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup (T003 suffices for US1).
2. Phase 3 US1 → trigger `workflow_dispatch`, confirm `data_as_of` advances, confirm weekend no-op + failure-abort+notify.
3. **STOP and VALIDATE** — the hosted instance now self-refreshes daily. Shippable on its own.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → independently testable → ship (removes the manual publish chore).
3. US2 → bounded levels, suite green → ship.
4. US3 → risk + fair-value sizing on top of US2 → ship.
5. US4 → comparison artifact justifies defaults → apply T035 → **gated** re-baseline T038.
6. Polish/verify (T040/T041) → all SCs confirmed.

### Notes

- [P] = different files, no incomplete-task dependency.
- The backtest re-baseline (T038) is the one Complexity-Tracking item — gated, explicit, never silent.
- No screening rule, gate, ranking, or citation changes anywhere (FR-022, Out of Scope).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
