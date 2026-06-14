# Modifications & Citations — Mid-Term Value Composite

The base method is the value/contrarian premium (Fama & French 1992;
Lakonishok, Shleifer & Vishny 1994). Everything below is a deliberate
**modification** layered on top, each with its own published source. When you
explain *why* a gate exists, cite the matching source here. Do not attribute
findings to a paper beyond what is summarized; if you're unsure, say so.

## Base method — the value composite

**Fama, E. F., & French, K. R. (1992). "The Cross-Section of Expected Stock
Returns." *Journal of Finance*, 47(2), 427–465.**
Book-to-market equity is one of the strongest cross-sectional predictors of
average returns: high book/market ("value") stocks earn higher subsequent
returns than low book/market ("growth/glamour") stocks, and this premium is not
explained by market beta.

**Lakonishok, J., Shleifer, A., & Vishny, R. W. (1994). "Contrarian Investment,
Extrapolation, and Risk." *Journal of Finance*, 49(5), 1541–1578.**
The value premium is driven by behavioral mispricing, not extra risk: investors
over-extrapolate past growth, overpricing glamour stocks and underpricing
out-of-favor value stocks. A contrarian, value-tilted portfolio outperforms
without bearing more fundamental risk. → Justifies combining **multiple** value
yields (book/market, earnings, cash-flow, sales) rather than book/market alone,
to capture cheapness robustly. The composite is the **equal-weight mean of the
available metrics' cross-sectional percentile ranks** (higher = cheaper);
missing members are ignored and the count reported.

## Modification 1 — Piotroski F-Score health gate (the value-trap filter)

**Piotroski, J. D. (2000). "Value Investing: The Use of Historical Financial
Statement Information." *Journal of Accounting Research*, 38 (Supplement),
1–41.**
The value premium concentrates in the cheap firms that are financially
*improving*; many cheap stocks are cheap for good reason ("value traps").
Piotroski's nine binary fundamental-health signals separate the two. Buying only
high-F-Score value names — and avoiding low-F-Score ones — sharply raises the
value premium. Here the floor is **F-Score ≥ 6** (the lower bound of his
high-score band). **A name that can't be scored is excluded** (not passed
through), because the whole point of the gate is to confirm the cheap name is
*not* a trap.

**The nine signals (1 point each; the screener also reports how many of the nine
were *evaluable* given the data):**

*Profitability*
1. **ROA > 0** — positive return on assets this year.
2. **CFO > 0** — positive operating cash flow this year.
3. **ΔROA > 0** — ROA improved versus last year.
4. **Accruals** — operating cash flow exceeds net income (earnings backed by
   cash, not accruals).

*Leverage, liquidity, dilution*
5. **Δ leverage < 0** — long-term-debt / assets fell.
6. **Δ current ratio > 0** — current ratio improved (better liquidity).
7. **No dilution** — shares outstanding did not increase.

*Operating efficiency*
8. **Δ gross margin > 0** — gross margin improved.
9. **Δ asset turnover > 0** — revenue / assets improved.

> A signal whose inputs are missing scores **None** (no point, and it lowers the
> evaluable count) — never a silent pass. So "F-Score 4/9 (4/9 signals
> evaluable)" means only four signals had data; treat it as **low-confidence**,
> not a genuine 4. Tell the user when the evaluable count is well under 9.

## Modification 2 — Within-sector ranking

**Asness, C. S., Frazzini, A., & Pedersen, L. H. (2013). "Value and Momentum
Everywhere." *Journal of Finance*, 68(3), 929–985.**
Value works across markets and asset classes, but raw value multiples differ
structurally by industry — banks and REITs always look "cheap" on book/market,
utilities on earnings yield. Ranking each name's value composite **within its
sector** (`within_sector_ranking = True`, default on) makes it compete with its
real peers, so the screen surfaces the cheapest *bank among banks*, not just
"all the banks." This is FR-014 distorted-sector handling.

## Modification 3 — Sector concentration cap

**Documented risk-control overlay (practitioner convention; not a single
paper).** Cap the result list at `max_per_sector = 5` so the screen can't pile
into one structurally cheap sector. This is a concentration control, not an
alpha claim — describe it that way.

## Modification 4 — Optional momentum floor ("not a falling knife"), OFF by default

**Asness, C. S., Frazzini, A., & Pedersen, L. H. (2013). "Value and Momentum
Everywhere." *Journal of Finance*, 68(3), 929–985.**
Value and momentum are negatively correlated but each carries a premium, so a
mild momentum overlay on a value screen removes the worst of the value traps —
cheap names that are cheap *because the price is in free-fall* — without
abandoning the contrarian thesis. The optional `min_momentum_12_1` gate keeps
only names whose 12-1 momentum is at or above the floor. **It is disabled by
default** (`-1.0` = pure value, no floor); the published variant raises it to
**`-0.20`** (tolerate up to a 20% trailing-year decline, no worse). The gate
**fails open** — a name with no momentum reading passes through (recorded as
skipped), so missing data never silently drops a value name.

This is the **single A/B parameter the value side of the four-variant
side-by-side run toggles** (feature 006: momentum floor ON `-0.20` vs OFF
`-1.0`), shown side-by-side so you can see exactly which cheap names a falling-
knife filter would have removed. It changes no default — pure value remains the
shipped default. Note the same AFP (2013) paper also grounds within-sector
ranking (Modification 2); cite it for both, but describe the momentum overlay as
a *value-trap defense*, not a momentum strategy.

## What is intentionally *looser* than the momentum strategy

- **Leverage ceiling D/E ≤ 2.0** (vs momentum's 1.5) — value names legitimately
  carry more debt; this is only a sanity ceiling, and it **fails open** on
  missing D/E.
- **No SMA-200 entry filter** — the 200-day SMA is used only to place the
  trailing stop. Value deliberately *enters weakness*, so requiring price above
  its long-term average would defeat the thesis. (Contrast: momentum *requires*
  `close > SMA-200`.)
- **4R take-profit** (vs 3R) — mean-reversion needs more time to pay off.

These are deliberate design choices grounded in the contrarian thesis, not
oversights — explain them that way if asked why value "looks less strict."
