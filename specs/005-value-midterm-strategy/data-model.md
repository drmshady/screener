# Phase 1 Data Model: Value-Based Mid-Term Strategy

Entities below extend the existing 001 schemas (`backend/src/models/strategy.py`)
and the universe-snapshot DataFrame produced by `screening/engine.py`. New fields
are **additive and optional** so existing strategies, contracts, and tests are
unaffected.

---

## 1. Strategy declaration — `midterm_value_composite`

Same shape every strategy declares (registry-enforced). Concrete values:

| Field | Value |
|------|-------|
| `slug` | `midterm_value_composite` |
| `name` | `Mid-Term Value Composite` |
| `citation` | `Fama & French (1992); Lakonishok, Shleifer & Vishny (1994)` |
| `timeframe` | `Mid-term` |
| `description` | Ranks liquid stocks by a multi-metric value composite, gated by Piotroski financial health, ranked within sector. |
| `holding_period_days` | `{ min: 60, max: 180 }` |
| `regime_favorability` | `{ Trending up: Neutral, Range-bound: Favorable, Trending down: Neutral }` |
| `default_exclude_earnings_within_days` | `0` |
| `enabled_by_default` | `False` until bias-check passes / operator override (mirrors momentum) |
| `modifications` | see below (each carries its own citation) |

### Parameters (each with default + documented range)

| Param | Default | Range | Purpose |
|------|---------|-------|---------|
| `min_f_score` | 6 | 0–9 | Piotroski floor (value-trap gate) |
| `composite_top_percentile` | 0.5 | 0.05–1.0 | Keep names in the cheapest top fraction of the composite (1.0 disables the hard cut; ranking still orders by composite) |
| `max_per_sector` | 5 | int | Sector concentration cap (reuses `rank_within_sector`) |
| `within_sector_ranking` | `true` | bool | Rank the composite within sector (FR-014 distorted-sector handling) |
| `max_debt_equity` | 2.0 | 0–5 | Secondary leverage sanity ceiling (looser than momentum; value names can be levered) |
| `take_profit_r_multiple` | 4.0 | 1–10 | Patient profit target (Decision 7) |
| `trend_sma_length` | 200 | 50–300 | SMA for the trailing-stop level only (NOT an entry gate — value enters weakness) |
| `structure_stop_buffer_atr` | 0.25 | 0–2 | ATR buffer below the 20-day low for the tighter structure stop |

### Modifications (cited)

- **Value composite** — equal-weight percentile-rank blend of book/market,
  earnings, cash-flow and sales yields. *Fama & French (1992); Lakonishok,
  Shleifer & Vishny (1994).*
- **Piotroski F-Score health gate** — keep financially improving cheap firms.
  *Piotroski (2000), Value Investing: The Use of Historical Financial Statement
  Information.*
- **Within-sector ranking** — compare the composite among sector peers so
  financials/REITs are not spuriously ranked. *Standard sector-relative value
  control; cf. Asness, Frazzini & Pedersen (2013), Value and Momentum Everywhere.*
- **Sector concentration cap** — at most N names per sector. *Documented
  risk-control overlay.*

---

## 2. Valuation inputs (per company, point-in-time)

Produced by `FundamentalsLoader.value_metrics_as_of`; threaded into the snapshot
DataFrame as new columns. Each is a plain `float | None`; `None` = unavailable on
or before the as-of date (never fabricated).

| Snapshot column | Source concept(s) | Notes |
|-----------------|-------------------|-------|
| `market_cap` | `close` × `shares_outstanding` | `shares_outstanding` point-in-time from EDGAR |
| `book_to_market` | `StockholdersEquity` / `market_cap` | negative equity → negative B/M (sorts as least cheap) |
| `earnings_yield` | TTM `NetIncomeLoss` / `market_cap` | negative earnings → negative yield |
| `cashflow_yield` | TTM operating CF / `market_cap` | |
| `sales_yield` | TTM `Revenues` / `market_cap` | |
| `value_composite` | mean of available yield percentile-ranks | recorded with `value_metrics_count` |
| `value_metrics_count` | int 0–4 | how many yields were evaluable (honesty) |

Validation rules: `market_cap > 0` required (else all yields skipped);
percentile ranks computed cross-sectionally over the reference/contemporaneous
universe (Decision 3); a name with `value_metrics_count == 0` is excluded with a
recorded reason.

---

## 3. Piotroski F-Score signals (per company, point-in-time)

Produced by `indicators/piotroski.py` from current- and prior-year fundamentals.

| Signal | Definition | Inputs |
|--------|-----------|--------|
| `roa_positive` | ROA = NI / total assets > 0 | NetIncomeLoss, Assets |
| `cfo_positive` | operating CF > 0 | NetCashProvidedByUsedInOperatingActivities |
| `roa_improved` | ΔROA > 0 | NI & Assets, two years |
| `accruals_ok` | operating CF > NI | CFO, NI |
| `leverage_down` | Δ(long-term debt / assets) < 0 | LongTermDebt, Assets, two years |
| `current_ratio_up` | Δ(current assets / current liabilities) > 0 | AssetsCurrent, LiabilitiesCurrent, two years |
| `no_dilution` | Δ shares outstanding ≤ 0 | shares, two years |
| `gross_margin_up` | Δ(gross profit / revenue) > 0 | GrossProfit, Revenues, two years |
| `asset_turnover_up` | Δ(revenue / assets) > 0 | Revenues, Assets, two years |
| `f_score` | sum of the nine (0–9) | — |
| `f_score_evaluable` | count of signals with non-missing inputs (0–9) | — |

Missing-input rule: an unevaluable signal scores 0 and decrements
`f_score_evaluable`; the gate reports *skipped/partial* (not a false pass) when
`f_score_evaluable` is low (Decision 2).

---

## 4. Candidate result (additive fields on `Candidate` / `AnalyzeResponse`)

Existing fields unchanged. New optional fields (default `None`) so the advisor
prompt and UI can surface value diagnostics, mirroring the momentum diagnostics:

| New field | Type | Meaning |
|-----------|------|---------|
| `value_composite` | `float?` | composite cheapness score (higher = cheaper) |
| `book_to_market` | `float?` | |
| `earnings_yield` | `float?` | |
| `cashflow_yield` | `float?` | |
| `sales_yield` | `float?` | |
| `f_score` | `int?` | 0–9 |
| `f_score_evaluable` | `int?` | 0–9 |

`gate_results` (existing `List[GateResult]`) carries the per-name value gates:
`Value composite`, `Piotroski F-Score`, `Leverage sanity`, `Sector concentration`
— each `pass | fail | skipped` with a human detail, exactly like momentum.

---

## 5. Backtest artifact — `midterm_value_composite.json`

Same schema the runner already writes (`BacktestSummary` + `bias_check` +
`yearly_metrics` + `coverage_notes` + `equity_curve`). Value-specific expectations:

- `data_window_start ≤ 2008-01-01`, `data_window_end ≥ 2023-01-01` (registry floor).
- `bias_check.survivorship_bias.passed = false` on the free Stooq archive
  (surfaced, not hidden).
- `coverage_notes` includes the pre-2011 XBRL sparsity note for empty early years.
- `data_sources` includes `sec_edgar_companyfacts`.

---

## Relationships

```
Strategy(midterm_value_composite)
  ├─ rules(universe_df) ──reads──> snapshot columns (valuation inputs §2 + F-Score §3)
  │     └─ emits ──> Candidate (levels + gate_results + value fields §4)
  ├─ backtest_summary ──loads──> BacktestSummary  (from artifact §5)
  └─ registered in registry  (load-time field enforcement)

FundamentalsLoader.value_metrics_as_of ──fills──> §2/§3 inputs (point-in-time, EDGAR)
reference_thresholds (cached) ──grades──> value_composite percentile (§2)
agent/advisor_prompt ──reads──> Strategy + Candidate(§4) + artifact(§5)  (FR-016)
```
