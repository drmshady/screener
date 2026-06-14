# Contract: Four-Variant Advisor Prompt Layout

Produced by `build_midterm_matrix_advisor_prompt(variants, *, regime, directive)`
in [backend/src/agent/advisor_prompt.py](../../../backend/src/agent/advisor_prompt.py).
Pure function of its inputs (no wall-clock) → byte-identical re-export for a fixed
snapshot (FR-013). Reuses the existing per-screen section builders.

## Section order (exact)

```text
<TASK HEADER>                 # shared; 4-variant framing; neutral unless directive flag on

## Market regime              # shared; computed once for the snapshot
- Current regime: <regime>
- (favorability is noted per-strategy inside each variant section)

## Variant 1 — Momentum — sector gate ON
<_strategy_context>           # name, citation, timeframe, params (incl. sector_strength_top_fraction=0.5), modifications+citations
<_run_config_block>           # "Sector-strength gate: ON — top 50% of sectors by breadth…"
### Candidates (<n>)
<_candidate_summary_block × n># rank, levels, ranking inputs, gates (compact)
- Backtest bias-check (momentum): <verdict from load_survivorship_status('midterm_52w_high_momentum')>

## Variant 2 — Momentum — sector gate OFF
… same, sector_strength_top_fraction=1.0, run-config "Sector-strength gate: OFF (default)…"
- Backtest bias-check (momentum): <same momentum verdict>   # Decision 6

## Variant 3 — Value — momentum floor ON
<_strategy_context>           # value declaration, params incl. min_momentum_12_1=-0.20
<run-config>                  # "Momentum floor: ON — drops names down >20% over 12-1…"
### Candidates (<n>) …
- Backtest bias-check (value): <verdict from load_survivorship_status('midterm_value_composite')>

## Variant 4 — Value — momentum floor OFF
… min_momentum_12_1=-1.0, run-config "Momentum floor: OFF (pure value)…"
- Backtest bias-check (value): <same value verdict>

## Honesty & limitations (read before any performance judgment)
- Survivorship caveat applied to ALL variants (both strategies FAIL on free Stooq)
- Per-candidate data gaps are flagged inline and are NOT genuine passes
- Data freshness: end-of-day, as of <data_as_of>
- <disclaimer>
- (if directive) Scope: personal-use, single owner only; not redistributable
```

## Required content per variant section (FR-012 / SC-006)

Each of the four sections MUST contain, with **0 omissions**:
1. strategy declaration with core citation and each modification's citation,
2. the toggled parameter's value for this variant (so on/off is explicit),
3. run-configuration line stating the gate ON/OFF (intentionally-disabled, not a
   data gap, when OFF — FR-006),
4. each candidate's levels + ranking inputs + gate statuses (or an explicit
   "no candidates matched" line when empty — FR-016),
5. the underlying strategy's honest bias-check verdict (FR-015).

## Determinism (FR-013 / SC-007)

- No wall-clock, randomness, or set-ordering in the body; variants emitted in the
  fixed order above; candidates in their `ScreenResult` rank order.
- Re-export on the same snapshot ⇒ identical bytes.

## Directive gating (FR-014)

- Task header and any take/pass/size language appear only when
  `personal_use_directive()` is true (`SCREENER_PERSONAL_USE_DIRECTIVE=1`).
- When off, neutral "screen match / candidate for further research" framing is
  used throughout, and the no-directive Playwright lint passes (FR-010, SC-005).
