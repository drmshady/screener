# Phase 1 Data Model: Momentum Risk & Validation Hardening

All changes are **additive/optional** extensions to existing Pydantic models and the baked
backtest JSON. No existing field is removed or retyped; older payloads remain valid so the
BFF proxy and frontend Zod schemas widen without breaking. Defaults preserve current output.

---

## 1. Backtest run (strengthened) — `backend/data/backtests/<slug>.json` + `GET /strategies/{slug}/backtest`

Extends the artifact written by `backtests/runner.run_backtest`.

| Field | Type | New? | Notes |
|---|---|---|---|
| `exit_model` | `"fixed_horizon" \| "modeled_levels"` | exists | Already present (011-US4). |
| `rebalance_cadence` | `"A" \| "Q" \| "M"` | **new** | Cadence used for this run (US1/FR-001). Default `Q`. |
| `cost_model` | object `{ per_side_bps: number, applied: bool }` | **new** | Disclosed per-side cost (US1/FR-002). |
| `bias_check[].costs` | existing bias-check item | changed value | `passed: true`, note = "modeled: N bps/side" (no longer "not included"). |
| `yearly_metrics[].trade_count` | int | exists/surfaced | Per-period trade count (already computed in `metrics.yearly_metric`). |
| `yearly_metrics[].reliability` | `"ok" \| "low_sample"` | **new** | Thin-sample flag (US1/FR-003, US7/FR-020). |
| `coverage_notes` | string[] | exists | Sparse-crisis-year note retained (must not be hidden by finer cadence). |
| `data_as_of`, `disclaimer` | string | exists | Preserved. |

**Validation / invariants**: same snapshot + same cadence + same cost ⇒ byte-identical JSON
(FR-015). `reliability = "low_sample"` iff `trade_count < SCREENER_BACKTEST_MIN_RELIABLE_TRADES`.

---

## 2. Exit-model comparison artifact (not served; local + committed under specs/ and `backend/backtests/comparison/`)

| Field | Type | Notes |
|---|---|---|
| `strategy_slug` | string | `midterm_52w_high_momentum`. |
| `variants` | object keyed by `fixed_horizon` \| `modeled_levels` \| `regime_overlay` | Each carries total return, hit rate, avg win, avg loss, max drawdown, trade count. |
| `verdict` | `"adopt_modeled" \| "keep_fixed" \| "adopt_regime_overlay" \| "keep_baseline"` | Documented adoption decision (FR-005/FR-006). |
| `decision_note` | string | One-line justification; reproducible. |
| `computed_at`, `snapshot_id` | string | For reproducibility. |

**Invariant**: the committed baseline (§1) changes **only** when `verdict` documents an
improvement; artifact retained either way.

---

## 3. Holding trailing level — `HoldingLevels` (`models/portfolio.py`) + `POST /portfolio/holdings`

| Field | Type | New? | Notes |
|---|---|---|---|
| `HoldingLevels.original_plan` | `LevelBlock` | exists | Cost-anchored, as-of earliest buy. |
| `HoldingLevels.current_condition` | `LevelBlock` | exists | Cost-anchored, current snapshot. |
| `HoldingLevels.trailing` | `LevelBlock \| None` | **new** | Chandelier-derived, **current-price**-anchored (US3/FR-007). `None`/`insufficient_data` when price ≤ cost or chandelier missing (FR-008 graceful degrade). |

`LevelBlock` gains an at-a-glance status value:

| Field | Type | New? | Notes |
|---|---|---|---|
| `status` | `"holding" \| "stop_breached" \| "target_reached" \| "gains_protected" \| "insufficient_data"` | **+`gains_protected`** | New status only used by the trailing block when its stop sits above cost (US7/FR-018). Existing values unchanged. |
| `risk_distance` | `Decimal \| None` | exists | Reused for candidate risk-distance display. |

**Invariant**: `trailing.stop_loss`, when present, is **never looser** than
`current_condition.stop_loss` and, for a winner, sits above `avg_cost` (SC-004). Rationale
zero-directive (FR-008).

---

## 4. Portfolio heat — `PortfolioTotals` + `SizingResponse` (`models/portfolio.py`)

`PortfolioTotals` (returned by `POST /portfolio/holdings`):

| Field | Type | New? | Notes |
|---|---|---|---|
| `total_capital_at_risk` | Decimal | exists | Sum of per-holding capital-at-risk. |
| `total_capital_at_risk_pct` | float | exists | Of total capital. |
| `heat_ceiling_pct` | float | **new** | Configured ceiling (US4/FR-010). |
| `heat_headroom_pct` | float | **new** | `ceiling − current` (US7/FR-019). |

`SizingResponse` (returned by sizing path):

| Field | Type | New? | Notes |
|---|---|---|---|
| `binding_constraint` | `"risk_target" \| "conviction" \| "position_cap" \| "sector_cap" \| "portfolio_heat" \| "conservative_fallback"` | **+2 values** | Adds `portfolio_heat` and `conservative_fallback` (US4/FR-009/FR-010). Existing values unchanged. |
| `conservative_fallback` | bool | **new** | True when a missing/invalid stop triggered the conservative size (FR-009). Replaces the fail-open cap-fill signal. |
| `risk_distance` | Decimal \| None | exists (`risk_per_share`) | Entry−stop, for candidate display (US7/FR-017). |
| `reward_to_risk` | float \| None | **new** | Reward-to-risk ratio for candidate display (US7/FR-017). |
| `portfolio_heat_after_pct` | float \| None | **new** | Resulting aggregate open risk if the position is taken (US7/FR-019). |

**Invariant**: with no stop, `suggested_shares` is strictly smaller than the legacy cap-fill
amount and `conservative_fallback = true` (SC-005). When heat binds, shares are reduced and
`binding_constraint = "portfolio_heat"`. Empty/single-holding portfolios behave sensibly.

---

## 5. Regime risk-budget overlay (config only — no persisted entity)

A pure mapping consumed by `portfolio/sizing.py`, not a stored model:

| Input | Source | Notes |
|---|---|---|
| regime | `regime/calculator.current_regime_response()` | Existing signal; unavailable ⇒ scale 1.0 (fail open). |
| `regime_risk_budget_enabled` | `flags` (`SCREENER_REGIME_RISK_BUDGET`) | Default OFF ⇒ byte-identical to today (FR-011, SC-006). |
| `unfavorable_scale` | `flags` (`SCREENER_REGIME_RISK_BUDGET_UNFAVORABLE`) | e.g. 0.5. |

**Invariant**: disabled ⇒ effective risk fraction identical to current; enabled ⇒ strictly
lower in an unfavorable regime than a favorable one (SC-006). Neutral, informational framing.

---

## 6. New operator flags — `lib/flags.py`

| Flag (env) | Default | Preserves today? |
|---|---|---|
| `SCREENER_BACKTEST_REBALANCE` | `Q` | Only affects a **re-run** artifact, not served output until re-baked. |
| `SCREENER_BACKTEST_COST_BPS` | `10` (per side) | Same — offline artifact only. |
| `SCREENER_BACKTEST_MIN_RELIABLE_TRADES` | `10` | Presentation flag only. |
| `SCREENER_SIZING_FALLBACK_ATR_MULT` | tuned so fallback < cap-fill | Changes only the *no-stop* sizing branch. |
| `SCREENER_PORTFOLIO_HEAT_CEILING` | set so it doesn't bind for typical single positions | Live sizing unchanged until heat actually binds. |
| `SCREENER_REGIME_RISK_BUDGET` | `0` (OFF) | Byte-identical sizing when OFF. |
| `SCREENER_REGIME_RISK_BUDGET_UNFAVORABLE` | `0.5` | Consulted only when overlay ON. |

All follow the existing `_TRUTHY` / `float(os.getenv(...))` idiom in `flags.py`.
