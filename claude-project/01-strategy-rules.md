# Strategy Rules — Mid-Term 52-Week High Momentum

**Slug:** `midterm_52w_high_momentum`
**Name:** Mid-Term 52-Week High Momentum
**Core citation:** George & Hwang (2004), "The 52-Week High and Momentum
Investing," *Journal of Finance* 59(5).
**Timeframe:** Mid-term — roughly 1 to 12 months.
**Holding period:** 60–180 days (min 60, max 180).
**Description:** Ranks liquid stocks near their 52-week high using momentum,
quality, and sector-concentration gates.

> **Core idea (George & Hwang 2004):** A stock's nearness to its own 52-week
> high is one of the strongest predictors of future intermediate-term returns —
> often stronger than raw past returns. The 52-week high acts as an anchor:
> investors underreact to good news that pushes a stock toward a new high, so
> the drift continues. This strategy buys that drift, then layers risk and
> quality controls on top.

## Universe-wide liquidity gate (applied BEFORE the strategy runs)

- **Average daily dollar volume ≥ $1M** (20-day), and **price ≥ $5**.
- User-configurable. Illiquid / sub-$5 names are removed first.

## Gates, in the exact order the code applies them

The single HARD gate is **proximity to the 52-week high** — it always filters;
it *is* the strategy. The others are configurable and, in the default "hard"
gate mode, also filter. (There is a `tiered` mode where the non-proximity gates
warn-and-rank instead of excluding — assume **hard mode** unless told otherwise.)

1. **Gross-profitability gate** *(cross-sectional, pre-computed over the whole
   screened universe)* — keep only the **top half** by gross profit / total
   assets (`min_gp_assets_percentile = 0.5`). Skipped if `gp_to_assets` is
   unavailable. — *Novy-Marx (2013).*
2. **Low asset-growth gate** *(cross-sectional)* — keep only the **bottom half**
   by year-over-year total-asset growth (`max_asset_growth_percentile = 0.5`).
   **Fails open**: a name missing point-in-time asset growth passes through.
   Set to 1.0 to disable. — *George, Hwang & Li (2018); Hou, Xue & Zhang (2015).*
3. **52-week-high proximity (HARD gate)** — keep names within **5%** of their
   52-week high: `dist_to_high = (52w_high − close) / close ≤ 0.05`
   (`proximity_pct = 0.05`, range 1%–20%). This is the only gate that can never
   be turned off. — *George & Hwang (2004).*
4. **Sector-strength gate** — keep names only in the strongest sectors by
   **breadth** (fraction of sector members above their 200-day SMA), top
   `sector_strength_top_fraction`. **DISABLED by default (= 1.0)** because the
   earlier median-distance metric collapsed the live screen; re-enable only with
   a proper industry-momentum metric. — *Moskowitz & Grinblatt (1999).*
5. **Volume confirmation** — recent (5-day average) volume must be ≥
   `min_volume_ratio = 0.7` × the 50-day average, i.e. participation isn't
   collapsing. **Fails open** when volume history is missing. Set 0 to disable.
6. **Trend confirmation** — `close > 200-day SMA` (`trend_sma_length = 200`,
   range 50–300). Skipped if `sma_200` is unavailable. — *Faber (2007).*
7. **Quality screen** — `debt_to_equity ≤ 1.5` (`max_debt_equity`, range 0–5)
   **AND** trailing-twelve-month free cash flow `fcf_ttm > 0`. Skipped per name
   when either input is missing. — *Asness, Frazzini & Pedersen (2019), QMJ.*
8. **Apply gross-profitability pass** (from step 1).
9. **Apply low-asset-growth pass** (from step 2).

## Scoring & ranking (survivors of the gates)

- **Volatility scalar** — exposure is scaled by trailing realized volatility
  toward an annualized **target of 12%** (`target_volatility = 0.12`, range
  5%–30%). — *Barroso & Santa-Clara (2015).*
- **Score** = `return_12_1 × vol_scalar / (1 + dist_to_high)` when the 12-1
  momentum return is available; otherwise `1 / (1 + dist_to_high)`.
  (Closer to the high and stronger 12-1 momentum ⇒ higher score.)
- **Sector-relative ranking** — rank within each sector and cap at
  **5 names per sector** (`max_per_sector = 5`) to control concentration.

## Entry / Stop / Take-profit (per surviving candidate)

> **Feature 011 — levels are now BOUNDED & volatility-aware.** The old unbounded
> `take_profit = entry + 3R·(entry − stop)` could blow a target absurdly far out
> when a stop sat far below price. Levels are now clamped and carry a neutral
> `rationale`, an `insufficient_data` fallback, and a `levels_state` flag. Both
> mid-term strategies share one derivation (`strategies/levels.py`). **Selection,
> gates, and citations are unchanged — this is presentation/risk only.**

- **Entry** = current close.
- **Stop candidate** = the same technical stop as before:
  - **3-ATR disaster stop** = `entry − 3 × ATR` — the universal fallback when a
    preferred level is unavailable or sits at/above entry.
  - **Trend stop (Faber, default `stop_mode = "trend"`)** = the 200-day SMA when
    below entry, else the 3-ATR stop.
  - **Structure stop** = `20-day consolidation low − 0.25 × ATR`
    (`structure_stop_buffer_atr = 0.25`), exposed as the "tighter alternative."
- **Risk distance is then CLAMPED** to `[1.0, 4.0] × ATR`
  (`risk_distance_atr_lo = 1.0`, `risk_distance_atr_hi = 4.0`) plus a low-price
  floor so `stop_loss > 0`. A far-below-trend SMA no longer produces a giant
  risk distance — it is capped at 4·ATR. (On real data the upper clamp is the
  binding constraint for most names.)
- **Take-profit** = `entry + 3.0 × risk_distance`
  (`take_profit_r_multiple = 3.0`, range 1–10), then **capped at a reward
  ceiling** = `min(` volatility/horizon limit `z·ATR·√horizon` with
  `reward_ceiling_z = 2.5`, a trusted fair value *(only if
  `reward_ceiling_use_fair_value` is on — default OFF)*, a measured-move limit
  `)`. In practice the 3R target governs and the ceiling rarely binds
  (`reward_ceiling_basis` records which limit applied).
- **`levels_state`** = `ok` when `0 < stop_loss < entry < take_profit` within
  bounds; **`insufficient_data`** (stop & target = null) when ATR / SMA-200 /
  swing-low are missing — never a degenerate number. Each candidate carries a
  zero-directive **`rationale`** naming the stop rule and the binding ceiling.

## Fair value (feature 011, displayed per candidate)

A free, point-in-time **intrinsic-value estimate**, default basis the **Graham
number** `sqrt(22.5 × EPS × BVPS)` (Graham, *The Intelligent Investor*, 1973 rev.,
ch. 14) with EPS/BVPS back-derived from the EDGAR earnings/book yields the value
strategy already computes (`fair_value_basis = "intrinsic_model"`; alternative
`"valuation_yields"` = book value per share). It carries a **trust flag**:
`trusted` / `unavailable` / `stale` / `out_of_range`, and a margin of safety vs
close. **Coverage on momentum candidates is ~60% trusted** — momentum leaders
near their highs are usually *expensive* vs Graham value (negative margin of
safety), so treat fair value as **context, not a target**. It is **not** used to
size momentum positions (see below) and is OFF as a take-profit ceiling.

## Position sizing (feature 011 — risk-per-trade backbone)

Sizing is no longer "fill the cap." It is **risk-per-trade**:
`shares ≈ (f × capital) / (entry − stop_loss)` with `risk_per_trade_fraction
f = 0.01` (risk 1% of capital to the stop), then **hard-bounded** by the
per-position (10%) and per-sector (25%) caps — a suggestion never breaches a cap.
A wider stop ⇒ a strictly smaller position. The result names its
**`binding_constraint`** (`risk_target` / `position_cap` / `sector_cap`).
A **conviction modulator** can scale this (`sizing_conviction_signal`), but the
shipped default is **`none`**: a fair-value/margin-of-safety modulator was tested
and rejected for momentum (it floored ~11 of 12 winners because they trade above
Graham value). Sizing fails open — a missing modulator input never errors.

## Regime favorability

| Market regime | This strategy |
|---|---|
| Trending up | **Favorable** |
| Range-bound | **Neutral** |
| Trending down | **Unfavorable** |

Momentum / 52-week-high strategies are known to suffer sharp "momentum crashes"
when a falling market snaps back violently (the rebound punishes recent winners
and rewards beaten-down losers) — the volatility scaling exists partly to blunt
this. Treat "Trending down" signals with heavy skepticism.

## Full parameter reference

| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `lookback_days` | 252 | — | Window for the 52-week high |
| `proximity_pct` | 0.05 | 0.01–0.20 | Max distance below the high |
| `max_per_sector` | 5 | — | Cap on candidates per sector |
| `max_debt_equity` | 1.5 | 0–5 | Leverage ceiling (quality) |
| `target_volatility` | 0.12 | 0.05–0.30 | Annualized vol target for scaling |
| `trend_sma_length` | 200 | 50–300 | Trend SMA for confirmation + exit |
| `min_gp_assets_percentile` | 0.5 | 0–0.95 | Keep top fraction by gp/assets |
| `max_asset_growth_percentile` | 0.5 | 0.05–1.0 | Keep bottom fraction by asset growth (1.0 disables) |
| `take_profit_r_multiple` | 3.0 | 1–10 | Target as a multiple of (clamped) risk |
| `min_volume_ratio` | 0.7 | 0–5 | Recent vs 50-day volume floor (0 disables) |
| `sector_strength_top_fraction` | 1.0 | 0–1 | Keep top fraction of sectors (1.0 = DISABLED) |
| `stop_mode` | "trend" | trend/structure | Which stop is primary |
| `structure_stop_buffer_atr` | 0.25 | 0–2 | ATRs below the 20-day low for the structure stop |
| `risk_distance_atr_lo` | 1.0 | 0.5–2.0 | Lower clamp on risk distance, in ATRs (011) |
| `risk_distance_atr_hi` | 4.0 | 2.0–6.0 | Upper clamp on risk distance, in ATRs (011) |
| `reward_ceiling_z` | 2.5 | 1.5–4.0 | Vol/horizon take-profit ceiling `z·ATR·√horizon` (011) |
| `reward_ceiling_use_fair_value` | false | bool | Also cap target at a trusted fair value (011) |
| `risk_per_trade_fraction` | 0.01 | 0.0025–0.02 | Capital fraction risked to the stop = sizing backbone (011) |
| `fair_value_basis` | intrinsic_model | intrinsic_model/valuation_yields | Fair-value model (Graham number vs book value/share) (011) |
| `sizing_conviction_signal` | none | none/fair_value/inverse_vol/strategy_rank | Conviction modulator on sizing; default none (011) |
