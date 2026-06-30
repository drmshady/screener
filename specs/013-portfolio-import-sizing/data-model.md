# Phase 1 Data Model: Portfolio Import, Purchase-Anchored Levels & Risk-Aware Sizing

All money is `Decimal` (quantized to cents via the existing `money()` helper); percentages are
floats in `[0,1]`. Entities below are new Pydantic models in `backend/src/models/portfolio.py`
unless noted. Browser-side mirrors live in `frontend/src/lib/store.ts` (Zustand) and Zod
schemas in `frontend/src/lib/api.ts`.

---

## Transaction

One buy or sell as recorded in the owner's sheet. Source of truth; persisted in the portfolio
blob. Holdings are always recomputed from these.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | Stable content hash (Decision 3) — `sha1(ticker|action|quantity|price|trade_date)` over normalized fields. **`source_row` is NOT in the hash** (it would change on row insertion/reordering and break idempotency); it is used only to disambiguate two byte-identical rows by appending an occurrence index (`#0`, `#1`) among same-hash rows. Drives idempotent re-import (FR-005/SC-003). |
| `ticker` | str | Upper-cased, trimmed. Required. |
| `action` | `"buy" \| "sell"` | Required; any other value ⇒ rejected row. |
| `quantity` | Decimal | > 0 required. Shares transacted (not signed). |
| `price` | Decimal | > 0 required. Price per share, USD. |
| `trade_date` | date (ISO) | Required, parseable. |
| `fees` | Decimal \| None | Optional. Default 0; reduces realized P/L if present. |
| `note` | str \| None | Optional free text. |
| `source_row` | int | 1-based sheet row, for the import summary + tiebreak. |

**Header aliases (case-insensitive, whitespace-trimmed)** — the owner's real sheet uses
descriptive headers, mapped to the canonical fields; all other columns (the sheet's
spreadsheet-computed columns) are ignored:

| Canonical field | Accepted header(s) |
|-----------------|--------------------|
| `trade_date` | `trade_date`, `date` |
| `action` | `action`, `type` |
| `ticker` | `ticker`, `stock`, `symbol` |
| `quantity` | `quantity`, `transacted units`, `units` |
| `price` | `price`, `transacted price (per unit)`, `price (per unit)` |
| `fees` | `fees`, `fee` |
| `note` | `note`, `notes` |

**Normalization (applied before validation, deterministic)**:
- **Numbers** (`quantity`, `price`, `fees`): strip `$`, thousands `,`, and surrounding
  whitespace, then parse `Decimal`. A placeholder dash `-`/`—` or empty cell in an optional
  column ⇒ treated as absent (fees default 0); in a required column ⇒ rejected.
- **`action`**: lower-cased; accepted only in `{buy, sell}`.
- **`ticker`**: upper-cased, trimmed.
- **`trade_date`**: parsed **day-first** for slash dates (`28/7/2025` ⇒ 28 Jul 2025;
  `5/9/2025` ⇒ 5 Sep 2025) and the month-name form (`9-Oct-2025`), plus ISO `YYYY-MM-DD`.
  Day-first is fixed (owner-confirmed) so parsing is deterministic and unambiguous.

**Validation (pure, `portfolio/transactions.py`)** → `(accepted: list[Transaction],
rejected: list[RejectedRow])`:
- Reject: missing ticker; `action` not in {buy, sell}; quantity/price non-numeric or ≤ 0;
  unparseable `trade_date`.
- **Dividend / other types** (`Div`, etc.) are **rejected as unsupported** with a clear,
  non-alarming reason (e.g. `"type 'div' is not a supported buy/sell transaction; cash
  dividends are not tracked in v1"`) — recognized data, surfaced in the summary, **never
  silently dropped** and never added to share count (a `Div` row's "units" do not change
  holdings).
- Tolerate unknown/extra columns; map known optional columns (`fees`, `note`).
- Never silently drop — every non-accepted row becomes a `RejectedRow` (FR-003, SC-002).

## RejectedRow

| Field | Type | Notes |
|-------|------|-------|
| `source_row` | int | 1-based sheet row reference. |
| `raw` | dict | The original cell values (for the owner to fix). |
| `reason` | str | Human-readable, e.g. "price '—' is not a positive number". |

---

## Holding (Position)

The owner's current net position in one ticker. **Derived, not persisted** — recomputed from
`transactions[]` + the snapshot on each `/portfolio/holdings` call (Decision 6). Aggregation in
`portfolio/aggregation.py` (pure).

| Field | Type | Notes |
|-------|------|-------|
| `ticker` | str | |
| `net_quantity` | Decimal | Σ(buy qty) − Σ(sell qty). |
| `avg_cost` | Decimal | Share-weighted average cost of **buys** (Decision 2). The level/sizing `entry` basis. |
| `cost_basis` | Decimal | `avg_cost × net_quantity` for open shares. |
| `earliest_buy_date` | date | Anchors original-plan levels; conveys plan age. |
| `most_recent_buy_date` | date | |
| `realized_pl` | Decimal | From sells under average cost (incl. fees). |
| `status` | `"open" \| "closed" \| "anomalous"` | `closed` when net_qty = 0; `anomalous` when net_qty < 0 (oversold, FR edge) — surfaced as a warning, never a short. |
| `priceable` | bool | False when out of coverage (Decision 7). |
| `sector` | str | From snapshot; "Unclassified" when unknown. |
| `current_price` | Decimal \| None | Latest snapshot close; None when not priceable. |
| `unrealized_pl` | Decimal \| None | `(current_price − avg_cost) × net_quantity`. |
| `unrealized_pl_pct` | float \| None | `(current_price − avg_cost) / avg_cost`. |
| `data_notes` | list[str] | Staleness / out-of-coverage notes (verbatim, like `/portfolio/quotes`). |
| `levels` | HoldingLevels | See below. |
| `risk` | HoldingRisk | See below. |

**Aggregation rules**:
- Group accepted transactions by ticker; order by `trade_date` then `source_row`.
- `avg_cost` = Σ(buy qty × buy price) / Σ(buy qty); unaffected by sells (average-cost method).
- `realized_pl` = Σ over sells of `(sell price − avg_cost_at_sale) × sell qty − fees`.
- Deterministic: identical inputs ⇒ identical output (SC-006).

---

## HoldingLevels

Both purchase-anchored bases (FR-009). Each base is the dict returned by
`strategies/levels.derive_bounded_levels` with `entry` forced to `avg_cost`.

| Field | Type | Notes |
|-------|------|-------|
| `original_plan` | LevelBlock | Inputs (ATR/SMA-200/swing-low) from `as_of=earliest_buy_date`; frozen. |
| `current_condition` | LevelBlock | Inputs from the latest snapshot; recomputed each run. |

**LevelBlock** (mirrors the `derive_bounded_levels` contract):
`entry` (= avg_cost), `stop_loss`, `tighter_stop_loss`, `take_profit`, `risk_distance`,
`reward_distance`, `reward_ceiling_basis`, `bounds_applied`, `levels_state`
(`"ok" | "insufficient_data"`), `rationale` (neutral), plus presentation-only:
`distance_to_stop_pct`, `distance_to_target_pct` (vs current price), and
`status` (`"holding" | "stop_breached" | "target_reached" | "insufficient_data"` —
informational, FR-011).

`insufficient_data` ⇒ documented neutral fallback, no error (FR-012).

---

## HoldingRisk

Recommended-vs-actual sizing + capital-at-risk (FR-014–FR-018). Built in
`portfolio/holding_risk.py` by calling `portfolio/sizing.size_position` with the holding's
**current-condition stop** and presenting the actual position alongside.

| Field | Type | Notes |
|-------|------|-------|
| `recommended_shares` | int | From `size_position` (risk-per-trade backbone, caps, fail-open). |
| `recommended_value` | Decimal | |
| `actual_shares` | Decimal | = `net_quantity`. |
| `actual_value` | Decimal | = `cost_basis` / market value as labelled. |
| `actual_capital_at_risk` | Decimal | `actual_shares × (avg_cost − current_condition.stop_loss)`, ≥ 0. |
| `actual_capital_at_risk_pct` | float | `/ total_capital`. |
| `per_trade_risk_budget` | Decimal | `risk_per_trade_fraction × total_capital`. |
| `over_risk` | bool | True when `actual_capital_at_risk > per_trade_risk_budget` or a cap is breached. |
| `binding_constraint` | str \| None | `"per_trade_budget" \| "position_cap" \| "sector_cap"` when over-risk. |
| `sizing_reasoning` | str | From `size_position` (neutral, names the binding constraint). |
| `fail_open` | bool | True when a conviction/modulator input was missing and sizing fell back to baseline (FR-018). |

When `current_condition.levels_state == "insufficient_data"` or `priceable == false`, risk is
omitted (None) with a neutral note rather than an error.

---

## Portfolio (envelope-level additions)

Lives in the existing opaque blob (`portfolio_state.json`), mirrored from the browser.

| Field | Type | Notes |
|-------|------|-------|
| `transactions` | list[Transaction] | Source of truth (Decision 6). |
| `sheet_id` | str \| None | Google spreadsheet id (non-secret). |
| `sheet_range` | str \| None | Tab/range, e.g. `Transactions!A1:G`. |
| `total_capital` | Decimal | Existing capital base (reused). |
| `caps` | PortfolioCaps | Existing per-position / per-sector caps (reused). |

The **OAuth access token is never stored** here or anywhere (FR-001).

## PortfolioTotals (in the holdings response)

| Field | Type | Notes |
|-------|------|-------|
| `total_invested` | Decimal | Σ open-holding market value (FR-017). |
| `total_capital_at_risk` | Decimal | Σ `actual_capital_at_risk` over open, priceable holdings (FR-017). |
| `total_capital_at_risk_pct` | float | `/ total_capital`. |

---

## Import Result

Returned by `POST /portfolio/import`.

| Field | Type | Notes |
|-------|------|-------|
| `accepted_count` | int | Net-new accepted transactions applied. |
| `duplicate_count` | int | Previously-seen rows skipped (idempotency, FR-005). |
| `rejected` | list[RejectedRow] | Full reject list with reasons (FR-003). |
| `transactions_total` | int | Total transactions in the portfolio after import. |
| `data_as_of` | str | (FR-019) |
| `disclaimer` | str | (FR-019) |

---

## Watchlist entry-timing (US4) — no new persisted entity

US4 adds no backend model. The watchlist re-uses the existing `WatchlistEntry` (browser
store) and reads live entry-timing from the **existing** `GET /analyze/{ticker}` response
(`entry_timing {state, summary, components}` + `data_as_of`, feature-012). Optionally, the
last-seen `entry_timing.state` is cached per watch entry in the Zustand store
(`schema_version` bump) to flag a newly entry-ready name — presentation only, no strategy
rule/default/citation change (FR-021/FR-026).

---

## State transitions

- **Transaction**: parsed → (accepted | rejected). Accepted rows are immutable once stored
  (keyed by `id`); re-import adds only ids not already present.
- **Holding.status**: `open` (net_qty > 0) → `closed` (net_qty = 0 after sells) or
  `anomalous` (net_qty < 0, warning).
- **Holding.levels.*.status**: `holding` → `stop_breached` / `target_reached` as current price
  crosses a level (informational only); `insufficient_data` when inputs are missing.
