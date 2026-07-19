# Contract: `POST /portfolio/holdings` — additive instruction fields

Extends the **existing** endpoint (feature 013/016). All additions are optional/additive: when the
carve-out is off and levels are absent, the response is byte-compatible with today for existing
consumers (they simply ignore the new fields).

## Request

Unchanged. `{ total_capital, strategy_slug, available_cash? }` (momentum-hardwired).

## Response additions

### Top-level

```jsonc
{
  // ...existing: holdings[], totals, realized_trades[], data_as_of, disclaimer...
  "directive_enabled": false        // NEW — true only under the single-owner carve-out
}
```

### Per holding (each `holdings[i]`)

```jsonc
{
  // ...existing: ticker, net_quantity, avg_cost, current_price, unrealized_pl(_pct),
  //    levels{original_plan,current_condition,trailing}, risk, priceable, data_notes...
  "instruction": {                  // NEW — always present when the holding is priceable
    "status_label": "Near stop",    // neutral, always safe to display
    "directive": "trim",            // "hold"|"trim"|"sell" ONLY when directive_enabled; else null/omitted
    "rationale": "Within 3% of the current-condition stop; heat headroom 4%.",
    "inputs": {
      "level_status": "ok",
      "distance_to_stop_pct": 0.021,
      "heat_headroom_pct": 0.04,
      "stage": null                 // stage is frontend-owned; echoed only if provided
    }
  }
}
```

## Semantics (see research Decision 2)

- Precedence: **sell** (`current_condition.status == "stop_breached"`) → **trim** (near stop
  `|distance_to_stop_pct| <= 0.03` OR `totals.heat_headroom_pct <= 0`) → **hold** (otherwise, incl.
  `target_reached`/`gains_protected`).
- `levels_state == "insufficient_data"` ⇒ `status_label == "Levels unavailable"`, `directive` null,
  card still renders (FR-004 edge case).
- `directive` is `null`/omitted whenever `directive_enabled == false` (FR-008) — the neutral
  `status_label` is always present.
- Sentiment score is **never** an input (FR-007).
- Deterministic: identical inputs ⇒ identical `instruction`.

## Tests

- Golden fixtures for each branch (sell/trim-near-stop/trim-heat/hold/target-reached/insufficient).
- `directive_enabled=false` ⇒ no `directive` verb on any holding (neutral-default contract test).
- `directive_enabled=true` ⇒ verb present and equals the branch's expected value.
- Determinism: same request twice ⇒ identical serialized `instruction` blocks.
- Back-compat: existing `/holdings` consumers unaffected (extra keys ignored).
