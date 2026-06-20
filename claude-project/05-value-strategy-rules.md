# Strategy Rules — Mid-Term Value Composite

**Slug:** `midterm_value_composite`
**Name:** Mid-Term Value Composite
**Core citations:** Fama & French (1992), "The Cross-Section of Expected Stock
Returns"; Lakonishok, Shleifer & Vishny (1994), "Contrarian Investment,
Extrapolation, and Risk."
**Timeframe:** Mid-term — roughly 1 to 12 months.
**Holding period:** 60–180 days (min 60, max 180).
**Description:** Ranks liquid stocks by a multi-metric value composite
(book/market, earnings, cash-flow, sales **yields**), gated by a Piotroski
F-Score and ranked **within sector**.

> **Core idea (value / contrarian premium):** Cheap stocks — high
> fundamental-to-price yields — earn higher subsequent returns than expensive
> ("glamour") stocks, because the market over-extrapolates recent growth and
> systematically misprices out-of-favor names. This strategy buys cheapness,
> but only in firms whose financials are *improving* (so it isn't buying value
> traps), and it compares each name against its **sector peers** so structurally
> cheap sectors (financials, REITs) don't dominate spuriously.

## How "cheapness" is measured — yields, not ratios

Every value metric is a **yield** = `fundamental / market cap`, so **higher =
cheaper**. This is deliberate: a yield handles negative numerators correctly (a
loss-making firm gets a *negative* earnings yield and sorts as *least* cheap),
whereas price/earnings or price/book go haywire when the denominator is tiny or
negative and can flag a distressed name as "cheap." The four yields:

| Metric | Definition | Inverse of |
|---|---|---|
| `book_to_market` | common (book) equity / market cap | price/book |
| `earnings_yield` | TTM net income / market cap | P/E |
| `cashflow_yield` | TTM operating cash flow / market cap | price/cash-flow |
| `sales_yield` | TTM revenue / market cap | price/sales |

**The composite** is the **mean of the available metrics' cross-sectional
percentile ranks** (each rank in [0, 1], higher = cheaper). It ignores missing
members and reports how many it used (`value_metrics_count`, out of 4), so a
name is never voided by one absent ratio — but a composite built from 1/4 yields
is far less trustworthy than one from 4/4. **Check the count.**

## Universe-wide liquidity gate (applied BEFORE the strategy runs)

- **Average daily dollar volume ≥ $1M** (20-day), and **price ≥ $5**.
- User-configurable. Illiquid / sub-$5 names are removed first. (Same gate as
  every other strategy in this screener.)

## Gates, in the exact order the code applies them

The single HARD gate is the **value composite** — it always filters; it *is* the
strategy. The others are configurable and, in default "hard" gate mode, also
filter. (A `tiered` mode warns-and-ranks instead of excluding on the non-core
gates — assume **hard mode** unless told otherwise.)

1. **Value composite (HARD gate)** — a name with **no evaluable value yield**
   cannot be ranked for cheapness and is **dropped**. This is the only gate that
   can never be turned off. — *Fama & French (1992); Lakonishok, Shleifer &
   Vishny (1994).*
2. **Cheapness cut** — keep the **cheapest top fraction** of the composite
   (`composite_top_percentile = 0.5` ⇒ top half). Prefers a cached
   reference-universe threshold (stable across screen / analyze / detail), else
   this universe's own quantile. Set to 1.0 to disable the hard cut (ranking
   still orders by composite).
3. **Piotroski F-Score health gate** — keep only financially *improving* cheap
   firms: `f_score ≥ min_f_score = 6` (the lower bound of Piotroski's
   high-score band). A name with **no point-in-time financials cannot be scored
   and is EXCLUDED in hard mode** (recorded as skipped) — this is the canonical
   value-trap filter, so missing-data names are dropped, not passed through. —
   *Piotroski (2000).* (See [06-value-modifications-and-citations.md](06-value-modifications-and-citations.md)
   for the nine signals.)
4. **Leverage sanity (soft)** — `debt_to_equity ≤ max_debt_equity = 2.0`. This
   ceiling is **looser than momentum's** (1.5) because value names legitimately
   carry more leverage. **Fails open**: a name missing D/E passes through.
5. **Momentum floor — "not a falling knife" (OPTIONAL, OFF by default)** —
   `return_12_1 ≥ min_momentum_12_1`. **Disabled by default** (`-1.0` = pure
   value, no floor); when raised above `-1.0` (the variant uses **`-0.20`**) it
   drops names whose 12-1 momentum is below the floor, so the screen doesn't buy
   cheapness that is cheap *because the price is collapsing*. **Fails open**: a
   name with no momentum reading passes through (recorded as skipped). This is
   the **one A/B parameter** the value side of the four-variant side-by-side run
   toggles (feature 006). — *Asness, Frazzini & Pedersen (2013).* (See
   [06-value-modifications-and-citations.md](06-value-modifications-and-citations.md).)
6. **Score = value composite** (higher = cheaper = better). Survivors are
   ranked **within each sector** and capped at **5 names per sector**
   (`max_per_sector = 5`, `within_sector_ranking = True`) so financials/REITs
   compete with their own peers and no single sector dominates.

## Entry / Stop / Take-profit (per surviving candidate)

> **Feature 011 — bounded, volatility-aware levels** (the same shared derivation
> as momentum, `strategies/levels.py`): risk distance is clamped, the target is
> capped at a reward ceiling, and missing inputs yield `insufficient_data`
> instead of a degenerate number. Selection/gates/citations unchanged.

- **Entry** = current close.
- **Stop candidate** (unchanged technical levels):
  - **3-ATR disaster stop** = `entry − 3 × ATR` — universal fallback.
  - **Trend stop (default)** = the 200-day SMA when below entry, else the 3-ATR
    stop. **The 200-day SMA is the STOP only — NOT an entry filter.** Unlike
    momentum, value deliberately *enters weakness* (no `close > SMA-200` gate).
  - **Structure stop** = `20-day swing low − 0.25 × ATR`
    (`structure_stop_buffer_atr = 0.25`), the tighter alternative.
- **Risk distance is CLAMPED** to `[1.0, 4.0] × ATR` (+ a low-price floor so
  `stop_loss > 0`) — same as momentum.
- **Take-profit** = `entry + 4.0 × risk_distance` (`take_profit_r_multiple =
  4.0`) — a **4R** target, **more patient than momentum's 3R** (mean-reversion
  needs longer), then **capped at the reward ceiling** (`z·ATR·√horizon`,
  `reward_ceiling_z = 2.5`; fair-value cap OFF by default). `levels_state` =
  `ok` / `insufficient_data`; each candidate carries a neutral `rationale`.

**Fair value & position sizing** work identically to momentum — see
[01-strategy-rules.md](01-strategy-rules.md) ("Fair value" and "Position sizing").
The risk-per-trade backbone (`f = 1%` of capital to the stop, hard-bounded by the
10%/25% caps) is strategy-agnostic. Note: a fair-value conviction modulator is
**off by default** (`sizing_conviction_signal = none`) but is *more* defensible
for value than momentum — value names are cheap relative to fundamentals, so a
positive margin of safety would be a real signal — though it remains unadopted
pending a real-data A/B on the value screen.

## Regime favorability

| Market regime | This strategy |
|---|---|
| Trending up | **Neutral** |
| Range-bound | **Favorable** |
| Trending down | **Neutral** |

**Important contrast with momentum:** a downtrend is **Neutral, not
Unfavorable**, on purpose. The value/contrarian premium does part of its work
*entering weakness*; marking downtrends Unfavorable would make the regime
master-switch suppress exactly the contrarian entries the thesis targets. Value
is strongest in **range-bound** markets where mean-reversion dominates.

## Full parameter reference

| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `min_f_score` | 6 | 0–9 | Piotroski F-Score floor (value-trap gate) |
| `composite_top_percentile` | 0.5 | 0.05–1.0 | Keep cheapest top fraction (1.0 disables the hard cut) |
| `within_sector_ranking` | true | bool | Rank composite within sector (financials/REITs vs peers) |
| `max_per_sector` | 5 | — | Cap on candidates per sector |
| `max_debt_equity` | 2.0 | 0–5 | Leverage sanity ceiling (looser than momentum; missing D/E passes through) |
| `min_momentum_12_1` | -1.0 (off) | -1.0–1.0 | Optional 12-1 momentum floor ("not a falling knife"); `-1.0` disables it, variant uses `-0.20`; missing momentum passes through |
| `take_profit_r_multiple` | 4.0 | 1–10 | Target as a multiple of (clamped) risk (more patient than momentum) |
| `trend_sma_length` | 200 | 50–300 | SMA length for the trailing STOP only (not an entry gate) |
| `structure_stop_buffer_atr` | 0.25 | 0–2 | ATRs below the 20-day low for the structure stop |
| `risk_distance_atr_lo` / `_hi` | 1.0 / 4.0 | — | Risk-distance clamp in ATRs (011, shared) |
| `reward_ceiling_z` | 2.5 | 1.5–4.0 | Vol/horizon take-profit ceiling (011, shared) |
| `risk_per_trade_fraction` | 0.01 | 0.0025–0.02 | Capital fraction risked to the stop = sizing backbone (011, shared) |
| `sizing_conviction_signal` | none | none/fair_value/inverse_vol/strategy_rank | Conviction modulator on sizing; default none (011, shared) |

## How this differs from the momentum strategy (quick reference)

| | Momentum (`midterm_52w_high_momentum`) | Value (`midterm_value_composite`) |
|---|---|---|
| Thesis | buy strength near 52-week high | buy cheapness, contrarian |
| Core hard gate | within 5% of 52-week high | value composite (yields) |
| Trap filter | QMJ quality + gp/assets | Piotroski F-Score ≥ 6 |
| SMA-200 | **entry filter** + stop | **stop only** (enters weakness) |
| Leverage ceiling | D/E ≤ 1.5 | D/E ≤ 2.0 (looser) |
| Take-profit | 3R | 4R (more patient) |
| 12-1 momentum | **core hard gate** (must be strong) | **optional floor, OFF by default** (`min_momentum_12_1`, variant `-0.20`) |
| Downtrend regime | **Unfavorable** | **Neutral** |
| Sector handling | sector-relative rank, cap 5 | within-sector rank (default on), cap 5 |
