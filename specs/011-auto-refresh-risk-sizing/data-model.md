# Phase 1 Data Model: Automated Refresh, Realistic Levels & Smarter Sizing

No new persistent store and no schema migration. These entities are mostly
**in-flight response shapes** (levels, sizing, fair value) plus one **CI run**
concept and one **regenerable artifact**. Existing stores (Parquet prices,
`catalog.db` incl. `backtest_runs`, EDGAR slim cache, `manifest.json`) are reused.

---

## Daily update run (US1)

One scheduled CI execution of the publish chain.

| Field | Type | Notes |
|-------|------|-------|
| `triggered_at` | timestamp (UTC) | Cron fire time. |
| `target_session` | date \| null | Latest completed trading session, or null on a non-trading day. |
| `new_session` | bool | False ⇒ idempotent no-op (no build/push/deploy). |
| `steps` | ordered list | refresh → integrity → secret-scan → build → push → factory-rebuild. |
| `outcome` | enum | `success` \| `aborted` \| `noop`. |
| `failed_step` | enum \| null | Populated on `aborted`; drives the notification. |
| `published_data_as_of` | date \| null | Advances **only** on `success`. |
| `notified` | bool | Owner notified on `aborted` (and optionally on `success`). |

**Invariants.** `aborted` ⇒ no publish/deploy, last known-good snapshot stays live,
`notified = true`. `noop`/`aborted` ⇒ `published_data_as_of` unchanged (never
regresses). Determinism: same `target_session` snapshot ⇒ byte-equivalent published
artifact (FR-001a). **Efficiency:** the daily run executes only the incremental
ingest; the heavy Stooq bundle is a separate, infrequent run.

---

## Candidate risk levels (US2)

The post-screen overlay per candidate. Extends the existing `derive_levels`/level
fields.

| Field | Type | Notes |
|-------|------|-------|
| `entry` | money | Latest close (unchanged). |
| `stop_loss` | money | `> 0`, `< entry`. The clamped technical stop. |
| `tighter_stop_loss` | money \| null | Structure-based tighter variant (unchanged concept). |
| `take_profit` | money | `> entry`, ≤ reward ceiling. |
| `risk_distance` | money | `entry − stop_loss`, within `[lo,hi]·ATR` band. |
| `reward_distance` | money | `take_profit − entry`, within the documented bound. |
| `reward_ceiling_basis` | enum | `volatility_horizon` \| `fair_value` \| `measured_move`. |
| `bounds_applied` | list | Which clamps fired (e.g. `risk_cap`, `reward_ceiling`). |
| `levels_state` | enum | `ok` \| `insufficient_data`. |
| `rationale` | string | Neutral, zero-directive; how stop + target were set. |

**Invariants (FR-007/008/009/010/012).** `levels_state = ok` ⇒
`0 < stop_loss < entry < take_profit`, both distances inside their bounds, and
`take_profit` ≤ reward ceiling. Missing ATR/SMA-200/swing-low ⇒
`levels_state = insufficient_data` with no degenerate numbers. Deterministic on a
fixed snapshot row.

---

## Fair-value estimate (US3)

Per-candidate intrinsic/fair price, computed from existing point-in-time inputs.

| Field | Type | Notes |
|-------|------|-------|
| `fair_value` | money \| null | Estimated intrinsic/fair price; null when unavailable. |
| `basis` | enum | `valuation_yields` \| `intrinsic_model` (adopted basis, FR-018). |
| `source_as_of` | date | Underlying filing/period as-of (point-in-time). |
| `provenance` | string | Source tag (EDGAR concept set + model name + citation). |
| `trust_flag` | enum | `trusted` \| `unavailable` \| `stale` \| `out_of_range`. |
| `margin_of_safety` | float \| null | `(fair_value − price) / fair_value`; null when untrusted. |

**Invariants (FR-016/018, Edge Cases).** Only `trust_flag = trusted` estimates feed
sizing/target caps. `unavailable`/`stale`/`out_of_range` ⇒ fail-open, noted, not
used. A new computed intrinsic model is golden-fixture tested (Principle IV).

---

## Sizing suggestion (US3)

Extends `SizingResponse`.

| Field | Type | Notes |
|-------|------|-------|
| `suggested_shares` | int | Whole shares (floor), ≥ 0. |
| `suggested_position_value` | money | `shares · entry`. |
| `risk_per_trade_target` | money | `f · total_capital` used. |
| `risk_per_share` | money | `entry − stop_loss` (FR-007 stop). |
| `conviction_signal` | enum | Adopted in US4: `fair_value` \| `inverse_vol` \| `strategy_rank` \| `none`. |
| `conviction_adjustment` | enum \| null | `none` \| `boost` \| `cap` (e.g. `discount_boost`/`premium_cap` when `fair_value`). |
| `binding_constraint` | enum | `risk_target` \| `conviction` \| `position_cap` \| `sector_cap`. |
| `caps_respected` | bool | MUST be true for any non-zero suggestion. |
| `conviction_used` | bool | False ⇒ fail-open path noted in `reasoning` (was `fair_value_used`). |
| `resulting_position_pct_of_capital` | float | Unchanged. |
| `resulting_sector_pct_of_capital` | float | Unchanged. |
| `reasoning` | string | Names the binding constraint; zero-directive (FR-017). |

**Invariants (FR-013/014/017, SC-004).** Never breaches a cap. Wider
`risk_per_share` ⇒ fewer `suggested_shares`, all else equal. Deterministic on fixed
input. Existing zero-room "cannot size without breaching cap" behavior preserved.

---

## Method comparison artifact (US4 / FR-019)

A regenerable, deterministic report on a frozen snapshot.

| Field | Type | Notes |
|-------|------|-------|
| `snapshot_id` | string | The frozen snapshot the comparison ran on. |
| `methods` | list | Per candidate level-method / sizing-method / fair-value-basis. |
| `realism_metrics` | per method | Degenerate rate, risk/reward distance distributions vs price/ATR/horizon. |
| `robustness_metrics` | per method | Stability across the universe. |
| `coverage_metrics` | per method | Fair-value availability/trust rate. |
| `backtest_baseline_delta` | object | The level/exit change's effect on the committed baseline. |
| `selected_default` | per dimension | The adopted choice the artifact justifies. |
| `regenerates_identically` | bool | SC-007 determinism check. |

**Invariants (FR-019/020, SC-007).** Regenerates byte-identically on the frozen
snapshot. The adopted defaults equal `selected_default`. Any backtest-baseline
impact is stated explicitly; the re-baseline is gated on `backtest_baseline_delta`
showing an improvement.
