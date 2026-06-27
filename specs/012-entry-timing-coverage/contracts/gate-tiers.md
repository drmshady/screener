# Contract: Three-Tier Gate Classification & Expanded Coverage (US2)

`screening/gate_tiers.py` + the engine's existing demotion sort. Defines the per-strategy
gate→tier map and the fail-open retention path. No gate threshold is changed (FR-015).

## Tier map

```python
def gate_tiers(strategy_slug: str) -> dict[str, Literal["essential", "preferred", "disqualifier"]]
```

Discoverable per strategy (FR-009), configurable via `lib/flags.py` overrides. Default for
`midterm_52w_high_momentum` (FR-009a):

- **essential**: `liquidity`, `data_integrity`, `52-week-high proximity`
- **preferred**: `market regime`, `sector strength`, `relative strength`
- **disqualifier**: `climax-top exhaustion`, `huge-gap breakout`

## Behaviour (`expanded_coverage` screen parameter, default OFF)

| Tier | non-pass / trigger | `expanded_coverage` OFF | `expanded_coverage` ON |
|------|--------------------|-------------------------|------------------------|
| essential | fail | **exclude** | **exclude** (FR-011) |
| disqualifier | positive detection | **exclude** / force not-entry-ready | **exclude** / force not-entry-ready (FR-011/022) |
| preferred | fail **or** unevaluable | **exclude** (today's hard-mode behaviour) | **retain**, record `skipped_gates[{gate, reason}]`, **demote** below all clean names (FR-010/012) |

## Invariants

1. **Default-off identity (FR-013/SC-009)**: with `expanded_coverage` OFF, the screen path,
   candidate set, and ordering are **byte-identical** to the pre-feature baseline for the
   same snapshot (reuses the existing hard-mode).
2. **Essential/disqualifier safety (FR-011/SC-003)**: no candidate failing an essential gate
   or triggering a disqualifier is ever surfaced, regardless of the toggle. 100% of
   coverage-added candidates fail/skip only **preferred** gates.
3. **Strict ordering (FR-012/SC-004)**: every fully-clean candidate ranks above every
   candidate with ≥1 skipped preferred gate — enforced by the existing
   `data_suspect`→`warning_count`→`score`→`ticker` sort in `_screen_from_universe` (the same
   path that demotes data-integrity-flagged names; data-suspect still sinks below all).
4. **No threshold change (FR-015)**: only *whether a non-pass on a preferred gate excludes*
   changes; every gate's pass/fail computation is unchanged.
5. **Transparency (FR-014)**: each `skipped_gates` entry (gate + reason) is surfaced on the
   candidate and carried verbatim into the advisor prompt / candidate detail.
6. **Relative strength** (new preferred confirmation): RS line = candidate cumulative return
   vs SPY over the momentum lookback; "near highs" = within a small band of its trailing
   max. Fails open (→ `skipped`) when SPY history is unavailable.

## Tests

- Acceptance scenarios US2.1–US2.5.
- SC-003: coverage count increases; 100% of added names fail/skip only preferred gates; zero
  added names fail an essential gate.
- SC-004: ordering invariant across mixed clean / skipped-gate sets.
- SC-009: default-off output byte-identical to baseline snapshot.
