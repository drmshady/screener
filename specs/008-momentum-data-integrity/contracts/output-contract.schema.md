# Contract: Strategy Output Contract (strategy-agnostic)

**Feature**: 008-momentum-data-integrity

Defines the shape every strategy's output contract MUST take so the single detection engine can run it unchanged (FR-001). A contract is a declarative list of invariants; the engine evaluates each against every returned candidate row plus the row's precomputed series-integrity signals.

## Engine entry point

```text
evaluate_contract(results_df, contract, *, snapshot_signals) -> results_df'
```

- **Input**: `results_df` = the DataFrame returned by `strategy.rules(universe)`; `contract` = `Strategy.output_contract`; `snapshot_signals` = the per-row series-integrity columns (data-model §8).
- **Output**: the same rows with two added columns — `data_integrity_warnings` (list of candidate-severity violations) and `data_suspect` (bool). Aggregate-severity violations are returned via `results_df'.attrs["integrity_notes"]` for the caller to append to `data_notes`.
- **Guarantees**: pure / deterministic (no network, no wall-clock); never raises on a single bad row (a row that errors a predicate is itself flagged, not allowed to crash the screen — US1-AC: "the run does not crash"); never drops a row (flag-not-exclude, FR-017).

## Invariant evaluation rules

1. Every invariant is evaluated for every candidate row (order is declaration order, for stable messages).
2. A `False` predicate with `severity=candidate` → append a `DataIntegrityWarning{figure, rule, reason}` and set `data_suspect=True`.
3. A `False` predicate with `severity=aggregate` → record once in `integrity_notes`.
4. A `True` predicate adds nothing (no false positives — FR-005/SC-002).
5. A predicate that needs series data reads ONLY `snapshot_signals` columns; it never performs I/O.

## Caller obligations (live screen — `_screen_from_universe`)

- Run `evaluate_contract` after `rules()` and before building `Candidate`s.
- Extend the sort to `["data_suspect", "warning_count", "score", "ticker"]` so flagged names sort last (FR-018) while clean order is preserved.
- Append `integrity_notes` and a "flagged/corrected N of M names" line to `data_notes` (FR-004, US4-AC4).

## Caller obligations (offline harness)

- Reuse the **same** contract + engine over a frozen snapshot for the seeded-defect test (no separate detection logic), proving one contract / two enforcement points.

## Strategy-agnostic proof obligation (FR-006 / SC-009)

The value strategy's existing implausibility backstop (currently inline in `engine.py::_value_row_fields`, dropping a name when any yield blows past a bound) MUST be expressible as a value-domain invariant in `midterm_value_composite`'s contract with **no engine change and no behaviour change** to the value strategy.
