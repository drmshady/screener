# Phase 1 Data Model: Portfolio Position Cards & Transaction Separation

No new **stored** entity, table, or persisted field is introduced. Every entity below is either
(a) an existing structure reused as-is, or (b) a **derived, in-response** synthesis object assembled
per request from existing data. This is consistent with FR-013 (presentation/synthesis only) and the
spec's Key Entities + Assumptions.

## Existing entities reused (unchanged)

- **Transaction** — append-only buy/sell record in the single-owner server blob. Structure
  unchanged; only its **surfacing location** moves to `/transactions` (FR-001, FR-010).
- **PortfolioHolding (+ levels/risk)** — per-ticker average-cost aggregation with
  `original_plan` / `current_condition` / `trailing` `LevelBlock`s, `risk`, `current_price`,
  `unrealized_pl(_pct)`, `priceable`, `data_notes`. Produced by `_assemble_holdings`. Unchanged.
- **PortfolioTotals** — includes `heat_ceiling_pct`, `heat_headroom_pct`, `realized_pnl`,
  `unrealized_pnl`, `total_pnl`, `win_rate`, `closed_trade_count`, `winning_trade_count`. Unchanged;
  the realized summary reads these directly.
- **RealizedTrade** — FIFO round-trip from `compute_realized_pnl` (`outcome` win/loss, `realized_pnl`,
  dates, `holding_days`). Unchanged; the ledger + realized detail live on `/transactions`, the
  summary aggregates them on `/portfolio`.
- **SentimentReport** — feature 014 durable, fingerprint-keyed narrative + label/score + spend-cap
  degrade. Unchanged; auto-loaded per card.

## New derived object: InstructionBlock (in-response, not stored)

Attached per holding on the `POST /portfolio/holdings` response. Additive and optional so existing
consumers stay byte-compatible.

| Field | Type | Notes |
|-------|------|-------|
| `status_label` | string (always present) | Neutral, non-directive status, e.g. `"Holding"`, `"Near stop"`, `"Stop breached"`, `"Target reached"`, `"Levels unavailable"`. Safe to show in any mode (FR-008). |
| `directive` | `"hold" \| "trim" \| "sell" \| null` | Present only when `directive_enabled` is true AND levels are sufficient. `null`/omitted otherwise. |
| `rationale` | string | Plain-language reason built from the same facts (e.g. `"Current-condition stop breached at $X"`). No advice phrasing beyond the gated verb. |
| `inputs` | object | Echo of the deciding facts for auditability/determinism: `{ level_status, distance_to_stop_pct, heat_headroom_pct, stage? }`. |

**Derivation** (pure `derive_instruction`, Decision 2): precedence Sell (stop breached) → Trim (near
stop OR heat ceiling breached) → Hold (healthy/target-reached/gains-protected) → levels-unavailable
(no verb). Sentiment score is **not** an input (FR-007). Same inputs ⇒ same output (determinism).

## New response-level field: `directive_enabled` (boolean)

Top-level on the `/portfolio/holdings` response. True only under the single-owner directive carve-out
(personal-use flag ON + owner-secret set + not multi-user); mirrors the existing `personal_use_directive`
boolean pattern but uses the carve-out predicate (Decision 3). Drives whether cards render the verb.

## Derived synthesis views (frontend, in-memory)

- **Position Card** — per open holding (`net_quantity > 0` only; FR-003): ticker/company, quantity +
  cost basis, current price + unrealized P&L, status/stage (PipelineStageBadge + level status), stop
  + target (`current_condition` and `trailing`), recent news/events (source + as-of, or "nothing
  new"), auto sentiment (FR-006), and the instruction (verb or neutral). Holdings with `net_quantity
  <= 0` produce **no** card (US3); a repurchase makes `net_quantity > 0` again ⇒ a new card (FR-011).
- **Realized Trade Summary** — counts won/lost, win rate %, total realized P&L, from PortfolioTotals /
  RealizedTrade. Explicit "no realized history yet" empty state (FR-009).

## Cross-cutting invariants

- Every card and the summary carry `data_as_of`/staleness + disclaimer (FR-012) from the existing
  response envelope.
- No card is hidden or fails to load for missing levels/news/sentiment — each section degrades to an
  explicit statement (FR-004/005/006 edge cases).
