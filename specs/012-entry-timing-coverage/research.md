# Phase 0 Research: Entry-Timing & Candidate Coverage

Feature `012-entry-timing-coverage`. Each decision resolves a NEEDS-CLARIFICATION or a
dependency/integration question from the plan's Technical Context. The spec's
Clarifications session (2026-06-27) already locked the product-level choices (full
geometric classifier; momentum-only; annotate-all default; custom three-tier model); the
decisions below resolve the **technical** approach within those constraints.

---

## Decision 1 — Base-pattern geometric classifier (US1, FR-002a)

**Decision**: Implement `indicators/base_pattern.py` as a pure, deterministic classifier
over a single ticker's adjusted daily OHLC history. It detects the **most recent
qualifying base** among four labelled types and returns
`{detected, base_type, pivot, handle_high, base_start, base_end, base_length_weeks,
base_depth, confidence}`. Approach per type:

- **Flat base**: a sideways consolidation where the high-to-low range over the window is
  shallow (≤ depth threshold) and price oscillates without a deep correction; pivot = the
  base's high. Minimum length 5 weeks (25 trading days).
- **Cup**: a single rounded correction-and-recovery — a left rim high, a rounded trough,
  and a return to near the left rim; pivot = the rim high. Minimum length 7 weeks.
- **Cup-with-handle**: a cup followed by a short, shallow downward drift (the handle) in
  the upper portion of the cup; **pivot = the handle high** (not the cup rim). Minimum
  length 7 weeks (cup + handle).
- **Double-bottom**: two distinct troughs separated by an interior peak (the middle
  pivot), with the second trough near the first; pivot = the interior-peak high. Minimum
  length 7 weeks.

Detection is geometric (swing-point extraction → shape constraints with explicit
tolerances), not a generic rolling-window max. When **no** type's constraints are met
with sufficient confidence, `detected=False` and the base-dependent components are
**undetermined** (FR-002a/FR-003) — never a fabricated pivot.

**Rationale**: The spec's Clarification chose a full classifier precisely so the
differentiated maturity rule (flat ≥ 5 wk; cup/cup-with-handle/double-bottom ≥ 7 wk) and
the handle-high pivot are applied per detected type. A high-precision/low-recall stance
(prefer "undetermined" over a wrong base) matches the constitution's data-integrity and
no-false-positive intent and the free daily-bar data tier. Pure + golden-fixture tested
satisfies Principle IV before any consumer.

**Alternatives considered**: (a) Reuse the existing rolling `breakout_high_20/50` as a
generic pivot — rejected: it cannot label base type, so the per-type maturity rule and
handle-high pivot are impossible (explicitly rejected in the spec Clarification). (b)
Swing-point + light shape only (no explicit labels) — rejected for the same reason. (c) A
learned/ML pattern detector — rejected: violates Principle II (black-box) and Principle IV
(no deterministic golden fixtures).

---

## Decision 2 — Where the overlay is computed, and determinism (US1)

**Decision**: Compute the base/pivot/breakout-volume **scalar columns** inside the
existing `_compute_snapshot_rows` pass in `screening/engine.py`, where each ticker's full
adjusted OHLCV `history` is already in scope (the same place 52w-high, ATR, SMA-200, and
volume ratios are computed). Persist them as snapshot columns (`base_type`, `pivot`,
`base_length_weeks`, `base_depth`, `breakout_volume_ratio`, `dist_above_pivot`,
`dist_above_sma_200`) and **bump `_STOOQ_SNAPSHOT_CACHE_VERSION` v6 → v7** so older cached
snapshots lacking them are invalidated (the documented gotcha:
[[snapshot-cache-version-gotcha]]). The pure overlay `screening/entry_timing.py` then
composes the six components + disqualifiers from those scalar columns plus `close`/`sma_200`.
It is invoked in `_screen_from_universe` **only for `midterm_52w_high_momentum`** (FR-023),
after `rules()` and the output contract, before candidate assembly. The
`entry_ready_only` parameter filters the assembled list (default OFF → annotate all,
FR-005).

**Rationale**: Detection needs the price *series*; the components/disqualifiers need only
scalars. Splitting them keeps the overlay pure and trivially deterministic, runs detection
exactly once per snapshot (memoized by the existing disk snapshot cache — no latency
regression, FR-008/perf goal), and keeps the overlay off the other three strategies for
free. Same snapshot → identical columns → identical classification and ordering (SC-002).

**Disqualifier thresholds (FR-022), fixed + configurable defaults**:
- **Climax-top exhaustion**: a ≈ +25%–50% advance within 1–3 weeks (measured as the
  max close-to-close run over a 5–15 trading-day trailing window) following an extended
  prior uptrend (e.g. ≥ N weeks above SMA-200). Default trigger 25% in ≤ 15 sessions after
  a qualifying prior trend → "climax-top exhaustion (not entry)".
- **Huge-gap breakout**: a breakout gap leaving price already `> +5%` above pivot →
  "gap-extended above pivot" (consistent with the pivot-proximity exclusion).
- **Recent short-lived catalyst**: a known catalyst (e.g. an index-inclusion effective
  date from the events store) with a recent effective date → attach an informational,
  **non-directive** "elevated post-catalyst pullback risk" warning; does **not** force
  not-entry-ready. Phrased to describe risk, never instruct action (SC-008).

All thresholds live in `lib/flags.py` as documented env-overridable knobs (the existing
011 idiom). Climax-top detection is deterministic for a given snapshot.

**Alternatives considered**: A separate post-screen price re-fetch pass to detect bases —
rejected: redundant I/O, breaks the single-snapshot determinism guarantee, and would have
to re-implement the seam-adjusted basis. Computing the overlay inside `rules()` — rejected:
`rules()` is shared/contract-validated and must stay an unchanged selection function
(FR-006); the overlay belongs after it.

---

## Decision 3 — Three-tier gate model & the demote-not-exclude path (US2, FR-009/009a)

**Decision**: Add `screening/gate_tiers.py` exposing a per-strategy
`gate_tiers(strategy_slug)` map (configurable via `lib/flags.py` overrides), defaulting for
`midterm_52w_high_momentum` to:

- **Essential** (fail → exclude): universe **liquidity** gate (ADV ≥ $1M 20d, price ≥ $5),
  the feature-008 **data-integrity** check, and the **primary thesis** gate (52-week-high
  proximity).
- **Preferred / non-essential** (non-pass → retained, marked `skipped`, demoted below all
  clean names): **market regime** (choppy/down → deduct ranking points + warn, never
  exclude), **sector strength** (treated `skipped` when the universe is narrow), and
  **relative strength** (RS line near new highs — an additional momentum confirmation).
- **Disqualifier** (positive detection → hard-exclude / force not-entry-ready):
  **climax-top exhaustion** and **huge-gap breakout** > +5% above pivot. The short-lived
  catalyst is a **warning only**, not an exclusion.

When `expanded_coverage` is enabled (default OFF), a candidate that fails or cannot
evaluate a **preferred** gate is **retained** with that gate recorded `skipped` + reason
and **demoted**. This reuses the strategy's existing **tiered-mode** machinery
(`_gate_mode`, per-row `warnings`/`warning_count`) and the engine's existing
`warning_count`/`data_suspect` sort in `_screen_from_universe`, which already guarantees
warned names sort strictly below clean names (FR-012/SC-004) by the same path as the
data-integrity demotion. Essential failures and disqualifier triggers exclude **regardless**
of the toggle (FR-011). **No gate threshold is changed** (FR-015). Default OFF → the
existing hard-mode path → output byte-identical to today (FR-013/SC-009).

**Rationale**: The codebase already has a soft-gate "warn + rank, don't exclude" mode and a
demotion sort that places warned/suspect names last — US2 is largely **wiring the existing
tiered behaviour to an explicit, per-strategy tier map and a coverage toggle**, plus adding
relative strength as a new soft confirmation. This minimizes new logic and inherits the
proven ordering invariant. Matches the documented gate-defaults preference
([[gate-defaults]]): hard mode is the default; soft expansion is opt-in.

**Relative-strength computation**: RS line = candidate cumulative return vs SPY over the
momentum lookback; "near new highs" = RS line within a small band of its trailing max.
Computed from series already loaded (candidate price history + the regime/SPY series the
regime gate already fetches). Fails open (→ `skipped`) when SPY history is unavailable.

**Alternatives considered**: A brand-new generalized gate-tier engine replacing
`rules()`-internal filtering across all strategies — rejected: large blast radius, risks
changing value/VCP/ATR behaviour and the committed momentum contract; the spec scopes US2
to surfacing/ordering, not a gate-engine rewrite. Making the primary thesis gate
demote-not-exclude (spec Question 2 option C) — rejected by the owner's confirmed
three-tier model (thesis stays essential).

---

## Decision 4 — Shariah quarterly-refresh cadence guard (US3, FR-016–021)

**Decision**: Add `shariah/refresh_cadence.py` with a pure, clock-injected
`should_refresh(now, last_success_at, *, interval_days=90, force=False, key_present=True)`
returning a decision object `{action: "refresh"|"skip"|"stale", reason, elapsed_days}`:

- `force=True` and `key_present` → **refresh** (bypass the cadence gate, FR-016/US3.4).
- `last_success_at` missing/unreadable → treated as **due** → refresh if `key_present`,
  else **stale** (fail-safe toward freshness, FR-018 / edge case).
- elapsed < 90 days → **skip** (reuse cache, **zero API calls**, FR-017/SC-006).
- elapsed ≥ 90 days and `key_present` → **refresh** (FR-016).
- elapsed ≥ 90 days and not `key_present` → **stale**: reuse cache, surface a loud
  "compliance data stale" condition (FR-019/SC-007).

`seed_halal_terminal_results` / `bulk_screen_universe` (and `scripts/ingest_daily.py`)
consult this guard **before** any `httpx` call and short-circuit on `skip`/`stale`. The
Halal Terminal manifest `refresh_interval_days` becomes **90** (was 7), so
`ShariahLookup._source_is_stale` reports staleness on the ~90-day basis (FR-020). The
decision is deterministic given `(now, last_success_at, force, key_present)` (FR-021/SC-005:
≤ ~4 calls/yr + forced).

**Rationale**: "3 months = 90 calendar days" (spec Assumption). The guard is the minimal,
testable seam: a pure function with injected clock makes the simulated-year and
within-window-zero-call tests trivial and deterministic, and it sits at the single network
entry point so no caller can bypass it. Reusing the existing manifest
`refresh_interval_days` field means downstream staleness messaging updates with one number.
Calendar-day (not trading-day) basis matches the spec.

**Alternatives considered**: A cron/schedule-only solution (run the seed every 90 days via
CI) — rejected: doesn't protect against an out-of-band manual `ingest_daily.py` run hitting
the API, and gives no in-process "stale" signal; the in-code guard is robust to *how* the
seed is invoked. Trading-day cadence — rejected by the spec's explicit calendar-day
assumption.

---

## Decision 5 — Models & API surface (cross-cutting)

**Decision**: Extend the `Candidate` Pydantic model with an optional `entry_timing` object
(overall state, the six component results, disqualifier results, and the diagnostics) and an
optional `skipped_gates: list[{gate, reason}]`; both default to `None`/`[]` so the schema is
backward compatible and non-momentum strategies simply omit `entry_timing`. No new endpoint:
the entry overlay and the `entry_ready_only` / `expanded_coverage` flags ride the existing
screen request `parameters` (the same pattern as `sector_strength_top_fraction`), and the
three-tier map is surfaced through the existing `StrategyGatesPanel` / strategy metadata.

**Rationale**: Keeps the API contract additive and the frontend change localized; avoids a
new route and its owner-secret/proxy wiring. Consistent with how feature 011 added
level/sizing metadata to `Candidate` rather than new endpoints.

**Alternatives considered**: A dedicated `/strategies/{slug}/entry-timing` endpoint —
rejected: the classification is per-candidate and always wanted alongside the screen, so an
embedded field avoids a second round-trip and a second owner-gated route.

---

## Determinism & constitution recap (applies to all decisions)

- Same snapshot → identical base columns, classification, candidate set, ordering, and
  refresh decision (SC-002/SC-009; the refresh decision is pure given its inputs).
- No existing strategy rule/default/threshold/citation/indicator/backtest-baseline change
  (FR-006/015). The new `base_pattern` indicator is golden-fixture tested **before** the
  overlay consumes it (Principle IV).
- Zero directive language in all new copy (SC-008); "good entry point" → objective cited
  technical classification; the catalyst caution describes risk only.
- `data_as_of` + `disclaimer` ride every response exposing the new data; hosted
  directive-OFF force unchanged.
