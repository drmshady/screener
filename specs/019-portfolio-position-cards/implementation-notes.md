# Implementation Notes — Feature 019 (Portfolio Position Cards & Transaction Separation)

Living "resume here" doc for future implementation sessions. Complements `tasks.md`
(the authoritative task list) and `plan.md` (design). Updated 2026-07-18.

---

## 1. Working copy & environment (READ FIRST)

- **Canonical working copy: `C:\screener`** (SSD). Use this. It holds the only working
  virtualenv and all Phase 1–2 work.
- `E:\screener` is a **redundant, retired** copy on a slow USB flash drive. Do not edit it.
  It also contains a broken `.venv312/` (bad base interpreter) and a `.venv/` missing backend
  deps. Safe to delete once no session is running from it.
- **Backend interpreter:** `C:\screener\.venv\Scripts\python.exe` — this is the **only**
  interpreter with backend deps installed (pydantic 2.13.4, fastapi, pytest, hypothesis,
  schemathesis). Run all backend tests / import checks with it.
- Both copies were on commit `a7da2c7`, branch `019-portfolio-position-cards`. If you ever
  need to reconcile drives again, the divergence is working-tree only.

## 2. Phase status

| Phase | Tasks | Status |
|-------|-------|--------|
| 1 — Setup | T001–T003 | ✅ Done (see notes in `tasks.md`) |
| 2 — Foundational | T004–T005 | ✅ Done (this doc §4) |
| 3 — US1 (position card) | T006–T014 | ⏭️ **Next**: write RED tests T006–T008 first |
| 4 — US2 (transactions page split) | T015–T018 | ⬜ Not started |
| 5 — US3 (closed positions drop off) | T019–T020 | ⬜ Not started |
| 6 — US4 (realized summary) | T021–T023 | ⬜ Not started |
| 7 — Polish | T024–T027 | ⬜ Not started |

Feature is **presentation/synthesis only** — must preserve byte-identical compute paths
(FR-013). One new pure backend module (`instruction.py`, still to write in T009), one additive
response field (done in T005), a frontend page split, and two new components.

## 3. Known test baseline (do NOT chase these locally)

Backend suite on a clean local checkout: **707 passed / 2 skipped / 8 failed + 1 collection
error**. All 9 failures share **one root cause**: the baked local snapshot `data_as_of` is
stale (`2026-06-18`), so `run_strategy("midterm_52w_high_momentum")` returns **0 candidates**.
This is **not a code bug** and **not introduced by 019**.

- Collection error: `backend/tests/contract/test_openapi.py` — `_live_candidate_ticker()`
  does `result.candidates[0].ticker` at import time → `IndexError` on an empty screen.
- Failing (stale-window assertions): `tests/integration/test_perf.py`,
  `tests/validation/test_midterm_backtest.py`, `test_midterm_gate_mode.py`,
  `test_midterm_modifications.py` (×2), `test_midterm_reference_tickers.py` (×2),
  `test_surface_sweep_api.py`.

**Fresh data comes from CI, not locally.** The GitHub Actions `daily-refresh.yml` cron runs
`scripts/publish_chain.ps1` to refresh + rebuild the snapshot image. To green these locally,
trigger it (Actions → *Run workflow*, or `gh workflow run "Daily Refresh & Deploy"`); a
`force_rebuild` dispatch does a code-only redeploy. Do not treat the 8+1 as regressions.

## 4. Phase 2 API surface added (for Phase 3 wiring)

**`backend/src/lib/flags.py`**
- `_single_owner_directive_carveout()` — private shared predicate: not multi-user AND
  `hosting.owner_secret()` set AND `SCREENER_PERSONAL_USE_DIRECTIVE` truthy.
- `brief_directive_enabled()` (feature 018) now delegates to it — behavior unchanged.
- `card_directive_enabled()` (feature 019) — gate for the card verb. **T010 sets the
  response `directive_enabled` from this.** Default `False`.

**`backend/src/models/portfolio.py`**
- `InstructionInputs`: `level_status: str`, `distance_to_stop_pct: float|None`,
  `heat_headroom_pct: float|None`, `stage: str|None`.
- `InstructionBlock`: `status_label: str` (always), `directive: "hold"|"trim"|"sell"|None`,
  `rationale: str`, `inputs: InstructionInputs`.
- `PortfolioHolding.instruction: InstructionBlock | None = None` (additive).
- `PortfolioHoldingsResponse.directive_enabled: bool = False` (additive, top-level).

## 5. Reused building blocks captured in Phase 1 (for the mapper, T009/T010)

- `LevelBlock.status ∈ {holding, stop_breached, target_reached, gains_protected, insufficient_data}`
- `LevelBlock.levels_state ∈ {ok, insufficient_data}`; `LevelBlock.distance_to_stop_pct: float|None`
- `PortfolioTotals.heat_headroom_pct: float` (and `heat_ceiling_pct`)
- `compute_realized_pnl(transactions) -> RealizedPnl` (`backend/src/portfolio/pnl.py`)
- `_assemble_holdings(...)` in `backend/src/api/portfolio.py` — the wiring point for T010.
- Constants for `derive_instruction` (T009): near-level `0.03`, `flags.portfolio_heat_ceiling()`.
  **No new indicator/threshold** — synthesis over existing numbers only (FR-007/FR-013).
- Precedence for `derive_instruction`: **Sell** (`current_condition.status == "stop_breached"`)
  → **Trim** (`|distance_to_stop_pct| <= 0.03` OR `heat_headroom_pct <= 0`) → **Hold**
  (healthy / target_reached / gains_protected) → **levels-unavailable** (`levels_state ==
  "insufficient_data"` → no verb, `status_label` only).
- AI sentiment score is **context only, never an input** to the instruction (FR-007; T007 enforces).

**Frontend** (Phase 1 capture): data flow is `frontend/src/app/portfolio/page.tsx` →
`syncFromServer` → `fetchHoldings`/`recordTransactions`/`deleteTransaction` in
`frontend/src/lib/api.ts`; holdings validated by `PortfolioHoldingsResponseSchema`. Reusable
components: `ImportTransactions.tsx`, `SentimentReport.tsx` (origin `"holding"`),
`EventsBadge.tsx`, `cockpit/PipelineStageBadge.tsx`.

## 6. Deployment (why local staleness is fine)

- Backend = FastAPI + a **read-only data snapshot baked into a Docker image**; the host runs
  no ingest. Image → GHCR (`ghcr.io/drmshady/screener:latest`); live host is a Hugging Face
  Space (`publish_chain.ps1 -SpaceId … -Deploy`). `render.yaml` is the alternate/legacy Render
  config. Runs `SCREENER_HOSTED_MODE=1`.
- Data advances via the `daily-refresh.yml` Actions cron (session guard → refresh →
  integrity check → secret-scan → build → push → deploy), with abort-before-publish keeping the
  last-good snapshot live. After a real publish it fires the feature-018 daily brief.
- Frontend = separate (Vercel + NextAuth Google BFF proxy, feature 010).
- **Directive carve-out** rides `_single_owner_directive_carveout()`: hosted mode does NOT
  force it off (unlike `personal_use_directive()`), because the owner-secret access gate proves
  output reaches only the owner. Neutral status is the default; the instruction section is
  never dropped (FR-008).

## 7. Resume checklist for Phase 3 (US1)

1. Open a session rooted at `C:\screener`.
2. Write **RED** tests first: T006 (`backend/tests/portfolio/test_instruction.py`),
   T007 (`…/test_instruction_determinism.py`), T008
   (`backend/tests/api/test_portfolio_holdings_instruction.py`). Run with
   `C:\screener\.venv\Scripts\python.exe -m pytest`.
3. Implement `backend/src/portfolio/instruction.py` `derive_instruction` (T009), then wire it
   into `_assemble_holdings` + set `directive_enabled` (T010).
4. Frontend: extend the schema (T011), build `PositionCard.tsx` (T012) + tests (T013), render
   the grid (T014). Watch the shared-file edits on `portfolio/page.tsx` (T014/T017/T020/T023 —
   sequence, don't parallelize).
