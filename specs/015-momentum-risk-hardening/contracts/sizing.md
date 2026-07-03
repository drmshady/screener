# Contract: Position sizing — safe fallback, portfolio heat, regime budget (US4, US5, US7)

**Surface**: `size_position(SizingRequest) -> SizingResponse` (`portfolio/sizing.py`), used by
the analyze/portfolio sizing path. Request shape unchanged (optional `stop_loss`, `holdings`,
`caps`, conviction inputs already present). Additive response fields + two new
`binding_constraint` values.

## Response additions (backward-compatible)

```jsonc
{
  // ... existing SizingResponse fields (suggested_shares, suggested_position_value,
  //     caps_respected, reasoning, risk_per_trade_target, risk_per_share,
  //     conviction_signal, conviction_adjustment, conviction_used) ...
  "binding_constraint": "risk_target | conviction | position_cap | sector_cap | portfolio_heat | conservative_fallback", // +portfolio_heat, +conservative_fallback
  "conservative_fallback": false,        // NEW — true when a missing/invalid stop forced a conservative size
  "reward_to_risk": 2.6,                 // NEW — for candidate display (US7/FR-017)
  "portfolio_heat_after_pct": 0.052      // NEW — aggregate open risk if this position is taken (US7/FR-019)
}
```

## Behavioral requirements

- **FR-009 (US4)**: with `stop_loss` missing/invalid, `suggested_shares` is materially smaller
  than the legacy cap-fill amount, `conservative_fallback = true`, and `reasoning` states a
  conservative fallback was used (SC-005). This **replaces** the fail-open-to-cap-fill branch.
- **FR-010 (US4)**: aggregate open risk (sum of per-position risk-to-stop for `holdings` + the
  proposed position) is bounded by `SCREENER_PORTFOLIO_HEAT_CEILING`. When it binds,
  `suggested_shares` is reduced and `binding_constraint = "portfolio_heat"`. Empty/single-
  holding portfolios behave sensibly.
- **FR-011 (US5)**: when `SCREENER_REGIME_RISK_BUDGET` is ON, the effective
  `risk_per_trade_target` is scaled down in an unfavorable regime (existing
  `regime/calculator` signal) and unchanged in a favorable one; regime unavailable ⇒ scale
  1.0 (fail open, never error). When OFF, output is **byte-identical** to current sizing
  (SC-006).
- **FR-017 (US7)**: `risk_per_share` (risk distance) + `reward_to_risk` presented plainly.
- **No regression (US4 AS-3)**: with a valid stop and ample room, output matches the existing
  risk-per-trade result.
- **FR-015**: `data_as_of` + `disclaimer` on the enclosing response; determinism preserved;
  neutral zero-directive language.

## Defaults preserve today

`SCREENER_PORTFOLIO_HEAT_CEILING` defaults high enough not to bind for typical single
positions; `SCREENER_REGIME_RISK_BUDGET` defaults OFF; the conservative fallback only changes
the previously-fail-open no-stop branch. A plain deploy with flags unset is byte-identical to
production sizing today.
