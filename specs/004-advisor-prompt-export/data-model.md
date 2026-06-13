# Phase 1 Data Model: Advisor Prompt Export

No new persisted entities. The feature composes existing computed data into one
transient text artifact. The "entities" below are the logical building blocks of
that artifact and the inputs it draws from.

## AdvisorPrompt (output, transient)

The copy-ready text produced for one candidate. A pure function of
(frozen snapshot, strategy declaration, personal-use flag). Not stored.

| Field | Source | Notes |
|---|---|---|
| `task_instruction` | flag-dependent template | Directive framing iff personal-use flag on; else neutral |
| `strategy_context` | `Strategy` declaration (registry) | Name, citation, timeframe, holding period, gates, modifications+citations |
| `candidate_result` | analyze computation | Ticker/name/sector, rank/matched, price levels, reward:risk |
| `gate_breakdown` | `evaluate(...)` gate_results | Each gate: status (pass/fail/skipped) + detail |
| `regime_note` | regime + `regime_favorability` | Current regime and its favorability for this strategy |
| `honesty_block` | backtest `bias_check` + gate notes | Survivorship status, fail-open notes, freshness, scope |
| `data_as_of` | snapshot | Date string; also the only temporal value in the body |
| `disclaimer` | `DISCLAIMER_TEXT` | Standard non-advice disclaimer |

**Validation / invariants** (enforced by tests):

- Contains **every** gate the strategy declares for the candidate (FR-004).
- Contains **every** modification the strategy declares, each with its citation
  (FR-006, SC-002).
- Contains the survivorship caveat **whenever**
  `bias_check.survivorship_bias.passed` is false (FR-007, SC-003).
- Gates that are `skipped`/passed-through are textually distinguished from real
  passes (FR-008).
- No directive trading language when the personal-use flag is off (FR-013, SC-006).
- Body contains no wall-clock timestamp; identical on re-run for a fixed
  snapshot (FR-011, SC-004).
- Every numeric value equals the analyze surface's value for that candidate
  (FR-010, SC-005).

## CandidateResult (input — existing)

The app's computed assessment of one stock under the strategy. Already modeled
by `AnalyzeResponse` / `Candidate` in `backend/src/models/strategy.py`:
`ticker`, `name`, `sector`, `would_be_selected`/`rank`, `current_price`,
`entry`, `stop_loss`, `tighter_stop_loss`, `take_profit`, `gate_results`,
`data_notes`, `data_as_of`, `disclaimer`.

## StrategyDeclaration (input — existing)

The `Strategy` object from the registry: `name`, `citation`, `timeframe`,
`holding_period_days`, `parameters`, `regime_favorability`, and `modifications`
(each a `Modification` with `name`, `description`, `citation`). Served today via
`GET /strategies/{slug}`.

## BiasCheck (input — existing artifact)

From `backend/data/backtests/midterm_52w_high_momentum.json` →
`bias_check`. Each key (`survivorship_bias`, `lookahead_bias`,
`point_in_time_fundamentals`, `costs`) has `{ passed: bool, note: str }`. The
honesty block reads `survivorship_bias` primarily; current state `passed=false`.

## PersonalUseFlag (input — new, config)

Boolean resolved from `SCREENER_PERSONAL_USE_DIRECTIVE` (default false), via a
small `flags.py` helper, mirroring the existing `SCREENER_*` operator overrides.
Selects directive vs neutral `task_instruction` and the framing of the prompt.
