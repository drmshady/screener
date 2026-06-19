# Research: Release Readiness (009)

Phase 0 decisions. The four spec clarifications (Session 2026-06-16) are treated
as resolved inputs; the remaining items are design decisions grounded in the
existing codebase. No NEEDS CLARIFICATION remain.

---

## Decision 1 — Startup refresh UX: manual-trigger-with-prompt

**Decision**: On app load, a mount-time `StartupFreshnessGate` calls the
read-only freshness check. If any material source is stale relative to the latest
completed trading session, it renders a **non-blocking prompt** offering *Refresh
now* or *Proceed on cached data*. Refresh is always operator-initiated.

**Rationale**: Clarified in spec (Q1 → manual-trigger-with-prompt). Silent/auto
refresh on start would (a) violate the operator's control, (b) risk a multi-second
network stall before the first action, and (c) make "why did the numbers change"
non-deterministic across sessions. A prompt keeps the operator in command while
still defeating the highest-risk failure (silent stale results).

**Alternatives rejected**:
- *Silent auto-refresh on start* — rejected by clarification; also blocks the UI
  and hides what changed.
- *Background refresh with later toast* — partial data could render as final
  before the toast; conflicts with US1-AC4.

## Decision 2 — Refresh scope: incremental / stale-only

**Decision**: "Refresh now" reuses the **existing** `POST /data/refresh`, which
already fetches only incremental bars (`fetch_incremental_ohlcv`, history-bounded),
is capped at 1,200 tickers, updates `manifest.json`, clears snapshot caches, and
best-effort refreshes reference thresholds. No new full-rebuild path is added.

**Rationale**: Clarified in spec (Q2 → incremental/stale-only). The incremental
path already exists and is bounded so an interactive click can't trigger a
multi-minute pull. Reusing it keeps one refresh code path and avoids a second,
divergent "startup refresh" implementation.

**Alternatives rejected**:
- *Full universe + fundamentals rebuild on start* — rejected by clarification;
  that is the scheduled `scripts/ingest_daily.py` job's role, not an interactive
  click.

## Decision 3 — Staleness-detection budget: ≤ 3 s, read-only

**Decision**: Add `GET /data/freshness`. It reads only the manifest's cached
`data_as_of` / `last_bar_date_by_ticker` per source and compares to
`latest_completed_trading_day()`. **No network call, no recomputation, no
mutation.** Returns per-source records + `any_stale`.

**Rationale**: Clarified in spec (Q3 → ≤ 3 s reading cached metadata only).
Reading a small JSON manifest and doing calendar arithmetic is sub-second; the
3 s figure is a guarantee ceiling. Keeping it read-only guarantees the startup
check can never itself stall on a dead source — that is the refresh's job, behind
the operator's explicit click.

**Alternatives rejected**:
- *Detection that pings each provider* — could exceed 3 s and couples detection
  to network health; the whole point is to detect from cached metadata.

## Decision 4 — Minimum fix bar: block on correctness + crashes

**Decision**: The bug scan produces `bug-scan-log.md`. Each finding is classified
`correctness` / `integrity` / `crash-hang` (= **must-fix before release**) or
`minor`/`cosmetic` (= **may defer** with a one-line logged rationale). Release is
gated on zero open must-fix findings (SC-007).

**Rationale**: Clarified in spec (Q4 → block on correctness + crashes). A
decision-support tool must not ship known wrong output or a primary-flow crash; a
visual nit can ship deferred. The log makes every deferral explicit and auditable.

**Alternatives rejected**:
- *Block on every finding* — over-scopes a personal-use release and incentivizes
  not logging minor issues.
- *Block on nothing (log only)* — would permit shipping known-wrong output,
  violating Principle I/IV intent.

## Decision 5 — Dedicated `/data/freshness` vs overloading `/meta`

**Decision**: Add a purpose-built `GET /data/freshness` for the startup gate
rather than extending `/meta`. `/meta` continues to back the detailed
`DataFreshnessPanel`.

**Rationale**: The startup gate needs one boolean decision (`any_stale`) plus the
minimal per-source basis to explain it, with a contract test pinning the ≤ 3 s,
no-mutation guarantee. Overloading `/meta` (whose shape serves the panel) would
blur that contract. The two endpoints share the same underlying manifest +
`latest_completed_trading_day()` logic, so there is no divergent source of truth.

**Alternatives rejected**:
- *Extend `/meta` with an `any_stale` flag* — viable but mixes two consumers'
  contracts; a dedicated endpoint is clearer to test and to reason about for the
  3 s SLA.

## Decision 6 — Per-surface / per-input freshness

**Decision**: Each data-bearing surface reflects the freshness of **its own**
material inputs (FR-004). Concretely, the advisor prompt lists per-input
freshness (prices as-of, fundamentals as-of, regime as-of) instead of a single
global timestamp; the freshness panel shows per-source state; the startup gate
names the specific stale source(s).

**Rationale**: A single global "data as of" can overstate currency — e.g. prices
fresh but fundamentals two weeks old. Honest disclosure (Principle I/V) requires
the surface to show the as-of of what it actually depends on. The manifest
already tracks per-source as-of, so this is presentation wiring, not new data.

**Alternatives rejected**:
- *Single global timestamp everywhere* — the spec's edge case ("partial refresh")
  explicitly forbids one timestamp overstating currency.

## Decision 7 — Determinism & no-mutation guarantees

**Decision**: The startup check mutates nothing; the only mutation is the
operator-triggered refresh. The advisor-prompt builder stays a **pure function**
(freshness values are read from the snapshot/result, never from wall-clock), so a
fixed snapshot yields a byte-identical prompt. Cleanup and fixes must not change
any screen/regime/sizing/event output for a fixed snapshot (FR-015, SC-010), and
the green suite proves it.

**Rationale**: Determinism is a constitution non-negotiable (III) and an explicit
success criterion (SC-010). Adding freshness disclosure must not introduce a
wall-clock dependency into deterministic artifacts; the existing builder already
avoids wall-clock in its body, and new lines pull from the snapshot's as-of
fields.

**Alternatives rejected**:
- *Stamp the prompt with generation time* — would break byte-identical re-export
  for a fixed snapshot (existing FR-011 of feature 004).

---

## Verification approach (US3/US4)

- **Suites**: run the complete backend (`pytest`) and frontend (Vitest +
  Playwright) suites on a clean checkout; assert 100% pass and **0 silently
  skipped financial-logic tests** (audit for `@pytest.mark.skip`/`xfail` on
  indicator/strategy tests).
- **Bug scan**: walk the real endpoints (`/screen`, `/analyze`, candidate detail,
  advisor-prompt export, `/portfolio`, `/data/refresh`, `/meta`,
  `/data/freshness`) and the data loaders; probe failure modes (source down,
  empty result, missing fundamentals, timeout). Record findings in
  `bug-scan-log.md`; fix must-fix, defer-with-rationale otherwise; add a
  regression test for each fix.
- **Robustness fixes** target the four spec failure modes and must keep the rest
  of the UI navigable and never present partial data as authoritative.

## Deployment approach (US5)

- The runbook (`quickstart.md`) follows the established Windows dev runbook
  conventions (`py -3.12`, `npm.cmd`, **Next production build** for headless — no
  env var baked into the build) and the personal-use, single-machine scope.
- Provider keys remain **process-local / inline**, never written to a file
  (existing convention; FR-022).
- Finalization ends with a suite-green commit on `009-release-readiness` (FR-023).
