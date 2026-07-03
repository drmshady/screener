# Contract: Portfolio holdings — trailing level + heat (US3, US7)

**Endpoint (unchanged surface)**: `POST /portfolio/holdings` (and the held-position advisor
prompt routes that share `_assemble_holdings`). Request shape unchanged
(`PortfolioHoldingsRequest`: `total_capital`, `caps`, `strategy_slug`). Additive response
fields only.

## Response additions (backward-compatible)

```jsonc
{
  "holdings": [
    {
      // ... existing PortfolioHolding fields ...
      "levels": {
        "original_plan":     { /* LevelBlock — cost-anchored, as-of earliest buy */ },
        "current_condition": { /* LevelBlock — cost-anchored, current snapshot */ },
        "trailing": {          // NEW — chandelier-derived, current-price-anchored
          "entry": 152.10,             // current price basis
          "stop_loss": 138.40,         // above avg_cost for a winner
          "take_profit": null,
          "risk_distance": 13.70,
          "levels_state": "ok",
          "status": "gains_protected", // NEW status value (or "holding"/"insufficient_data")
          "rationale": "Trailing chandelier exit (22-bar high − 3×ATR) sits above the average cost, protecting unrealized gains.",
          "distance_to_stop_pct": -0.09
        }
      }
    }
  ],
  "totals": {
    "total_invested": 40000.00,
    "total_capital_at_risk": 1800.00,
    "total_capital_at_risk_pct": 0.045,
    "heat_ceiling_pct": 0.06,     // NEW
    "heat_headroom_pct": 0.015    // NEW — ceiling − current
  },
  "data_as_of": "…",
  "disclaimer": "…"
}
```

## Behavioral requirements

- **FR-007 (US3)**: for a holding trading materially above average cost, `trailing.stop_loss`
  sits **above** the purchase price (SC-004) and rises as price rises.
- **FR-008**: when current price ≤ average cost, or the chandelier value is missing,
  `trailing` is `null` or `levels_state = "insufficient_data"` and **never** presents a looser
  level than `current_condition` — no fabricated levels. Rationale is neutral, zero-directive.
- **FR-018 (US7)**: the three blocks render together with an at-a-glance status that
  distinguishes a `gains_protected` trailing stop from the cost-anchored blocks.
- **FR-010 / FR-019**: `totals` expose the heat ceiling and remaining headroom for legibility.
- **FR-015**: `data_as_of` + `disclaimer` present; determinism preserved; hosted directive-OFF.

## Reuse

`trailing` is built by the existing `_block(...)` + `_status(...)` helpers in
`portfolio/holding_levels.py` from the `chandelier_exit` column already produced by
`screening/engine.build_single_ticker_snapshot`. No new indicator, data source, or router.
