# Phase 0 Research: Advisor Prompt Export

All Technical Context items were resolvable from the existing codebase and the
spec's Assumptions; there were no open NEEDS CLARIFICATION. The decisions below
record *why* the chosen approach is the honest, low-drift one.

## Decision 1 — Backend builder as the single source of truth (not a client template)

- **Decision**: Assemble the prompt in a pure backend function
  `backend/src/agent/advisor_prompt.py :: build_advisor_prompt(...)`, reading the
  registry `Strategy` object and the backtest artifact directly. The frontend
  only fetches and copies.
- **Rationale**: Principle II (transparency) and III (reproducibility). A
  client-side TypeScript template would re-encode the strategy's rules,
  citations, and parameters and drift the moment the strategy file changes —
  exactly the dishonesty this feature is meant to avoid. A backend builder reads
  the live declaration, so a parameter or modification change is reflected
  automatically (FR-012), and the function is deterministically unit-testable.
- **Alternatives considered**:
  - *Pure client-side builder from data already on the page*: rejected — would
    duplicate and drift the strategy context; the candidate payload also lacks
    the full modification list and the `bias_check`.
  - *Persisting generated prompts*: rejected — unnecessary; the prompt is a pure
    function of the frozen snapshot + declaration, so it is reproducible on
    demand (no new persistence, Principle III).

## Decision 2 — Reuse `analyze.py`'s single-ticker universe evaluation

- **Decision**: The endpoint lives on the existing `/analyze` router and reuses
  `build_single_ticker_snapshot`, `prepare_universe_gates`, `evaluate`, and
  `derive_levels` so the prompt's gate results and levels are identical to what
  the analyze surface already shows.
- **Rationale**: Guarantees SC-005 (every number in the prompt equals the
  on-screen figure) for free and avoids a second, divergent computation path.
- **Alternatives considered**: a standalone recomputation — rejected as a
  consistency and maintenance risk.

## Decision 3 — Honesty block sourced from the artifact's real `bias_check`

- **Decision**: Read `bias_check` from
  `backend/data/backtests/midterm_52w_high_momentum.json`. Emit the
  survivorship caveat whenever `bias_check.survivorship_bias.passed` is false,
  quoting/derived from its `note`. If the artifact is missing/unreadable, state
  that the bias status could not be confirmed (never claim it is clean).
- **Rationale**: Principle III. Makes the caveat a data-driven fact (FR-007,
  SC-003), not boilerplate that could go stale if the bias check later passes.
  Current artifact state: `survivorship_bias.passed = false` (free Stooq bundle
  has no delisted tickers); `lookahead_bias`, `point_in_time_fundamentals`,
  `costs` all pass with notes.
- **Alternatives considered**: a hard-coded caveat string — rejected; it would
  lie once the delisted-data limitation is fixed.

## Decision 4 — Personal-use directive flag via the existing `SCREENER_*` pattern

- **Decision**: A single flag `personal_use_directive()` (env
  `SCREENER_PERSONAL_USE_DIRECTIVE`, **default off**) following the same
  operator-override convention already used in the strategy file
  (`SCREENER_TREAT_STRATEGY_VALID`, `SCREENER_MIDTERM_STOP_MODE`,
  `SCREENER_GATE_MODE`). When off → neutral framing, zero directive language;
  when on → directive task framing.
- **Rationale**: Principle V. Keeps the app compliant by default, makes the
  personal-use exception explicit, reversible, and discoverable, and matches an
  established codebase idiom rather than inventing a new mechanism. Enabling it
  to default-on requires the constitutional amendment noted in the plan.
- **Alternatives considered**:
  - *Always directive*: rejected — silently violates a NON-NEGOTIABLE principle.
  - *A persisted user setting*: deferred — the env-var operator override is the
    established pattern and sufficient for a single-user tool; a UI toggle can
    follow if wanted.

## Decision 5 — Determinism: no wall-clock in the prompt body

- **Decision**: The prompt body uses only the snapshot's `data_as_of`; it must
  not embed `utc_now`/generation timestamps. The endpoint envelope may carry a
  disclaimer + as-of, but the copyable prompt text is a pure function of
  (snapshot, declaration, flag).
- **Rationale**: FR-011 / SC-004 require byte-identical regeneration on the same
  snapshot. A generation timestamp would break that.
- **Alternatives considered**: including a "generated at" line — rejected; it
  defeats the determinism guarantee and adds no value to the advisor.

## Decision 6 — Scoped no-directive-copy lint exemption

- **Decision**: Mark only the personal-use prompt-preview element (e.g. a
  `data-personal-use-prompt` attribute) and exempt that single element in
  `no-directive-copy.spec.ts`; the rest of the page remains under the lint.
  The exemption is only meaningful when the flag is on.
- **Rationale**: Principle V / FR-014 — preserve the global no-directive
  guarantee for all app chrome while allowing the deliberately-directive,
  personal-use prompt text to exist in one clearly-marked place.
- **Alternatives considered**: disabling the lint for the page — rejected as far
  too broad.
