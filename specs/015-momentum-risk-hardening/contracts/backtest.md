# Contract: Backtest — strengthened evidence (US1, US2)

**Endpoint (unchanged surface)**: `GET /strategies/{slug}/backtest` — served read-only from
the **baked** `backend/data/backtests/<slug>.json`. No request-shape change. Additive
response fields only.

## Response additions (backward-compatible)

```jsonc
{
  // ... existing fields (strategy_slug, summary_metrics, yearly_metrics[], bias_check[],
  //     coverage_notes, equity curve, data_as_of, disclaimer) ...
  "exit_model": "fixed_horizon | modeled_levels",     // existing (011-US4)
  "rebalance_cadence": "A | Q | M",                    // NEW — cadence of this run
  "cost_model": { "per_side_bps": 10, "applied": true }, // NEW — disclosed cost
  "yearly_metrics": [
    {
      "year": 2015,
      "total_return": 0.12,
      "trade_count": 7,               // surfaced (already computed)
      "reliability": "ok | low_sample" // NEW — thin-sample flag
      // ... existing per-year metric fields ...
    }
  ],
  "bias_check": [
    { "item": "costs", "passed": true, "note": "modeled: 10 bps/side" } // CHANGED value
  ]
}
```

## Behavioral requirements

- **FR-001**: entries distributed across multiple rebalance dates per year; total trades
  materially larger than the current ~80 (SC-001).
- **FR-002 / Principle III**: `cost_model.applied = true` and the `costs` bias-check item
  passes with a modeled note (no self-reported "not included" while passing) (SC-002).
- **FR-003 / FR-020**: every `yearly_metrics[]` carries `trade_count` + `reliability`; the
  frontend `WalkForwardMetricsPanel` visually distinguishes `low_sample` years (SC-011).
- **FR-004 (US2)**: a `modeled_levels` run uses the same bounded stop/target the live screen
  displays, conservative when both are touched intrabar (runner `_modeled_exit_return`,
  already implemented).
- **FR-005 / FR-006**: the served baseline JSON changes only after a documented improvement
  in the comparison artifact; re-running the harness on the same snapshot yields
  byte-identical JSON (SC-003).
- **FR-015**: `data_as_of` + `disclaimer` present; determinism preserved.

## Deployment note

The strengthened JSON is produced **locally** and **baked into the image**; the hosted
backend never runs the backtest. Shipping is via the existing `scripts/publish_chain.ps1`
(or daily-refresh `force_rebuild`). This matches the 010 hosted-mode contract exactly.
