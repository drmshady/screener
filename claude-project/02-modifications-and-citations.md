# Modifications & Citations

The base strategy is George & Hwang (2004). Everything below is a deliberate
**modification** layered on top, each with its own published source. When you
explain *why* a gate exists, cite the matching source here. Do not attribute
findings to a paper beyond what is summarized; if you're unsure, say so.

## Base method

**George, T. J., & Hwang, C.-Y. (2004). "The 52-Week High and Momentum
Investing." *Journal of Finance*, 59(5), 2145–2176.**
A stock's proximity to its 52-week high predicts future intermediate-term
returns and largely subsumes the Jegadeesh-Titman price-momentum effect.
Interpretation: the 52-week high is a psychological anchor; traders underreact
to news that pushes price toward/through it, producing continued drift. The
strategy goes long names nearest their 52-week high.

## Modification 1 — Volatility scaling

**Barroso, P., & Santa-Clara, P. (2015). "Momentum has its moments." *Journal
of Financial Economics*, 116(1), 111–120.**
Momentum returns have time-varying risk and occasionally crash hard. Scaling
exposure by recent realized volatility (targeting a constant volatility, here
12% annualized) dramatically improves momentum's risk-adjusted return and tames
its worst drawdowns. → Drives the `vol_scalar` in the score and the
`target_volatility` parameter.

## Modification 2 — Sector-relative ranking

**Documented risk-control overlay (practitioner convention; not a single
paper).** Rank candidates within their sector and cap the count per sector
(`max_per_sector = 5`) so the screen can't pile into one hot sector. This is a
concentration control, not an alpha claim — describe it that way.

## Modification 3 — Quality screen

**Asness, C. S., Frazzini, A., & Pedersen, L. H. (2019). "Quality Minus Junk."
*Review of Accounting Studies*, 24(1), 34–112.**
High-quality firms (profitable, growing, safe, well-managed) earn higher
risk-adjusted returns; "junk" underperforms. Here, distilled to two cheap,
robust proxies: leverage ceiling (`debt_to_equity ≤ 1.5`) and positive trailing
free cash flow (`fcf_ttm > 0`). This screens out fragile names riding momentum.

## Modification 4 — Gross-profitability gate

**Novy-Marx, R. (2013). "The Other Side of Value: The Gross Profitability
Premium." *Journal of Financial Economics*, 108(1), 1–28.**
Gross profits / total assets is a powerful, clean profitability signal — "the
other side of value." Keeping the top half of the universe by gp/assets tilts
toward genuinely productive firms and complements the quality screen.

## Modification 5 — Low asset-growth gate

**George, D. T., Hwang, C.-Y., & Li, Y. (2018). "The 52-Week High, q-Theory,
and the Cross-Section of Stock Returns." *Journal of Financial Economics*.**
**+ Hou, K., Xue, C., & Zhang, L. (2015). "Digesting Anomalies: An Investment
Approach." *Review of Financial Studies*, 28(3), 650–705.**
Under q-theory, firms that invest heavily (high asset growth) subsequently earn
lower returns. The 52-week-high premium concentrates in high-momentum, **low**
asset-growth firms. So keep the bottom half by year-over-year asset growth.
**Fails open** where point-in-time asset growth is unavailable (sparse on the
free data tier).

## Modification 6 — Trend confirmation & exit

**Faber, M. T. (2007). "A Quantitative Approach to Tactical Asset Allocation."
*Journal of Wealth Management*, 9(4).**
A simple long-term moving-average rule (price vs its ~10-month / 200-day SMA)
keeps you in uptrends and out of downtrends, sharply reducing drawdowns. Used
here both as an entry filter (`close > 200-day SMA`) and as the default
trailing stop.

## Modification 7 — Volume confirmation

**Standard liquidity / participation check (no specific 52-week-high paper
prescribes a volume rule — say so honestly).** Recent 5-day average volume must
hold ≥ 0.7× the 50-day average, so nearness-to-high isn't happening on
collapsing participation. Deliberately a *smoothed* recent-window measure, not a
single-day spike, because the 52-week-high anchoring effect actually favors
quiet underreaction drift — this only screens out clearly fading names.

> **Reconcile with Modification 9's volume component (deliberate, not a bug).**
> This gate (≥ 0.7× *participation*, smoothed) and the entry-timing
> `volume_confirmation` component (≥ 1.4× *breakout* surge) measure different
> things for different reasons. The gate encodes the **base thesis** — George &
> Hwang drift is *supposed* to be quiet, so a low-volume name is a valid screen
> match. The entry-timing component encodes a **Minervini breakout** view, where
> a pivot break wants a volume surge. A clean drift name will therefore pass the
> gate yet read `not-entry-ready` ("weak-volume breakout") in the overlay — that
> is **correct and expected**, not a contradiction. Treat the overlay's volume
> flag on such a name as *timing texture*, never as a reason to fail it: the
> entry-timing state is a tie-breaker/risk-veto, not a gate (see
> [00-custom-instructions.md](00-custom-instructions.md) ranking rubric).

## Modification 8 — Sector-strength gate (currently DISABLED)

**Moskowitz, T. J., & Grinblatt, M. (1999). "Do Industries Explain Momentum?"
*Journal of Finance*, 54(4), 1249–1290.**
Much of individual-stock momentum is actually industry momentum; the
52-week-high effect is materially stronger when the stock's own industry is
also leading. The gate keeps names only in sectors with strong breadth (members
above their 200-day SMA). **Off by default** (`sector_strength_top_fraction =
1.0`) pending a better industry-momentum metric — note this when it comes up.

## Modification 9 — Entry-timing overlay (feature 012, MOMENTUM-ONLY, default-off diagnostic)

**Minervini, M. (2013). *Trade Like a Stock Market Wizard*. McGraw-Hill** (base /
pivot / volume-confirmed-breakout structure). The "extended from the 200-day"
caution echoes **Faber (2007)** (already Modification 6). This is a **diagnostic
overlay, NOT a strategy and explicitly NOT CAN SLIM / O'Neil** — it changes no
gate, threshold, ranking, or citation; it only annotates each already-surfaced
momentum candidate with an objective *technical-state* classification.

It attaches **only** to `midterm_52w_high_momentum` (never value, never the
short-term strategies) and labels each candidate **entry-ready /
not-entry-ready / entry-undetermined** from six pass/fail/undetermined
components plus disqualifiers:

- **pivot_proximity** — within `entry_pivot_max_extension` (default **5%**) above
  the detected pivot; *below* the pivot → undetermined.
- **trend** — close above the 200-day SMA (Faber).
- **volume_confirmation** — breakout volume ratio ≥ `entry_volume_ratio_min`
  (default **1.4×**; ≥ **1.5×** reads as "strong").
- **base_maturity** — base ≥ `entry_flat_base_min_weeks` (**5w**, flat) /
  `entry_cup_base_min_weeks` (**7w**, cup) long.
- **base_depth** — base depth ≤ `entry_base_depth_max` (**33%**).
- **not_extended** — distance above the 200-day SMA ≤ `entry_sma200_extension_max`
  (**40%**).

Plus **disqualifiers**: **climax-top exhaustion** (a ≥ `entry_climax_advance_min`
**25%** trailing advance after a ≥ **8-week** prior trend) and **huge-gap
breakout** (gap > `entry_huge_gap_threshold` **5%** above pivot) both **force
not-entry-ready**; a **recent short-lived catalyst** attaches a non-directive
"elevated post-catalyst pullback risk" ("sell-the-news") caution that **does not**
force a state. Overall state = **not-entry-ready** if any component fails or a
forcing disqualifier triggers; **entry-undetermined** if any component is
undetermined (missing/unclassifiable data — never a false entry-ready);
**entry-ready** only when all six pass and nothing forces otherwise.

The base/pivot come from an explicit golden-fixture-tested geometric classifier
(`indicators/base_pattern.py`: flat / cup / cup-with-handle / double-bottom).
Unclassifiable patterns yield **entry-undetermined**, never a fabricated pivot.
Every label is neutral and **zero-directive** ("near pivot", "extended",
"immature base") — present it as a *state*, not a buy/sell instruction.
