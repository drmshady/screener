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

## Modification 8 — Sector-strength gate (currently DISABLED)

**Moskowitz, T. J., & Grinblatt, M. (1999). "Do Industries Explain Momentum?"
*Journal of Finance*, 54(4), 1249–1290.**
Much of individual-stock momentum is actually industry momentum; the
52-week-high effect is materially stronger when the stock's own industry is
also leading. The gate keeps names only in sectors with strong breadth (members
above their 200-day SMA). **Off by default** (`sector_strength_top_fraction =
1.0`) pending a better industry-momentum metric — note this when it comes up.
