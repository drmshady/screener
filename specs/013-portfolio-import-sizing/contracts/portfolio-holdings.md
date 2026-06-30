# Contract: `POST /portfolio/holdings`

Return the owner's current holdings with **purchase-anchored levels** (both bases) and the
**risk-aware sizing** view, recomputed deterministically from the persisted transactions +
latest snapshot. Router: `backend/src/api/portfolio.py`.

## Request

```jsonc
{
  "total_capital": 100000,           // capital base for sizing (reuses existing config)
  "caps": { "per_position_cap_pct": 0.10, "per_sector_cap_pct": 0.25 },  // optional, defaults
  "strategy_slug": "midterm_52w_high_momentum"  // optional; levels strategy, default as today
}
```

Transactions are read from the persisted portfolio blob (not sent in the body), so this
endpoint reflects whatever the most recent `/portfolio/import` stored.

## Behavior

1. Aggregate persisted `transactions[]` → average-cost holdings (`portfolio/aggregation.py`).
2. For each **open, priceable** holding:
   - **original_plan** levels: `build_single_ticker_snapshot(ticker, as_of=earliest_buy_date)`
     → `derive_bounded_levels`, `entry` overridden to `avg_cost` (Decision 4).
   - **current_condition** levels: `build_single_ticker_snapshot(ticker)` (latest) →
     `derive_bounded_levels`, `entry` = `avg_cost`.
   - **risk**: `size_position` with `stop_loss = current_condition.stop_loss`,
     `total_capital`, `caps`; plus actual capital-at-risk + over-risk flag (Decision 5).
3. Out-of-coverage / no-OHLCV tickers ⇒ `priceable=false`, facts intact, no levels/risk,
   neutral note (Decision 7) — never breaks the response.
4. Compute portfolio totals (total invested, total capital-at-risk).

## Response `200`

```jsonc
{
  "holdings": [
    {
      "ticker": "AAPL",
      "net_quantity": 30,
      "avg_cost": 182.40,
      "cost_basis": 5472.00,
      "earliest_buy_date": "2026-02-10",
      "most_recent_buy_date": "2026-04-22",
      "realized_pl": 0.00,
      "status": "open",
      "priceable": true,
      "sector": "Information Technology",
      "current_price": 205.10,
      "unrealized_pl": 681.00,
      "unrealized_pl_pct": 0.1244,
      "data_notes": [],
      "levels": {
        "original_plan": {
          "entry": 182.40, "stop_loss": 168.90, "take_profit": 214.30,
          "tighter_stop_loss": 171.20, "risk_distance": 13.50, "reward_distance": 31.90,
          "reward_ceiling_basis": "r_multiple", "bounds_applied": [],
          "levels_state": "ok", "status": "holding",
          "distance_to_stop_pct": -0.176, "distance_to_target_pct": 0.045,
          "rationale": "Stop uses the 200-day SMA trend stop with risk distance bounded to 13.50; target uses 2R and is checked against the r multiple ceiling."
        },
        "current_condition": { "...": "same shape, latest-snapshot inputs" }
      },
      "risk": {
        "recommended_shares": 18, "recommended_value": 3691.80,
        "actual_shares": 30, "actual_value": 5472.00,
        "actual_capital_at_risk": 405.00, "actual_capital_at_risk_pct": 0.00405,
        "per_trade_risk_budget": 1000.00,
        "over_risk": false, "binding_constraint": null,
        "fail_open": true,
        "sizing_reasoning": "Risk-per-trade target is 18 shares ...; risk-per-trade sizing only (no conviction modulation adopted). Binding constraint: risk target."
      }
    }
  ],
  "totals": {
    "total_invested": 5472.00,
    "total_capital_at_risk": 405.00,
    "total_capital_at_risk_pct": 0.00405
  },
  "data_as_of": "2026-06-30T21:00:00Z",
  "disclaimer": "For informational purposes only; not investment advice."
}
```

## Guarantees

- **Determinism (SC-006)**: identical snapshot + persisted transactions ⇒ byte-identical
  response across runs.
- **Disclosure (FR-019)**: `data_as_of` (newest contributing snapshot) + `disclaimer` always
  present.
- **No directive language (FR-020)**: every label/`status`/`reasoning`/`rationale` is
  descriptive; `status` ∈ {holding, stop_breached, target_reached, insufficient_data}.
- **No strategy/baseline change (FR-021)**: only `derive_bounded_levels` and `size_position`
  are *called*; neither is modified.
