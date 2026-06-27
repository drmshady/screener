# Contract: Entry-Timing Overlay (US1)

`screening/entry_timing.py` — pure, deterministic post-screen overlay attached **only** to
`midterm_52w_high_momentum` candidates (FR-023). Composes the six components + disqualifiers
into an `EntryTimingClassification` (data-model §1) from the scalar snapshot columns. No I/O,
no network, no wall-clock dependence.

## Signature

```python
def classify_entry_timing(row: Mapping[str, Any], *, thresholds: EntryThresholds) -> EntryTimingClassification
```

`row` must carry: `close`, `sma_200`, `pivot`, `base_type`, `base_length_weeks`,
`base_depth`, `breakout_volume_ratio`, and (for disqualifiers) the climax-top advance
measure, gap-above-pivot measure, and any recent-catalyst signal from the events snapshot.
`thresholds` are resolved from `lib/flags.py` (documented defaults + ranges).

## Invariants

1. **State derivation (FR-001/003)**: `entry_ready` ⟺ all six components `pass` AND no
   `forces_not_entry_ready` disqualifier; `not_entry_ready` ⟺ ≥1 component `fail` OR a
   forcing disqualifier; `entry_undetermined` ⟺ ≥1 component `undetermined` AND none `fail`
   AND no forcing disqualifier.
2. **No false entry-ready (FR-002a/003)**: a missing required input (undetectable base/pivot,
   < 50 days volume, < 200 days SMA-200) yields `undetermined` for that component → the
   candidate is never `entry_ready` on absent data.
3. **Component thresholds (FR-002)** exactly as data-model §1a; arithmetic reproducible from
   the exposed diagnostics (SC-001).
4. **Disqualifiers (FR-022)**: `climax_top` (+25–50% in 1–3 wk after an extended uptrend) and
   `huge_gap` (>+5% above pivot) force `not_entry_ready` and exclude when `entry_ready_only`
   is ON; `short_lived_catalyst` attaches a non-directive warning only and does **not**
   change `state`.
5. **Momentum-only (FR-023)**: the overlay is invoked solely for
   `midterm_52w_high_momentum`; VCP / value-composite / ATR-breakout candidates carry no
   `entry_timing`.
6. **Additive (FR-006)**: the overlay never changes selection, ranking, gates, thresholds,
   citations, or the backtest baseline of any strategy.
7. **Determinism (FR-008)**: same `row` → identical classification; no randomness/clock.
8. **Zero directive language (FR-007/SC-008)**: every string (`summary`, component/disqualifier
   `reason`) describes a technical state; never "buy"/"sell"/"recommended"/"strong buy".
   Attribution to Minervini (2013) for base/pivot/breakout; never labelled CAN SLIM.

## Filter behaviour (FR-005)

`entry_ready_only` screen parameter (default **OFF**): OFF → all candidates returned, each
annotated; ON → only `entry_ready` candidates returned (a strict subset of the same
selection/ordering — SC-002). With ON the screen may legitimately return zero candidates;
the empty state explains why (spec edge case).

## Tests (test-first where indicator-backed)

- Acceptance scenarios US1.1–US1.8 reproduced on a frozen snapshot.
- Each component pass/fail/undetermined boundary; each disqualifier trigger boundary.
- Determinism: repeat runs of the same snapshot yield identical classification + ordering.
- Directive-language lint over all emitted copy.
