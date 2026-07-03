# Phase 0 Research: Momentum Cockpit

**Feature**: 016-momentum-cockpit | **Date**: 2026-07-03

All product decisions were settled during brainstorming (see spec Assumptions and the owner
decisions recorded in the plan). This file records the *technical* decisions — the choices
that shape the implementation — with rationale and rejected alternatives. There are no
outstanding NEEDS CLARIFICATION items.

---

## D1. Batch board endpoint vs. N× per-ticker calls

- **Decision**: A single `POST /pipeline/board` that accepts the watched tickers + capital and
  returns the whole fit-ranked board in one response.
- **Rationale**: `compute_candidate_result` rebuilds a universe snapshot + per-ticker EDGAR
  overlay per call, and `aggregate_exposure` is a portfolio-wide computation. Doing N× round
  trips would rebuild the snapshot N times and recompute exposure N times. One call builds the
  universe snapshot **once**, computes `aggregate_exposure` **once**, and reuses both across
  every ticker — keeping the board within the single-ticker latency budget × N.
- **Alternatives rejected**: (a) N× `GET /analyze/{ticker}` from the browser — repeated
  snapshot rebuilds, exposure recomputed client-side, heat math leaks to the frontend;
  (b) a streaming/websocket board — speculative complexity for a single-owner, on-demand tool.

## D2. Momentum-hardwired endpoint (reject other slugs)

- **Decision**: The board serves `midterm_52w_high_momentum` only; any other slug → HTTP 422
  with a clear message.
- **Rationale**: Entry-timing readiness (feature 012) is *only defined for momentum*. A
  multi-strategy pipeline would have to invent a readiness signal for strategies that have
  none — dishonest. Making the constraint explicit (and testable) is more honest than silently
  degrading.
- **Alternatives rejected**: a strategy picker on the board (implies parity that doesn't
  exist); silently returning empty readiness for non-momentum (hides the real limitation).

## D3. Fit as pure facts → band; score internal

- **Decision**: `score_fit(...)` is a pure function over independent boolean **facts**
  (`entry_ready`, `meaningful_size_survives`, `heat_headroom_ok`, `sector_room_ok`,
  `not_overconcentrated`, `regime_allows_entries`, `reward_to_risk_ok`, `cash_sufficient`).
  A deterministic weighted sum yields an internal 0–100 score used only for sort order; the UI
  shows a `fit_band ∈ {strong_fit, partial_fit, poor_fit, blocked}` plus the facts that
  failed — never the raw number.
- **Rationale**: The facts are the load-bearing, explainable output; a 0–100 score implies
  false precision for a heuristic. Showing failed facts is honest and actionable ("blocked:
  regime, heat"). Purity (no I/O — the API layer fetches data and passes facts in) guarantees
  determinism and trivial golden-fixture testing.
- **Alternatives rejected**: exposing the numeric score (false precision);
  configurable `fit_weight_*` flags (speculative flexibility for a single-owner tool — weights
  are hardcoded documented constants).

## D4. Two label vocabularies switched by the existing directive flag

- **Decision**: Neutral vocabulary (`fit_band` + fact→phrase rationale, no take/pass/size
  verbs) is always present. An optional `directive_label ∈ {consider_entry, hold_off,
  size_down, pass}` is set **only** when `personal_use_directive()` is on AND the app is not
  hosted; it is omitted entirely otherwise (pydantic `exclude`-if-None, same idiom as
  `Candidate.entry_timing`).
- **Rationale**: Reuses the constitution's existing v1.1.0 personal-use exception and its
  implementing flag — no new directive capability, and hosted mode already force-OFFs it via
  `hosting.hosted_mode()`. A separate optional field (not a mutation of the neutral text)
  keeps the Playwright no-directive lint green on the default/hosted path and makes leakage
  test-detectable.
- **Alternatives rejected**: a new dedicated directive flag (redundant); folding directive
  verbs into the rationale string (would trip the language lint and blur the boundary).

## D5. Available cash: cash-first, additive, flag-free

- **Decision**: The owner enters **available cash**; effective `total_capital` derives = cash
  + current market value of holdings. `size_position` gains an *optional* `available_cash`
  argument that caps `suggested_shares` so `shares × entry ≤ available_cash`, reporting
  `binding_constraint = "available_cash"` when it binds. No flag — absent ⇒ byte-identical.
- **Rationale**: Cash is the owner's real broker constraint; deriving total capital removes the
  manual re-sync as the market moves. Making it an optional request field (not a flag) means
  today's behavior is preserved for any caller that doesn't send it — the safest possible
  migration. `available_cash = 0` is honestly represented (suggested 0, reason available_cash).
- **Alternatives rejected**: a `pipeline_enabled`-style flag for cash sizing (unnecessary — an
  absent field already gates it); keeping the manual total-capital input as primary (forces the
  owner to keep re-syncing). Groundwork: a dormant `cash_balance_override` in `store.ts` (never
  wired to UI) is folded into the v6→7 migration (seed `available_cash` from it if set).

## D6. Pipeline stage: derived-first, manual overrides kept, frontend-owned

- **Decision**: Stage is *computed* each render by a pure `derivePipelineStage` selector with
  precedence **holdings-derived (owned/managing) > exited > ready > staged > watching**.
  `owned`/`managing` derive from `/portfolio/holdings`; `ready` from the board's
  `entry_timing == entry_ready`; `watching` is the default for a saved entry; `staged`/`exited`
  are the only *manual* overrides. Pipeline state lives in a new frontend-owned `pipeline` key
  synced via the existing `PUT /portfolio/state`.
- **Rationale**: Deriving from the source of truth (actual holdings, live readiness) prevents
  stale/contradictory stages; holdings-derived winning avoids `ready`↔`owned` flicker on a
  stale board. Keeping state frontend-owned honors the constitution's "owner blob opaque to
  backend" rule — the backend passes it through untouched.
- **Alternatives rejected**: backend-authoritative stage (backend would have to parse the
  owner blob); all-manual stages (owner has to hand-maintain what the app already knows).

## D7. Cockpit as the home page in place (no /cockpit route)

- **Decision**: Rework `app/page.tsx` into the cockpit; no separate `/cockpit` route.
- **Rationale**: The owner asked for a momentum-focused daily driver, and home is today just a
  static link grid. When `pipeline_enabled()` is OFF (board 404s), the page degrades to today's
  panels — no build-time env flag needed (respects the Windows-runbook "no env-var-in-build"
  rule via runtime graceful degradation).
- **Alternatives rejected**: a separate `/cockpit` route with home unchanged (splits the daily
  workflow, leaves a redundant static home); a build-time flag to switch home (violates the
  no-env-var-in-Next-prod-build rule).

## D8. Manual transactions reuse the import path; retain raw transactions

- **Decision**: `POST /portfolio/transactions` (append) + `DELETE /portfolio/transactions/{id}`
  (correct) reuse the existing import validator + `_assemble_holdings` aggregation, so manual
  entry and Sheet import converge on one holdings model. Raw transactions are **retained** in
  the owner blob (a `transactions` list), not just the aggregated average-cost snapshot. The
  Sheet import endpoint is unchanged and stays as the secondary bulk path.
- **Rationale**: Reusing the validator/aggregator guarantees identical holdings regardless of
  source (contract-testable). Retaining raw transactions is required so realized P&L (D9) is
  recomputable from history; the aggregate stays the source of truth for holdings/sizing (no
  double-count).
- **Alternatives rejected**: a separate manual-holdings model (divergence risk, double
  validation); discarding transactions after aggregation (makes realized P&L impossible).

## D9. Realized P&L via FIFO; unrealized via mark-to-market; informational only

- **Decision**: A new pure `portfolio/pnl.py`: `compute_realized_pnl(transactions)`
  FIFO-matches sells against prior buys per ticker → per-round-trip realized gain/loss
  (proceeds − cost basis − fees), win/loss flag, holding period, aggregated to per-ticker and
  portfolio totals + win rate. Unrealized P&L marks open holdings to market using existing
  quotes (`market_value − cost_basis`), degrading gracefully on a missing quote. All P&L fields
  are additive/optional ⇒ byte-identical when there are no closed lots. P&L never feeds any
  gate, rank, level, sizing, or backtest.
- **Rationale**: FIFO is a single, well-understood, documented cost-basis method — deterministic
  and golden-fixture testable. Keeping P&L purely informational preserves every constitution
  guarantee (no strategy/backtest impact). Graceful quote degradation follows the existing
  `portfolio_quotes` fail-soft idiom.
- **Alternatives rejected**: average-cost or specific-lot basis (average-cost loses per-trade
  win/loss; specific-lot needs UI the owner didn't ask for); letting P&L influence sizing
  (would violate the no-baseline-change / determinism guarantees).

## D10. UI-only strategy removal (reversibility invariant)

- **Decision**: Value + short-term are removed from every in-app entry point (home cards, nav,
  screen/compare links) while their strategy code, registry entries, and test suites remain in
  place and passing. Generic `/screen/[slug]` may remain reachable by direct URL but nothing
  links to it.
- **Rationale**: Honors the standing "momentum primary, value postponed — do NOT delete" rule
  and keeps the change fully reversible; a regression test asserts the value/short-term backend
  suites still pass unchanged (reversibility invariant). Momentum-only is the honest product
  surface given readiness only exists for momentum.
- **Alternatives rejected**: deleting the strategies (irreversible, breaks the standing rule
  and existing tests); leaving them linked but demoted (contradicts the owner's explicit
  "remove from the UI" decision).

## D11. Determinism & no-directive guardrails

- **Decision**: `score_fit` is pure; `size_position`, `aggregate_exposure`,
  `classify_entry_timing`, and `compute_realized_pnl` are deterministic → same snapshot + same
  portfolio ⇒ identical board and identical P&L. Neutral rationale comes from a fixed
  fact→phrase map; directive text is a separate flag-gated field with an explicit
  "never-present-hosted" test; the Playwright language lint runs on the reworked home.
- **Rationale**: These are the two constitution guarantees most at risk in a synthesis/home-page
  feature; making them structural (purity + separate field + lint) rather than reviewer-enforced
  keeps them from regressing.
- **Alternatives rejected**: composing directive text inline (lint risk); wall-clock or
  ordering-dependent fit tie-breaks (non-determinism — ties break on a stable key).

---

## Resolved unknowns summary

| Unknown | Resolution |
|---|---|
| Board shape: batch vs. per-ticker | Batch `POST /pipeline/board`, shared snapshot + one exposure (D1) |
| Multi-strategy pipeline? | No — momentum-only, 422 for other slugs (D2) |
| Fit output form | Pure facts → band; internal numeric score for sort only (D3) |
| Directive framing | Reuse `personal_use_directive()`; optional field, omitted hosted (D4) |
| Cash model | Cash-first, derived total capital, optional additive sizing limit (D5) |
| Stage authority | Derived-first, frontend-owned, manual staged/exited only (D6) |
| Cockpit routing | Replace home in place; graceful runtime 404 fallback (D7) |
| Manual txns | Reuse import validator + aggregation; retain raw txns (D8) |
| P&L method | FIFO realized + mark-to-market unrealized; informational only (D9) |
| Strategy removal scope | UI-only, code/tests kept green, reversible (D10) |
| Guardrails | Purity + separate directive field + lint + stable tie-break (D11) |
