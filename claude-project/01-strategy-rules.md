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

- **Entry** = current close.
- **3-ATR disaster stop** = `entry − 3 × ATR` — the universal fallback whenever
  a preferred stop level is unavailable or sits at/above entry.
- **Trend stop (Faber, default)** = the 200-day SMA when it's below entry, else
  the 3-ATR stop.
- **Structure stop** = `20-day consolidation low − 0.25 × ATR`
  (`structure_stop_buffer_atr = 0.25`), i.e. "just below support." Usually
  tighter than the 200-SMA stop ⇒ better reward:risk. Falls back to 3-ATR if
  invalid.
- **Active stop** = trend stop by default (`stop_mode = "trend"`); switch to
  `"structure"` for the breakout-workflow style. Both are always shown; the
  structure stop is exposed as the "tighter alternative."
- **Take-profit** = `entry + 3.0 × (entry − stop_loss)`
  (`take_profit_r_multiple = 3.0`, range 1–10) — a 3R target.

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
| `take_profit_r_multiple` | 3.0 | 1–10 | Target as a multiple of risk |
| `min_volume_ratio` | 0.7 | 0–5 | Recent vs 50-day volume floor (0 disables) |
| `sector_strength_top_fraction` | 1.0 | 0–1 | Keep top fraction of sectors (1.0 = DISABLED) |
| `stop_mode` | "trend" | trend/structure | Which stop is primary |
| `structure_stop_buffer_atr` | 0.25 | 0–2 | ATRs below the 20-day low for the structure stop |
