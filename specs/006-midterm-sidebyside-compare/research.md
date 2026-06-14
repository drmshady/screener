# Phase 0 Research: Mid-Term Side-by-Side Variant Comparison

All decisions below resolve to existing, tested mechanisms; no NEEDS
CLARIFICATION remained after inspecting the code.

## Decision 1 — The four variants are a fixed matrix driven by existing parameters

**Decision**: Ship a fixed set of exactly four variants:

| # | Label | Strategy slug | Toggled parameter | Value |
|---|-------|---------------|-------------------|-------|
| 1 | Momentum — sector gate ON  | `midterm_52w_high_momentum` | `sector_strength_top_fraction` | `0.5` |
| 2 | Momentum — sector gate OFF | `midterm_52w_high_momentum` | `sector_strength_top_fraction` | `1.0` (default) |
| 3 | Value — momentum floor ON  | `midterm_value_composite`   | `min_momentum_12_1` | `-0.20` |
| 4 | Value — momentum floor OFF | `midterm_value_composite`   | `min_momentum_12_1` | `-1.0` (default) |

**Rationale**: Both toggles already exist and are already honoured per-run.
- Momentum sector gate: `sector_strength_top_fraction` (default `1.0` = disabled);
  `0 < frac < 1` enables it, keeping names only in the top-`frac` of sectors by
  breadth ([midterm_52w_high_momentum.py:99](../../backend/src/strategies/midterm_52w_high_momentum.py#L99)).
- Value momentum floor: `min_momentum_12_1` (default `-1.0` = disabled);
  a value like `-0.20` drops names down >20% over 12-1
  ([midterm_value_composite.py:70](../../backend/src/strategies/midterm_value_composite.py#L70)).

The canonical "ON" values match the operator's existing A/B harness:
`scripts/ab_sector_gate.py` sweeps fractions `[1.0, 0.67, 0.5]` (so `0.5` =
"top 50%"), and the momentum-floor parameter's own docstring uses `-0.20` as the
worked example. Choosing those keeps the side-by-side consistent with the manual
A/B the operator already runs (see memory: "A/B every recommended default change
on real data").

**Alternatives considered**:
- *User-defined variant matrix* (arbitrary N, arbitrary params): more flexible but
  larger surface, harder to make the advisor prompt deterministic and legible, and
  not what the request asked for. Deferred — the four-variant set is fixed for v1
  (Assumption in spec).
- *Reuse a single toggle value for "ON"*: rejected hard-coding; the ON values are
  defaults of the matrix definition but remain the strategy parameters' documented
  range, so a later override is trivial.

## Decision 2 — Build the universe snapshot once; evaluate four `rules()` over it

**Decision**: Add a matrix runner that assembles the liquid-universe snapshot
**once** for the given `as_of_date`/filters, then evaluates each variant by
setting the variant's `universe.attrs[...]` toggle and calling that strategy's
`rules()` on a copy of the shared frame — producing four `ScreenResult`-shaped
results that share one `data_as_of`, one universe, and one regime.

**Rationale**: `run_strategy` is deterministic on `as_of_date`, so calling it four
times would already yield consistent results — but it rebuilds the (expensive)
universe snapshot each time and recomputes regime four times, and it does not
*guarantee* the four runs saw the identical universe. Building once and fanning
out four `rules()` passes (a) literally satisfies FR-002 "same snapshot for all
four", (b) keeps the run within the p95 ≤ 10 s budget, and (c) keeps regime
computed once and shared. The per-run toggle threading already used by
`run_strategy` ([engine.py:1071](../../backend/src/screening/engine.py#L1071),
[engine.py:1077](../../backend/src/screening/engine.py#L1077)) is the seam to
reuse — factor the snapshot-build and the "apply attrs + call rules + assemble
candidates" steps so both the single-strategy path and the matrix path call them.

**Alternatives considered**:
- *Call `run_strategy` four times unchanged*: simplest, still deterministic on the
  frozen snapshot, but rebuilds the universe 4× and only *probabilistically* shares
  it. Acceptable fallback if the refactor proves invasive, but the shared-snapshot
  runner is preferred for correctness (FR-002) and performance. Documented as the
  fallback in tasks.

## Decision 3 — "Toggle OFF a gate" is recorded as intentionally-disabled, not skipped

**Decision**: When a variant's toggle disables a gate (momentum sector gate OFF,
value momentum floor OFF), the variant surfaces that as a configuration state
distinct from "skipped on missing data".

**Rationale**: The code already distinguishes these. The momentum prompt's
`_run_config_block` states the sector gate ON/OFF explicitly and the
`_candidate_summary_block` deliberately does **not** flag a sector-gate skip as a
data gap when the gate is OFF ([advisor_prompt.py:357-401](../../backend/src/agent/advisor_prompt.py#L357)).
The value strategy emits an explicit "momentum floor disabled (pure value …)"
note when `min_momentum_12_1 <= -1.0` ([midterm_value_composite.py:537](../../backend/src/strategies/midterm_value_composite.py#L537)).
The matrix surface and prompt reuse these so FR-006 / SC-008 hold without new
gate logic.

## Decision 4 — One combined advisor prompt, built from existing section builders

**Decision**: Add `build_midterm_matrix_advisor_prompt(variants, *, regime,
directive)` that emits: one shared task header (4-variant framing), one shared
market-regime block, then four clearly delimited variant sections. Each variant
section reuses `_strategy_context` (declaration + citations), `_run_config_block`
(toggle state), the compact `_candidate_summary_block` per candidate, and the
strategy's own `bias_check` line; a single combined honesty footer closes the
prompt. Directive framing stays gated on `personal_use_directive()`.

**Rationale**: `build_screen_advisor_prompt` already assembles a one-strategy
batch prompt from these exact helpers and is a pure function of its inputs (no
wall-clock), so the multi-variant assembler inherits determinism (FR-013 / SC-007)
and the directive gate (FR-014) for free. Per-variant `bias_check` comes from
`load_survivorship_status(slug=…)`, already keyed by slug
([advisor_prompt.py:16](../../backend/src/agent/advisor_prompt.py#L16)) — so both
momentum and value carry their own honest verdict (FR-012, FR-015).

**Alternatives considered**:
- *Concatenate four independent single-strategy prompts*: produces four task
  headers and four regimes, bloats the prompt, and invites the advisor to treat
  them as unrelated. Rejected in favour of one shared header + delimited sections.

## Decision 5 — New live-compare endpoints, separate from the 003 backtest bake-off

**Decision**: Add `POST /strategies/midterm-compare` (returns the four variant
results + shared regime/`data_as_of`/disclaimer) and
`POST /strategies/midterm-compare/advisor-prompt` (returns the single combined
prompt). These live next to the existing `/strategies/{slug}/run` and
`/strategies/{slug}/advisor-prompt`.

**Rationale**: Feature 003's comparison is a *backtest* harness producing a
Calmar-ranked historical scorecard ([specs/003-strategy-comparison/spec.md](../003-strategy-comparison/spec.md)).
This feature compares **live** candidates under parameter toggles — a different
question and a different payload. A dedicated endpoint keeps each surface honest
about what it shows (a screen snapshot, not a backtest verdict) and avoids
overloading the 003 semantics. The frontend reuses 003's side-by-side
*presentation idiom* and the standing disclaimer/`data_as_of` shell.

**Alternatives considered**:
- *Extend the 003 comparison endpoint*: rejected — mixing a live-screen payload
  into a backtest-ranking response would blur "backtest performance" vs "today's
  candidates" and risk implying a variant is validated by a backtest it doesn't
  have.

## Decision 6 — Honesty: failing bias-check travels with both of a strategy's variants

**Decision**: Each strategy's `bias_check` (survivorship still FAILS on free
Stooq for both momentum and value) is attached to **both** of that strategy's
variants in the comparison view and the prompt; toggling a gate does not change
the underlying backtest verdict.

**Rationale**: The toggles are screen-time configuration, not backtest reruns, so
the honest verdict is a property of the strategy, not the variant (FR-015, SC-009).
Surfacing it on each variant prevents a reader from assuming "sector gate ON" or
"momentum floor ON" somehow validated the strategy. This matches the existing
honesty-block behaviour, just replicated per strategy.
