# Data Model: US Stock Screener MVP

**Feature**: 001-screener-mvp
**Date**: 2026-06-10

This file defines the entities the screener operates on. Every entity carries source-provenance fields (`source_name`, `source_as_of`) where it represents data fetched from an external source — per Constitution I.

The schemas below describe the *logical* shape of each entity and its validation rules. Concrete representations live in:
- `backend/src/models/` — Pydantic v2 schemas (API DTOs and internal models).
- SQLite tables in `backend/data/catalog.db` for catalog/reference data.
- Parquet files under `backend/data/prices/` for time-series data.
- Browser `localStorage` for the user-side `Portfolio`, `Watchlist`, and `UserSettings`.

---

## Conventions

- All monetary values are USD with explicit `Decimal` precision in code; cents to four decimal places (e.g., 12.3456).
- All timestamps are ISO 8601 UTC with `Z` suffix (e.g., `2026-06-09T20:00:00Z`).
- All as-of dates are end-of-trading-day in US/Eastern time, presented as a UTC timestamp at 21:00 UTC (4 PM ET market close).
- A `source_name` field is short and stable (e.g., `"sec_edgar"`, `"yfinance"`, `"spus_holdings"`, `"econ_calendar_v1"`).
- Identifiers: tickers are uppercase strings (e.g., `"AAPL"`). All entities with a ticker validate against the loaded universe at write time — unknown tickers are either rejected (for screen results) or accepted with `is_in_universe=false` (for portfolio holdings).

---

## Entity: Ticker

Catalog row for one US-listed common equity.

| Field | Type | Notes |
|---|---|---|
| `ticker` | string (PK) | Uppercase symbol, e.g., `"AAPL"`. |
| `name` | string | Issuer name. |
| `exchange` | enum | `NYSE`, `NASDAQ`, `NYSE_AMERICAN`. |
| `cik` | string | SEC Central Index Key, 10-digit zero-padded. Nullable for non-EDGAR-filed issuers (rare in our universe). |
| `sic_code` | string | 4-digit SIC code from EDGAR. Nullable. |
| `sector` | enum or `"Unclassified"` | Derived from `sic_code` via the SIC-to-sector mapping. |
| `industry` | string | Optional finer-grained label. |
| `listed_at` | date | First date the ticker is in our OHLCV history. |
| `delisted_at` | date | Nullable; populated when the ticker delists. |
| `source_name` | string | E.g., `"sec_edgar_company_tickers"`. |
| `source_as_of` | timestamp | When the catalog row was last refreshed. |

**Validation**: `ticker` matches `^[A-Z][A-Z0-9.-]{0,9}$`. Either `delisted_at IS NULL` (active) or `>= listed_at` (delisted).

**Survivorship**: Delisted tickers are kept (Constitution I).

---

## Entity: OHLCV Bar

End-of-day price bar for one ticker on one trading date.

| Field | Type | Notes |
|---|---|---|
| `ticker` | string | Foreign key to `Ticker`. |
| `as_of_date` | date | Trading date (US/Eastern). |
| `open` | Decimal | Unadjusted open. |
| `high` | Decimal | Unadjusted high. |
| `low` | Decimal | Unadjusted low. |
| `close` | Decimal | Unadjusted close. |
| `adj_close` | Decimal | Split- and dividend-adjusted close. |
| `volume` | int | Share volume. |
| `source_name` | string | E.g., `"yfinance"`. |
| `source_as_of` | timestamp | Fetch time. |

**Primary key**: `(ticker, as_of_date)`. Stored as Parquet partitioned by `year(as_of_date)`.

**Point-in-time discipline**: Adjusted closes are recomputed only forward from the as-of date — historical adjusted closes are never restated retroactively. The unadjusted columns are the authoritative point-in-time view; adjusted is a convenience.

---

## Entity: Indicator Series

Derived per-ticker daily series for any computed indicator (RSI, SMA, EMA, ATR, MACD, etc.).

Indicators are computed on demand from `OHLCV Bar` data by pure functions in `backend/src/indicators/`. They are not persisted in the v1 design — the screening engine computes them in-memory per run. (Caching is a v1.x optimization if the perf budget tightens.)

Each indicator's signature is documented in its module and is fixture-tested per Constitution IV.

---

## Entity: Fundamentals Snapshot

One quarterly or annual fundamentals snapshot per ticker, derived from EDGAR XBRL.

| Field | Type | Notes |
|---|---|---|
| `ticker` | string | FK to `Ticker`. |
| `period_end` | date | Fiscal period end. |
| `filing_date` | date | When the filing was received by EDGAR (point-in-time discipline). |
| `form_type` | enum | `10-Q`, `10-K`. |
| `revenue` | Decimal | TTM and quarterly variants computed downstream. |
| `eps_basic` | Decimal | Basic EPS for the period. |
| `eps_diluted` | Decimal | Diluted EPS. |
| `net_income` | Decimal | Net income for the period. |
| `total_assets` | Decimal | Balance-sheet snapshot. |
| `total_liabilities` | Decimal | Balance-sheet snapshot. |
| `shares_outstanding` | Decimal | As of period end. |
| `accession_number` | string | EDGAR filing accession number — links back to the source. |
| `source_name` | string | `"sec_edgar"`. |
| `source_as_of` | timestamp | When the row was ingested. |

**Primary key**: `(ticker, period_end, form_type)`.

---

## Entity: Strategy

Static metadata + rule definition for one screening strategy. Defined in code, registered at module import.

| Field | Type | Notes |
|---|---|---|
| `slug` | string (PK) | Module-name slug, e.g., `"midterm_52w_high_momentum"`. |
| `name` | string | Display name. |
| `timeframe` | enum | `Short-term` or `Mid-term`. |
| `citation` | string | URL or full bibliographic reference. |
| `description` | string | Plain-language rule summary for the UI. |
| `holding_period_days` | object | `{min: int, max: int}` — expected holding window. |
| `parameters` | object | `{ name: { default, min, max, type, description } }` per parameter. |
| `regime_favorability` | object | `{ "Trending up": "Favorable" | "Neutral" | "Unfavorable", "Range-bound": ..., "Trending down": ... }` |
| `default_exclude_earnings_within_days` | int | E.g., 7 for short-term, 0 for mid-term. |
| `enabled_by_default` | bool | Whether the strategy is on at v1 launch. |
| `modifications` | array<object> | Each modification to the cited core methodology, with `name`, `description`, and its own `citation`. E.g., `[{name: "Volatility scaling", citation: "Barroso & Santa-Clara (2015)"}]`. Powers the user-facing "Strategy gates" panel (FR-037). |
| `backtest_summary` | object | Headline metrics for the strategy's most recent walk-forward backtest: `data_window_start`, `data_window_end`, `total_return`, `max_drawdown`, `hit_rate`, `avg_win`, `avg_loss`, `turnover`, `source_name`, `source_as_of`. |

**Validation**: Every strategy MUST declare a `citation` and a `rules` callable; the registry refuses to load a strategy missing either (Constitution II). A strategy with `enabled_by_default=true` MUST have a `backtest_summary` whose `data_window_end - data_window_start ≥ 15 years` AND whose window spans 2008-2009 (research.md Decision 15). Strategies failing this check fall back to `enabled_by_default=false` and ship with a "Limited backtest window" warning surfaced on their detail page.

---

## Entity: Screen Result

Snapshot of one strategy's run against one data as-of date.

| Field | Type | Notes |
|---|---|---|
| `id` | string | Hash of `(strategy_slug, as_of_date, parameters_snapshot, filters_snapshot)`. Deterministic. |
| `strategy_slug` | string | FK to `Strategy`. |
| `as_of_date` | date | Data snapshot the screen ran against. |
| `parameters_snapshot` | object | Frozen parameter values used. |
| `filters_snapshot` | object | `{ shariah_only: bool, exclude_earnings_within_days: int }`. |
| `candidate_count` | int | |
| `candidates` | array<Candidate> | Ranked list. |
| `computed_at` | timestamp | Server-side computation time. |
| `disclaimer` | string | Constant text; included in every API response per Constitution V. |

**Determinism**: Same `(strategy_slug, as_of_date, parameters_snapshot, filters_snapshot)` MUST produce the same `id` and the same `candidates` list (FR-018, SC-008).

---

## Entity: Candidate

One ticker matched by one strategy on one as-of date.

| Field | Type | Notes |
|---|---|---|
| `ticker` | string | FK to `Ticker`. |
| `name` | string | Display copy of issuer name. |
| `sector` | string | Derived. |
| `current_price` | Decimal | Last close as of `as_of_date`. |
| `entry` | Decimal | Suggested entry per strategy rule. |
| `stop_loss` | Decimal | Suggested stop per strategy rule. |
| `take_profit` | Decimal | Suggested first target per strategy rule. |
| `rank` | int | 1-indexed rank within this `ScreenResult`. |
| `score` | float | Strategy's ranking score. |
| `reason` | string | One-line "why it matched". |
| `shariah_compliant` | bool | NULL if `filters_snapshot.shariah_only` is False; otherwise true (excluded otherwise). |
| `shariah_source_as_of` | timestamp | Nullable; mirrors the Shariah source's as-of. |
| `next_earnings_date` | date | Nullable. |
| `days_to_earnings` | int | Nullable; derived. |
| `recent_8k_count_30d` | int | Trailing 30 days of 8-K filings. |
| `events_source_as_of` | timestamp | When the events data backing the badges was refreshed. |

**Validation**:
- `0 < stop_loss < entry <= take_profit`. (Long-only in v1; short setups would invert and are out of scope.)
- `entry`, `stop_loss`, `take_profit` are rounded to the nearest cent.
- If `filters_snapshot.exclude_earnings_within_days > 0` and `days_to_earnings` is known and within the window, the candidate MUST NOT appear in this `ScreenResult`.

---

## Entity: Portfolio (client-side only)

Stored in browser `localStorage`. Schema versioned for forward migration.

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | E.g., `1`. |
| `total_capital` | Decimal | User-entered total capital (USD). |
| `holdings` | array<Holding> | |
| `cash_balance_override` | Decimal | Optional; derived if omitted as `total_capital - sum(holdings.market_value)`. |
| `created_at` | timestamp | First save. |
| `updated_at` | timestamp | Last edit. |

**Derived (computed on render, never stored)**:
- `total_invested` = sum of `holdings[i].shares * latest_price[i]`.
- `cash_balance` = `cash_balance_override ?? (total_capital - total_invested)`.
- `sector_exposure[sector]` = sum of holdings in that sector / `total_capital`.
- `concentration_flags` = list of `{ position | sector } > cap`.

---

## Entity: Holding (client-side)

| Field | Type | Notes |
|---|---|---|
| `ticker` | string | |
| `shares` | int or Decimal | Fractional shares allowed for portfolio entry but not for sizing suggestions (whole-share output only per FR-012). |
| `avg_cost` | Decimal | Per-share average cost basis. |
| `added_at` | timestamp | |
| `note` | string | Optional user note. |

**Derived**: `market_value`, `cost_basis_total`, `unrealized_gain`, `sector`, `is_in_universe`, `shariah_compliant` (when filter ON).

---

## Entity: Watchlist Entry (client-side)

| Field | Type | Notes |
|---|---|---|
| `id` | string | UUIDv4. |
| `ticker` | string | |
| `strategy_slug` | string | Which strategy produced the candidate. |
| `saved_at` | timestamp | |
| `state` | enum | `saved`, `dismissed`, `acted_on`. |
| `levels_snapshot` | object | `{ entry, stop_loss, take_profit }` captured at save time. |
| `note` | string | Optional. |

---

## Entity: User Settings (client-side)

| Field | Type | Default | Notes |
|---|---|---|---|
| `per_position_cap_pct` | float | `0.10` | 10% of total capital. |
| `per_sector_cap_pct` | float | `0.25` | 25% of total capital. |
| `shariah_filter_on` | bool | `false` | Per spec assumption. |
| `shariah_external_sources` | array<string> | `["spus_holdings"]` | Ordered list of active external Shariah sources. Default SPUS only; user can add HLAL or others without code changes. |
| `shariah_user_inclusion` | array<UserShariahOverride> | `[]` | User-curated compliant tickers extending external sources (FR-038). |
| `shariah_user_exclusion` | array<UserShariahOverride> | `[]` | User-curated non-compliant overrides (FR-039). |
| `default_strategy_slug` | string | `"midterm_52w_high_momentum"` | |
| `exclude_earnings_within_days_overrides` | object | `{}` | Per-strategy overrides; falls back to strategy's `default_exclude_earnings_within_days`. |
| `liquidity_min_avg_dollar_volume_20d` | int | `1_000_000` | Trailing-20-day ADV threshold for the universe-wide liquidity gate (FR-034, research.md Decision 14). |
| `liquidity_min_price` | Decimal | `5.00` | Share-price floor for the universe-wide liquidity gate. |

---

## Entity: Backtest Run (server-side)

One walk-forward backtest run, computed offline and read at runtime to populate the strategy detail page.

| Field | Type | Notes |
|---|---|---|
| `id` | string (PK) | Stable hash of `(strategy_slug, data_snapshot_id, code_version)`. |
| `strategy_slug` | string | FK to `Strategy`. |
| `data_window_start` | date | First trading day in the backtest. |
| `data_window_end` | date | Last trading day. |
| `data_sources` | array<object> | Each: `{source_name, source_as_of}` (e.g., `stooq`, `sec_edgar`). |
| `bias_check` | object | Each item in the bias-check checklist with `passed: bool` and `note: string`. Constitution III gate. |
| `yearly_metrics` | array<object> | Per calendar year: `{year, trades, hit_rate, avg_win, avg_loss, total_return, max_drawdown}`. Powers the user-facing walk-forward table (FR-035). |
| `summary_metrics` | object | Aggregates across the full window: `{total_return, max_drawdown, hit_rate, avg_win, avg_loss, turnover}`. |
| `code_version` | string | Git SHA or release tag of the backtest runner. |
| `computed_at` | timestamp | When the backtest was last run. |

**Validation**:
- `data_window_end >= data_window_start + 15 years` AND the window contains 2008-2009 → required for `Strategy.enabled_by_default=true`.
- Every item in `bias_check` is true → required for the strategy to ship at all.
- Deterministic on a fixed `data_snapshot_id` (Constitution III).

---

## Entity: Market Regime

Computed daily from SPY + S&P 500 breadth.

| Field | Type | Notes |
|---|---|---|
| `as_of_date` | date | |
| `regime` | enum | `Trending up`, `Range-bound`, `Trending down`. |
| `rule_summary` | string | Plain-language description of the rule that produced this regime. |
| `inputs` | object | `{ spy_close, spy_sma200, breadth_pct_above_sma200 }` — frozen for audit. |
| `source_name` | string | E.g., `"spy_breadth_regime_v1"`. |
| `source_as_of` | timestamp | When inputs were fetched. |

---

## Entity: Shariah Source Row (external)

One ticker in a configured *external* Shariah source's universe (e.g., SPUS holdings).

| Field | Type | Notes |
|---|---|---|
| `ticker` | string | |
| `source_name` | string | E.g., `"spus_holdings"`, `"hlal_holdings"`. |
| `source_kind` | enum | Always `external` for this entity (distinguishes from user overrides below). |
| `source_as_of` | timestamp | When the external list was last refreshed. |
| `source_url` | string | URL of the holdings page / PDF / JSON, for audit. |

---

## Entity: User Shariah Override (client-side, browser `localStorage`)

A per-ticker override the user maintains themselves. Two directions, stored in two parallel lists.

| Field | Type | Notes |
|---|---|---|
| `ticker` | string | |
| `direction` | enum | `include` (user-marked compliant, extends external source) or `exclude` (user-marked non-compliant, overrides external inclusion). |
| `added_at` | timestamp | When the user added this override. |
| `note` | string | Optional free-text rationale (e.g., a URL to a Shariah-board review the user trusts, or a brief reason). |

**Persistence**: lives in browser `localStorage` alongside `Portfolio`, `Watchlist`, and `UserSettings`. Sent server-side as part of every screen-run / candidate / sizing request that needs Shariah evaluation. Included in the export/import bundle (FR-019, FR-041).

**Composite lookup** — the v1 effective compliance verdict for a ticker, when the Shariah filter is ON:

```
is_shariah_compliant(ticker) ⇔
    (ticker ∈ active_external_sources  OR  ticker ∈ user_inclusion_list)
    AND
    (ticker ∉ user_exclusion_list)
```

Per FR-040 / research.md Decision 9. Defense-in-depth: the screening engine asserts the verdict on every returned candidate.

**Effective source kind** for the badge:
- If the ticker is in `user_exclusion_list` → `Excluded by user` (no compliant badge).
- Else if in any active external source → external source name (e.g., `SPUS`) wins; the user's `note` is preserved for the case where the user later removes the external source.
- Else if in `user_inclusion_list` only → `User` with the user's `note` shown on hover.
- Else (when filter is ON and ticker is not in any list) → ticker is excluded from the result.

**Stale-source semantics**: when any active external source has not refreshed within its documented refresh interval, the lookup still uses the last-known external list and the response carries `is_stale=true`. User overrides are never stale (they're entirely user-maintained).

---

## Entity: Ticker Event

Per-ticker event record (earnings or 8-K material news).

| Field | Type | Notes |
|---|---|---|
| `ticker` | string | |
| `event_type` | enum | `earnings_scheduled`, `8K_filed`. |
| `event_date` | date | Scheduled date (for earnings) or filed date (for 8-K). |
| `event_time` | time | Nullable; available for earnings (BMO/AMC) when source provides. |
| `source_name` | string | `"yfinance_earnings_v1"` or `"sec_edgar_8k"`. |
| `source_as_of` | timestamp | |
| `source_url` | string | Link to EDGAR filing or calendar entry. |
| `metadata` | object | Free-form per-source extras (e.g., 8-K item numbers). |

---

## Entity: Market Event

Per-week US macroeconomic release record.

| Field | Type | Notes |
|---|---|---|
| `event_id` | string | Stable slug, e.g., `"fomc_20260618"`. |
| `event_type` | enum | `FOMC`, `CPI`, `NFP`, `PCE`, `PPI` (extensible). |
| `scheduled_at` | timestamp | UTC, with time-of-day if known. |
| `expected_value` | string | Consensus, e.g., `"0.25% hike"`, `"+200K"`. Nullable. |
| `actual_value` | string | Post-release. Nullable. |
| `status` | enum | `upcoming`, `released`, `cancelled`. |
| `source_name` | string | `"econ_calendar_v1"`. |
| `source_as_of` | timestamp | |
| `source_url` | string | Federal Reserve / BLS / BEA page. |

---

## Entity: Events Source

A configurable provider record.

| Field | Type | Notes |
|---|---|---|
| `source_id` | string (PK) | E.g., `"sec_edgar_8k"`, `"yfinance_earnings_v1"`, `"econ_calendar_v1"`. |
| `display_name` | string | UI label. |
| `kind` | enum | `ticker_events`, `market_events`. |
| `refresh_interval_days` | int | E.g., 1 for daily, 7 for weekly. |
| `last_refreshed_at` | timestamp | |
| `is_stale` | bool | Derived: `now - last_refreshed_at > refresh_interval_days`. |

---

## Relationships (summary)

```text
Ticker 1—* OHLCV Bar
Ticker 1—* Fundamentals Snapshot
Ticker 1—* Ticker Event
Ticker 0—1 Shariah Source Row  (per active source)

Strategy 1—* Screen Result
Screen Result 1—* Candidate
Candidate *—1 Ticker

Portfolio 1—* Holding
Holding *—1 Ticker

Watchlist Entry *—1 Candidate (by ticker + strategy)
User Settings 0..1 per browser
Market Regime 1 per as_of_date
Market Event * per week
```

---

## State Transitions

- **Watchlist Entry**: `saved → dismissed`, `saved → acted_on`, `acted_on → dismissed` (e.g., user changed their mind after the fact). All transitions are user-initiated; the system never auto-transitions. State + timestamps preserved for audit.
- **Market Event**: `upcoming → released` (when the actual value is populated by the daily ingest) or `upcoming → cancelled` (rare; manual operator override).
- **Ticker**: `active → delisted` when `delisted_at` is set by the daily ingest discovering a missing CIK in the EDGAR submissions feed for N consecutive days.
- **Shariah Source Row**: A ticker can leave the SPUS holdings list silently across refreshes. The Portfolio view surfaces `compliance_changed` flag when a holding was compliant at `holding.added_at` but is no longer compliant per the current `source_as_of`.

---

## Validation Rules (cross-entity, beyond field-level)

- A `Candidate` whose `ticker` is not in the active `Ticker` catalog MUST NOT be returned by the screening engine (the engine pre-filters).
- A `ScreenResult` with `filters_snapshot.shariah_only = true` MUST contain only candidates whose tickers appear in the active Shariah source — verified by a post-filter assert in the engine (defense in depth for SC-011).
- A position-sizing suggestion MUST never push `position_value / total_capital` above `per_position_cap_pct` or `sector_value / total_capital` above `per_sector_cap_pct` for the resulting hypothetical portfolio (FR-012, SC-007).
- The universe-wide liquidity gate (research.md Decision 14, FR-034) MUST be applied by the universe loader before any strategy sees the data: every `Candidate` returned by the screening engine MUST come from a ticker with trailing-20-day average daily dollar volume ≥ `UserSettings.liquidity_min_avg_dollar_volume_20d` AND price ≥ `UserSettings.liquidity_min_price`. Defense-in-depth: the screening engine asserts this post-hoc on every result.
- A `Holding` whose ticker fails the liquidity gate remains in the user's `Portfolio` for sector exposure and concentration purposes, but is tagged `excluded_by_liquidity_gate=true` so the UI can explain why no screen will surface it as a candidate.
- `current_price`, `entry`, `stop_loss`, `take_profit` in a `Candidate` MUST all derive from the same `as_of_date` — no mixed-date arithmetic.
