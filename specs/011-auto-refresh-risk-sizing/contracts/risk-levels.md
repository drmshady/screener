# Contract: Risk Levels — `derive_levels` v2 (US2, FR-007…012)

**Surface:** `derive_levels(row) -> dict` in
[`midterm_52w_high_momentum.py`](../../../backend/src/strategies/midterm_52w_high_momentum.py#L477)
(and the shared method used by `midterm_value_composite`). Same call sites
([`api/analyze.py`](../../../backend/src/api/analyze.py)); the **return shape gains
metadata** but stays backward-compatible (`entry`, `stop_loss`,
`tighter_stop_loss`, `take_profit` keys remain).

## Inputs (from the screen row, unchanged sources)

`close`, `atr`, `sma_200`, `contraction_low_20`, horizon (strategy
`holding_period_days`), and — when trusted — the fair-value estimate.

## Derivation

1. `entry = close`.
2. Stop = existing technical stop (structure / trend / ATR per `stop_mode`), then
   **clamp `risk_distance = entry − stop`** into `[lo·atr, hi·atr]` (and a
   price-fraction cap for low-priced names). Result: `0 < stop_loss < entry`.
3. `take_profit = entry + R · risk_distance`, then **cap at the reward ceiling** =
   `min(volatility_horizon_limit, fair_value_if_trusted, measured_move_if_used)`.
   Record `reward_ceiling_basis`.
4. Missing required input ⇒ `levels_state = "insufficient_data"` with
   `stop_loss = take_profit = None` (no degenerate numbers).
5. Build `rationale`: neutral, zero-directive, names the stop rule + the binding
   ceiling.

## Invariants

- `levels_state == "ok"` ⇒ `0 < stop_loss < entry < take_profit` (FR-007).
- `risk_distance` ∈ `[lo·atr, hi·atr]`; `reward_distance` within its documented
  bound (FR-008).
- `take_profit` ≤ reward ceiling (FR-009).
- Insufficient inputs ⇒ explicit state, never degenerate (FR-010).
- Byte-identical on a fixed row (FR-012).
- No screening/selection rule, gate, ranking, or citation change.

## Parameters (documented defaults + ranges, like existing ones)

`risk_distance_atr_lo`, `risk_distance_atr_hi`, `take_profit_r_multiple` (reused),
`reward_ceiling_z`, `reward_ceiling_use_fair_value` (bool). Final values set by the
US4 artifact.

## Tests (property/fixture, written first)

Across a real snapshot: 100% non-degenerate within bounds, 0 targets beyond the
ceiling (SC-003); far-below-SMA-200 name → bounded risk distance (Acceptance #2);
recompute → byte-identical (Acceptance #3); rationale present + zero-directive
(Acceptance #4); missing-input row → `insufficient_data`.
