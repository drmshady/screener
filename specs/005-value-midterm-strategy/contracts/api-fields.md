# Contract: additive API fields (back-compatible)

No new endpoints. The value strategy flows through the **existing** routes:
`POST /screen` (run), `GET /strategies` + `/strategies/{slug}`,
`POST /analyze`, `GET /strategies/{slug}/backtest`, the 003 comparison route, and
the 004 advisor-prompt route. The only schema change is **additive, optional**
fields so older clients and the existing OpenAPI/contract tests stay green.

## `Candidate` and `AnalyzeResponse` (new optional fields, default `null`)

```
value_composite:    number | null
book_to_market:     number | null
earnings_yield:     number | null
cashflow_yield:     number | null
sales_yield:        number | null
f_score:            integer | null   # 0..9
f_score_evaluable:  integer | null   # 0..9
```

Guarantees:
- All default `null`; momentum candidates simply leave them `null`, so existing
  responses and tests are unaffected.
- Every value-strategy response still carries `data_as_of` and `disclaimer`
  (FR-012) and a populated `gate_results` list (FR-008).
- `gate_results[]` items keep the existing `{gate, status, detail}` shape; value
  gates are `Value composite`, `Piotroski F-Score`, `Leverage sanity`,
  `Sector concentration`.

## `/strategies` listing

The value strategy appears automatically (registry-driven) with full declaration
metadata: `name`, `citation`, `timeframe`, `holding_period_days`,
`regime_favorability`, `modifications[]` (each with its own `citation`),
`parameters`, `enabled_by_default`, and `backtest_summary` when the artifact
exists.

## `/strategies/{slug}/backtest`

Returns the `midterm_value_composite.json` artifact unchanged in shape: per-year
`yearly_metrics`, `summary_metrics`, `bias_check` (survivorship surfaced as
failing), `coverage_notes`, `equity_curve`.

## Advisor prompt (004) — `POST` advisor-prompt routes

Accept `strategy = midterm_value_composite`. The builder reads this strategy's
live declaration + its backtest artifact (survivorship path parameterized by
slug) and emits the value diagnostics (composite, F-Score, yields) in the
diagnostics lines. With `SCREENER_PERSONAL_USE_DIRECTIVE` off (default), the
prompt is neutral and emits zero directive language (no-directive lint passes).

## No-directive lint (frontend)

All new/updated surfaces MUST pass `frontend/tests/e2e/no-directive-copy.spec.ts`
(no "Buy"/"Sell"/"Recommended"/"Strong buy" in rendered copy), with the same
scoped exemption the 004 personal-use preview already uses.
