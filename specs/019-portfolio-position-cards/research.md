# Phase 0 Research: Portfolio Position Cards & Transaction Separation

All Technical Context items are resolved from the existing codebase; there are **no**
NEEDS CLARIFICATION items. Decisions below record the reuse strategy and the one genuinely
new piece of logic (the instruction mapper).

## Decision 1 — Where the Hold/Trim/Sell instruction is computed

**Decision**: A new **pure backend module** `backend/src/portfolio/instruction.py` exposing
`derive_instruction(facts) -> InstructionBlock`, surfaced as an **additive per-holding field**
on the existing `POST /portfolio/holdings` response. No new endpoint.

**Rationale**:
- FR-007 requires the call be deterministic and derived purely from existing rule-based signals
  (stop/target status, portfolio heat, lifecycle stage). A backend pure function is directly
  unit-testable with golden fixtures (Constitution IV) and inherits the app's determinism guarantee.
- The directive gate already lives backend (`lib/flags.py` + `hosting.owner_secret()`); computing
  the verb server-side keeps the carve-out enforcement in one authoritative place rather than
  re-deriving gating in the browser.
- `/portfolio/holdings` (via `_assemble_holdings`) already returns, per holding, the levels
  (`original_plan` / `current_condition` / `trailing`), risk, and unrealized P&L, plus portfolio
  `heat_headroom_pct` in `totals`. The instruction is a pure function of facts already in that
  response — mapping it there is zero extra data fetching.

**Alternatives considered**:
- *Frontend-only derivation* — rejected: duplicates the carve-out gating logic in TS, harder to
  golden-test, and risks drift from the backend's determinism contract.
- *A new dedicated `/portfolio/instruction` endpoint* — rejected: unnecessary round trip; the
  facts are already assembled in `/holdings`.

## Decision 2 — Instruction rule (deterministic mapping, no new indicator)

**Decision**: Map already-computed status facts to one of `hold` / `trim` / `sell` (verb) plus an
always-present neutral `status_label` and a plain-language `rationale`, using this precedence:

1. **Sell** — the current-condition stop is **breached** (`LevelBlock.status == "stop_breached"`).
2. **Trim** — a deteriorating-but-not-breached risk signal: near the stop
   (`|distance_to_stop_pct| <= NEAR_LEVEL_PCT`, the existing 3% threshold) **or** the portfolio
   heat ceiling is breached (`heat_headroom_pct <= 0`), i.e. reduce exposure.
3. **Hold** — a healthy position with no breach (default when levels are OK and nothing above fires;
   includes `target_reached`/`gains_protected`, which are non-directive "let it run / protected"
   states — surfaced in the rationale, still `hold`).
4. **Levels unavailable** — `levels_state == "insufficient_data"`: `status_label` states levels are
   unavailable, `directive` is omitted (no verb), and the card still renders (edge case, FR-004).

Thresholds reuse **existing** constants (the frontend's `NEAR_LEVEL_PCT = 0.03` and the backend
`portfolio_heat_ceiling()`); **no** new indicator, gate, or threshold is introduced (FR-013). The
AI sentiment score is **not** an input (FR-007).

**Rationale**: These are exactly the signals the spec names, and they already drive the current
holding-alerts banner and the pipeline attention list — the mapper consolidates them into one
call per card without inventing anything. Lifecycle **stage** (frontend-owned via
`PUT /portfolio/state`) refines the neutral `status_label` on the card (e.g. "Managing"), but the
verb is derived from breach/heat facts so it stays server-deterministic and independent of
browser-local stage state.

**Alternatives considered**: folding sentiment or a fit-score band into the verb — rejected by
FR-007 (sentiment is context only) and FR-013 (no new scoring).

## Decision 3 — Directive gating for the in-app card (constitution v1.2.0 carve-out)

**Decision**: Gate the Hold/Trim/Sell **verbs** behind the **same single-owner carve-out** feature
018 established — personal-use flag ON **and** owner-secret access gate enforced **and** not
multi-user — surfaced to the frontend as a top-level boolean on the `/holdings` response
(`directive_enabled`). When false, the card shows the neutral `status_label` only (FR-008). Reuse
the existing gate helper (`brief_directive_enabled()` logic) via a shared private predicate rather
than the hosted-force-OFF `personal_use_directive()`.

**Rationale**: The owner's deployment is hosted (feature 010) but single-user and access-gated, so
`personal_use_directive()` is force-OFF there and would suppress the very verbs the owner asked for.
The v1.2.0 carve-out (and its 018 implementation `brief_directive_enabled()`) exists precisely for
this single-owner-hosted case: output reaches only the owner's own screen behind the same
owner-secret allowlist. Card instructions meet those conditions identically. Keeping it separate
from `personal_use_directive()` ensures no third-party-reachable surface gains directive output.

**Alternatives considered**: reusing `personal_use_directive()` directly — rejected: it is
force-disabled in hosted mode, so the owner would never see the verbs on their own hosted instance.

## Decision 4 — Transactions page split (relocate, don't redesign)

**Decision**: Create `/transactions` and **move** (not rebuild) the existing Portfolio-page
transaction UI to it: `ImportTransactions`, the "Record a Transaction" form, the transaction
ledger table, the realized-trades detail, and the per-holding Remove controls. Add a Transactions
nav link and a Portfolio→Transactions link. The Portfolio page keeps only card review + the
realized summary. All three write paths (Sheet import, in-app record, delete) already converge on
the same server-owned `transactions` list via `syncFromServer`/`loadHoldings`, so returning to
Portfolio reflects changes immediately (US2 AC3) with no data-layer change.

**Rationale**: FR-001/FR-002 ask for relocation of unchanged controls; the split is a routing +
component-move exercise. Closed-position disappearance (US3) and the realized summary (US4) are
pure consequences of existing net-quantity aggregation and `compute_realized_pnl` — no new backend
"closed position" state is introduced (spec Assumptions).

**Alternatives considered**: a tab within one page — rejected: the spec explicitly wants separate
pages so Portfolio is reserved for current positions.

## Decision 5 — Auto sentiment per card without blocking the shell

**Decision**: Each open-position card **auto-loads** feature 014's sentiment/narrative (origin
`"holding"`) on Portfolio load via the existing `SentimentReport`/`/sentiment` pipeline, fetched
**lazily per card in the background** so the shell (cards, levels, status, instruction) is usable
immediately (SC-005, FR-006). Reuse feature 014's ~$5/month spend cap and its deterministic
source-only template degrade so a many-holding portfolio never exceeds budget or errors — a
capped card shows the template narrative, not a blank/error (edge case).

**Rationale**: The pipeline already captures narratives once into a fingerprint-keyed durable store
served back byte-identically and degrades to a template when the cap is reached, so "auto for every
holding" adds display timing, not budget risk. Background/lazy fetch keeps the decision surface
(levels + instruction) independent of narrative latency.

**Alternatives considered**: eager blocking fetch of all narratives before render — rejected by
SC-005; per-card click-to-load — rejected by FR-006 ("not gated behind a per-card click").

## Decision 6 — News/events + stage badge reuse

**Decision**: Cards render recent news/events via the existing `EventsBadge` (+ `/events`) with
source + as-of, and the lifecycle status via the existing `cockpit/PipelineStageBadge` (stage from
frontend-owned `PUT /portfolio/state`) combined with the level/breach status. Both degrade to an
explicit "nothing new"/"no data" statement rather than a blank section (FR-005, edge cases).

**Rationale**: Reuses shipped components and their graceful-degradation copy; no new data path.

## Summary of new vs reused

- **New**: `portfolio/instruction.py` (pure mapper + golden tests); additive `InstructionBlock` +
  `directive_enabled` on the `/holdings` response; a card-instruction directive predicate in
  `flags.py`; `/transactions` route; `PositionCard` + `RealizedSummary` components.
- **Reused unchanged**: aggregation, holding levels/risk, realized/unrealized P&L, sentiment
  pipeline + spend cap, events, pipeline stage badge, the owner-secret allowlist + BFF proxy, and
  the whole transaction write path.
