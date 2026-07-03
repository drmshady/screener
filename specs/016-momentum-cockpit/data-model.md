# Phase 1 Data Model: Momentum Cockpit

**Feature**: 016-momentum-cockpit | **Date**: 2026-07-03

This feature adds one new backend model module (`models/pipeline.py`), extends
`models/portfolio.py` additively, and adds one frontend-owned persisted key. Much of the
transaction/P&L substrate **already exists** from feature 013 (`Transaction`,
`PortfolioTransactionsSlice`, `Holding.realized_pl`, `PortfolioHolding.unrealized_pl`); 016
wires it to new surfaces (manual entry, FIFO round-trip history, board) rather than inventing
it. All additions are optional/additive so existing payloads stay byte-identical.

---

## New entities (backend — `models/pipeline.py`)

### FitFacts
The independent boolean facts `score_fit` consumes (pure input; the API layer computes each
from existing outputs).

| Field | Type | Source |
|---|---|---|
| `entry_ready` | bool | `classify_entry_timing(...) == entry_ready` |
| `meaningful_size_survives` | bool | `SizingResponse`: `suggested_shares > 0` AND `caps_respected` AND NOT `conservative_fallback` |
| `heat_headroom_ok` | bool | `SizingResponse.binding_constraint != "portfolio_heat"` |
| `sector_room_ok` | bool | `SizingResponse.binding_constraint != "sector_cap"` |
| `not_overconcentrated` | bool | resulting position pct ≤ per-position cap (from `SizingResponse`) |
| `regime_allows_entries` | bool | regime favorability for new momentum entries |
| `reward_to_risk_ok` | bool | `SizingResponse.reward_to_risk ≥ fit_reward_to_risk_floor()` (default 1.5) |
| `cash_sufficient` | bool | `SizingResponse.binding_constraint != "available_cash"` (and suggested_shares > 0) |

### FitResult
| Field | Type | Notes |
|---|---|---|
| `score` | int (0–100) | internal, deterministic weighted sum of facts; used for sort order only — not shown raw |
| `fit_band` | `Literal["strong_fit","partial_fit","poor_fit","blocked"]` | derived from score/facts |
| `facts` | `FitFacts` | echoed so the UI can render which failed |
| `failed_facts` | `list[str]` | the fact names that are False (convenience for the UI) |
| `rationale` | str | neutral, from a fixed fact→phrase map (no directive verbs) |
| `directive_label` | `Literal["consider_entry","hold_off","size_down","pass"] \| None` | **omitted** unless `personal_use_directive()` AND not hosted (pydantic exclude-if-None) |

Weights are **hardcoded documented constants** in `fit.py` (no `fit_weight_*` flags).

### PipelineBoardItem
| Field | Type | Notes |
|---|---|---|
| `ticker` | str | |
| `entry_timing_state` | str \| None | from `compute_candidate_result`; None if unavailable |
| `sizing_preview` | `SizingResponse` \| None | inline size + binding constraint + heat-after |
| `fit` | `FitResult` \| None | None when the ticker was skipped |
| `sector` | str | for client-side sector-clustering |
| `skipped_reason` | str \| None | set (and other fields None) on per-ticker fail-soft |

### PipelineBoardResponse
| Field | Type | Notes |
|---|---|---|
| `items` | `list[PipelineBoardItem]` | one per requested ticker (order = fit-ranked or request order; client re-sorts by fit) |
| `regime` | object | reused regime payload |
| `regime_allows_new_entries` | bool | |
| `heat_ceiling_pct` | float | |
| `heat_headroom_pct` | float | |
| `available_cash` | Decimal \| None | echoed when provided |
| `personal_use_directive` | bool | whether directive labels are populated |
| `data_as_of` | str | envelope (Field default) |
| `disclaimer` | str | envelope (Field default) |

### PipelineBoardRequest
| Field | Type | Notes |
|---|---|---|
| `tickers` | list[str] | watched momentum tickers |
| `strategy_slug` | str = `"midterm_52w_high_momentum"` | **422 if any other slug** |
| `total_capital` | Decimal | derived total (cash + holdings MV) when cash set |
| `available_cash` | Decimal \| None | optional; threaded into each `size_position` |
| `caps` | `PortfolioCaps` | reused |

Holdings are **derived server-side** from persisted transactions via `_assemble_holdings`, not
sent in the request, so the board matches the portfolio page exactly.

---

## Extended entities (backend — `models/portfolio.py`, all additive/optional)

### SizingRequest / SizingResponse (US2 — available cash)
- `SizingRequest`: **+ `available_cash: Decimal | None = None`** (optional; absent ⇒ today's
  behavior).
- `SizingResponse.binding_constraint`: extend the documented vocabulary with **`"available_cash"`**
  (existing values: `risk_target | conviction | position_cap | sector_cap | portfolio_heat |
  conservative_fallback`). No field shape change — only a new possible value + logic that caps
  `suggested_shares` so `shares × entry ≤ available_cash`.

### PortfolioTotals / PortfolioHolding (US4 — P&L)
Existing (feature 013): `Holding.realized_pl`, `Holding.status ∈ {open,closed,anomalous}`,
`PortfolioHolding.unrealized_pl` / `unrealized_pl_pct`. 016 adds portfolio-level aggregates and
a realized round-trip history:
- `PortfolioTotals`: **+ optional** `realized_pnl: Decimal | None`, `unrealized_pnl: Decimal | None`,
  `total_pnl: Decimal | None`, `win_rate: float | None`, `closed_trade_count: int = 0`,
  `winning_trade_count: int = 0`. All None/0 when there are no closed lots ⇒ byte-identical.
- **New `RealizedTrade`** (returned in the holdings response or a dedicated P&L payload): one
  FIFO round-trip — `ticker`, `shares`, `buy_date`, `sell_date`, `proceeds`, `cost_basis`,
  `fees`, `realized_pnl`, `outcome: Literal["win","loss","flat"]`, `holding_days`.

### PortfolioHoldingsRequest (US2)
- **+ optional `available_cash: Decimal | None = None`** threaded into per-holding sizing so the
  portfolio page's recommended sizes also respect cash.

---

## Reused entities (no change)

- `Transaction`, `PortfolioTransactionsSlice`, `ImportRequest`, `ImportResult`, `RejectedRow` —
  manual entry reuses these verbatim (the import already validates + aggregates transactions).
- `SizingHolding`, `PortfolioCaps`, `PortfolioExposure`, `SectorExposure`, `ConcentrationFlag`,
  `HoldingLevels`, `LevelBlock`, `HoldingRisk` — consumed as-is by the board.

---

## New backend request contracts (manual transactions — reuse existing `Transaction` shape)

- `POST /portfolio/transactions` — body: one or more raw transaction rows (same shape the import
  validator already accepts: ticker, action ∈ {buy, sell}, quantity, price, trade_date, optional
  fees, note). Server validates + assigns the stable content-hash `id` + appends to the retained
  `transactions` list, then re-aggregates via `_assemble_holdings`. Response: reuses
  `ImportResult` (accepted/duplicate/rejected/transactions_total).
- `DELETE /portfolio/transactions/{id}` — remove one transaction by its stable `id` (correct a
  mistake); re-aggregate. Response: updated `ImportResult`-style summary.

---

## Frontend-owned state (persist v6 → v7)

`StoredState` in `frontend/src/lib/store.ts`:
- **+ `pipeline` key** — `Record<string, { manual_stage?: "staged" | "exited";
  acknowledged_ready_at?: string; ready_since?: string }>` keyed by `${strategy}-${ticker}`.
  Backend never parses it (opaque blob; synced via `PUT /portfolio/state`).
- **`Portfolio` + `available_cash?: number`** — the cash-first anchor. Migration seeds it from
  the dormant `cash_balance_override` if that was ever set, then retires the override.
- **Derived** (not stored): effective `total_capital` = `available_cash + Σ holding market value`
  when `available_cash` is set; otherwise today's manual `total_capital`.

Migration `6 → 7`: no-op default `pipeline = {}`; seed `available_cash` from any old override;
leave everything else untouched (round-trips through `exportSnapshot` / `normalizeStoredState` /
`PortfolioSync`).

### `derivePipelineStage` (pure selector, `lib/pipeline.ts`)
Precedence **holdings-derived > exited > ready > staged > watching**:
- `owned` / `managing` — from `/portfolio/holdings` (open holding ⇒ owned; escalates to
  managing when a `levels` block `status != "holding"` or `risk.over_risk`). Never manual.
- `ready` — board `entry_timing == entry_ready` and not held.
- `watching` — default for a saved watchlist entry.
- `staged` / `exited` — the only manual overrides (`manual_stage`).

---

## Flags (`backend/src/lib/flags.py`, Feature 016 section)

| Flag | Default | Effect |
|---|---|---|
| `pipeline_enabled()` | **OFF** | ON exposes `POST /pipeline/board`; OFF → 404 (home degrades to today's panels) |
| `fit_reward_to_risk_floor()` | `1.5` | threshold for the `reward_to_risk_ok` fact |
| `personal_use_directive()` | (existing) | reused; gates `directive_label` (also force-OFF hosted) |

No flag for available-cash sizing (optional request field ⇒ absent = byte-identical) and no
`fit_weight_*` flags (weights are documented constants).
