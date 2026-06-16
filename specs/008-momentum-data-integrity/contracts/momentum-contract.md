# Contract: Mid-Term Momentum Output Contract (pilot)

**Feature**: 008-momentum-data-integrity | **Strategy**: `midterm_52w_high_momentum`

The concrete invariants for the pilot (FR-003). Each row is `(candidate, signals)`. Tolerances marked **[A/B]** are initial defaults to be calibrated on the 2026-06-12 snapshot before locking (research Decision 9); the **10% divergence** threshold is fixed by the spec.

## Invariants

| name | family | severity | predicate (satisfied when…) | figure |
|------|--------|----------|------------------------------|--------|
| `coherence.dist_to_high` | coherence | candidate | `abs(dist_to_high − (52w_high−close)/close) ≤ 1e-6` | `dist_to_high` |
| `coherence.entry_eq_close` | coherence | candidate | `abs(entry − close) ≤ 0.01` | `entry` |
| `gate.proximity` | gate | candidate | `dist_to_high ≤ proximity_pct` (the hard gate actually holds at the stated parameter) | `dist_to_high` |
| `score.reproduces` | score | candidate | `abs(score − return_12_1·vol_scalar/(1+dist_to_high)) ≤ tol` **[A/B: rel 1e-3]** | `score` |
| `level.ordering` | level | candidate | `0 < stop_loss < entry < take_profit` | `stop_loss` |
| `level.r_multiple` | level | candidate | `abs((take_profit−entry)/(entry−stop_loss) − take_profit_r_multiple) ≤ tol` **[A/B: 1e-2]** | `take_profit` |
| `value_domain.finite` | value_domain | candidate | no NaN/inf in `{close, 52w_high, return_12_1, atr, score, stop_loss, take_profit}` | (per figure) |
| `value_domain.positive` | value_domain | candidate | `close > 0` and `atr > 0` | `close` |
| `value_domain.return_plausible` | value_domain | candidate | `−0.95 ≤ return_12_1 ≤ R_MAX` **[A/B: R_MAX ≈ 9.0, i.e. +900%]** | `return_12_1` |
| `value_domain.high_plausible` | value_domain | candidate | `52w_high ≥ close` and `52w_high ≤ close·H_MAX` **[A/B: H_MAX ≈ 12]** | `52w_high` |
| `series.dates_ok` | series | candidate | `series_dates_ok` (strictly increasing, unique dates) | — |
| `series.no_unexplained_jump` | series | candidate | `series_max_session_move ≤ JUMP_MAX` **[A/B: 0.40]** OR `corporate_action_in_window` | `return_12_1` |
| `series.seam_consistent` | series | candidate | `seam_consistent` (Stooq↔overlay factor derivable + stable) | `close` |
| `identity.single_share_class` | identity | candidate | `share_class_consistent` | `close` |
| `aggregate.flag_count` | (n/a) | aggregate | informational: count of flagged names → data note | — |

## Notes

- `gate.proximity` catches the "listed-but-doesn't-actually-pass" defect even when coherence holds (US1-AC3).
- `series.no_unexplained_jump` does **not** fire when the move is explained by a known corporate action (FR-015) — `corporate_action_in_window` is sourced from the providers' adjustment data, not pure statistics.
- `value_domain.return_plausible` is the momentum analogue of the value strategy's yield backstop (FR-004 momentum failure mode #4); BELFB's pre-fix +221% trips it, and after the seam fix (Decision 2) a correct BELFB does not.
- A row that errors any predicate is flagged with a generic `value_domain.finite`-class violation rather than crashing the screen (output-contract.schema.md).

## Determinism

Every predicate is a pure function of the row + precomputed signals; the same frozen snapshot yields the identical warning set on every run (FR-024 / SC-005).
