# Phase 0 Research: Value-Based Mid-Term Strategy

All decisions below resolve the Technical Context. Each follows the project's
established pattern (mirror `midterm_52w_high_momentum`) unless a value-specific
concern forces a deviation.

---

## Decision 1 — Core value definition: multi-metric composite, not a single ratio

**Decision**: Rank by an equal-weight **composite of four cheapness yields**,
each computed as a *yield* (fundamental ÷ market value) so higher = cheaper and
negatives sort correctly:

- **Book-to-market** = common equity (StockholdersEquity) / market cap
- **Earnings yield** = net income (NetIncomeLoss, TTM) / market cap
- **Cash-flow yield** = operating cash flow / market cap
- **Sales yield** = revenue (TTM) / market cap

The composite is the mean of each name's **cross-sectional percentile rank** on
the available yields (so a missing single yield doesn't void the name; the
composite uses the yields it has, and the count is recorded).

**Rationale**: Single-ratio value (e.g. book/market alone) is noisy and biased by
sector and accounting regime; a composite is the standard academic and
practitioner robustness improvement and reduces the negative-book-value blow-ups
(Decision 5). Percentile-rank averaging is scale-free and avoids one large ratio
dominating. Anchored on Fama & French (1992) and Lakonishok, Shleifer & Vishny
(1994) (LSV value/contrarian premium).

**Alternatives considered**:
- *Book/market only (HML)* — simplest, but most exposed to negative/zero book
  value and sector distortion; rejected as the sole measure (still a composite
  member).
- *EBIT/EV (Greenblatt magic-formula numerator)* — strong, but EV requires
  reliable debt + cash + minority-interest assembly from EDGAR that is less
  consistently tagged than the four chosen concepts; deferred (can join the
  composite later behind the same percentile-rank machinery).
- *Single composite z-score instead of percentile rank* — z-scores are dominated
  by outliers; percentile rank is more robust for a cross-section with fat tails.

---

## Decision 2 — Value-trap gate: Piotroski (2000) F-Score

**Decision**: Compute the nine binary Piotroski signals and keep names at/above a
configurable floor (`min_f_score`, default **6** of 9). The nine signals:

*Profitability*: (1) ROA > 0; (2) operating cash flow > 0; (3) ΔROA > 0;
(4) accruals: operating cash flow > net income.
*Leverage/Liquidity/Funding*: (5) Δlong-term-leverage < 0; (6) Δcurrent ratio > 0;
(7) no new shares issued (Δshares ≤ 0).
*Operating efficiency*: (8) Δgross margin > 0; (9) Δasset turnover > 0.

**Rationale**: Piotroski (2000) showed the value premium concentrates in
financially *improving* cheap firms; the F-Score is the canonical, fully
deterministic, peer-reviewed value-trap filter and pairs naturally with a value
composite. A floor of 6 is Piotroski's "high score" band lower bound and a
defensible default; exposed as a tunable parameter.

**Alternatives considered**:
- *Reuse the momentum strategy's QMJ-style leverage+FCF quality screen* — simpler
  (already coded) but far weaker as a value-trap filter and not the cited
  value-investing instrument; rejected as the primary gate (the existing
  leverage/FCF check can remain as a secondary sanity gate).
- *Altman Z-score (distress)* — complementary but less directly tied to the value
  premium; deferred.

**Missing-input rule**: a signal whose inputs are unavailable point-in-time is
scored 0 (conservative — it does not award an unearned point), and the number of
*evaluable* signals is recorded so the gate can be reported as skipped/partial
rather than a false pass when coverage is thin (consistent with the momentum
strategy's honest gate accounting).

---

## Decision 3 — Cross-sectional thresholds via the reference-universe cache

**Decision**: Reuse the existing `reference_thresholds` mechanism. Cache the
value-composite percentile cut (and any absolute composite reference) over the
**compliant reference universe**, so a name's cheapness verdict does not flip with
the screened slice (Shariah on/off, universe size) and is identical across the
screen, single-ticker analysis, and candidate detail.

**Rationale**: This is exactly the problem `_apply_cross_sectional_gates` +
`load_reference_thresholds` already solve for gp/asset-growth; the value composite
has the same cross-sectional nature. Reuse keeps one consistent grading universe.

**Alternatives considered**: contemporaneous-universe quantile only (what the
momentum gates fall back to when no cache exists) — kept as the documented
fallback, not the default.

---

## Decision 4 — Distorted sectors (financials, REITs): rank the composite within sector

**Decision (FR-014)**: Compute the value composite **within sector** (percentile
rank among sector peers), then cap per sector exactly as momentum does via
`rank_within_sector`. Financials and REITs therefore compete against their own
peers rather than being spuriously ranked cheap/expensive against industrials.
The F-Score is still computed for them but its known weakness for financials
(leverage and turnover signals are less meaningful for banks) is **documented**
in the strategy declaration and the candidate `reason`.

**Rationale**: Book/market, gross margin, and asset turnover are structurally
different for banks/insurers/REITs; sector-relative ranking is the standard,
transparent fix and reuses code already present. Outright exclusion of whole
sectors was rejected as overly blunt for a personal-use tool and would silently
shrink the opportunity set.

**Alternatives considered**:
- *Exclude financials/REITs entirely* — simplest, but discards a large,
  legitimately screenable slice; rejected.
- *Substitute sector-appropriate metrics (e.g. P/B-only for banks)* — more
  faithful but adds per-sector special-casing and more code paths; deferred.

---

## Decision 5 — Negative / zero / undefined valuation inputs (FR-015)

**Decision**: Because every measure is a **yield** (fundamental ÷ positive market
cap), a negative numerator yields a negative number that correctly sorts as
*least cheap*, never as "infinitely cheap" (the failure mode of price/earnings or
price/book where a tiny/negative denominator explodes). Names with **negative book
value** receive a real (negative) book-to-market and are not awarded a top rank.
A yield whose numerator is entirely missing is dropped from that name's composite
(composite computed over available members), and a name with **zero** evaluable
yields is excluded with a recorded reason.

**Rationale**: Yields + percentile ranks make sign-handling automatic and avoid
denominator blow-ups; this is the single biggest correctness win of the
composite-of-yields design over a composite-of-ratios.

---

## Decision 6 — Regime favorability

**Decision**: Declare `REGIME_FAVORABILITY = {Trending up: Neutral, Range-bound:
Favorable, Trending down: Neutral}`. The strategy is **not** marked Unfavorable in
downtrends (so the Faber regime master-switch does not auto-block all entries),
because the value/contrarian premium historically does part of its work entering
weakness — but it is only Neutral in trends, where momentum dominates.

**Rationale**: Honest, literature-consistent, and avoids over-claiming. Marking it
Unfavorable in downtrends would (via `strategy_is_regime_sensitive` +
`regime_gate`) suppress exactly the contrarian entries the thesis targets. The
declaration is the single source of truth the regime engine and advisor prompt
read.

**Alternatives considered**: copy momentum's favorability (Unfavorable in
downtrends) — rejected as thesis-inconsistent.

---

## Decision 7 — Holding period, levels, and stop logic

**Decision**: `HOLDING_PERIOD = {min: 60, max: 180}` (same mid-term band as
momentum, so the 003 comparison and 004 export apply unchanged). Levels reuse the
momentum derivation: entry = close; primary stop = trend (200-day SMA when below
entry) with the 3-ATR disaster fallback; expose the tighter structure stop; take-
profit = entry + R-multiple × (entry − stop). Value names need a wider berth, so
the **default `take_profit_r_multiple` is higher** (research default 4.0 vs
momentum's 3.0) — tunable.

**Rationale**: Reusing the proven level machinery keeps the UI, comparison, and
prompt consistent; the only value-specific tuning is a more patient profit target.
A value thesis is mean-reversion, so a hard time-based or valuation-normalization
exit is a future enhancement, not v1.

---

## Decision 8 — Fundamentals pipeline extension (the real new work)

**Decision**: Add `FundamentalsLoader.value_metrics_as_of(ticker, as_of, payload)`
returning point-in-time: common equity, net income (TTM), operating cash flow,
revenue (TTM), and the prior-year values + current assets/liabilities + long-term
debt + shares outstanding needed for the nine F-Score deltas. Extend the runner's
`NEEDED_TAGS` slim cache and `_edgar_profiles` / `_compute_snapshot_rows` so the
new columns flow into the universe snapshot the same way `gp_to_assets` /
`asset_growth` already do. Market cap = close × point-in-time shares outstanding.

**Rationale**: All required concepts are standard us-gaap tags EDGAR already
exposes; the slim-cache + `_latest_as_of` pattern already enforces point-in-time
discipline. This is an extension of a working pipeline, not a new one.

**Concepts to add to `NEEDED_TAGS`**: `NetIncomeLoss`,
`EntityCommonStockSharesOutstanding` (or `CommonStockSharesOutstanding`),
`AssetsCurrent`, `LiabilitiesCurrent`, `LongTermDebtNoncurrent` (and common
fallbacks). `StockholdersEquity`, `Revenues`/`RevenueFromContract…`, `GrossProfit`,
`Assets`, and `NetCashProvidedByUsedInOperatingActivities` are already cached.

---

## Decision 9 — Backtest scope and the honest pre-2011 fundamentals limitation

**Decision**: Run `--strategy midterm_value_composite --start 2008-01-01 --end
2024-12-31`, producing walk-forward per-year metrics. Set `uses_fundamentals =
True` for the value slug and add its candidate-pool branch (the value pool is
simply the liquid, ≥252-bar universe — ranking happens inside `rules()`, there is
no price pre-filter like near-high). The honest `bias_check` will report
**survivorship FAIL** (Stooq lacks delisted names) and `coverage_notes` will flag
that **SEC XBRL fundamentals are sparse before ~2011**, so 2008–2010 contribute
few/no trades for this (fundamentals-dependent) strategy.

**Rationale**: This is the same true, already-surfaced limitation the momentum
strategy carries — the window *spans* ≥15 years incl. 2008–2009 and every year
gets a metric row (some empty for documented data reasons). Pretending otherwise
would violate Principle III. The strategy stays **disabled by default** under the
registry's `_window_meets_floor`/bias gating; an explicit `SCREENER_*` operator
override (mirroring `OPERATOR_TREAT_AS_VALID`) is available if the single user
wants it live with eyes open.

**Alternatives considered**: a paid point-in-time fundamentals vendor (EOD
Historical Data) to backfill pre-2011 — out of scope for v1 personal-use; noted as
the upgrade path if coverage proves insufficient.

---

## Decision 10 — Advisor-prompt builder generalization

**Decision**: Make `agent/advisor_prompt.py` strategy-agnostic for the two spots
that are momentum-specific: (a) parameterize the backtest artifact path in
`load_survivorship_status` by slug (default still momentum for back-compat), and
(b) replace the hardcoded momentum ranking sentence in `_strategy_context` with
one derived from the strategy (or a generic phrasing), and extend
`_diagnostics_lines` to surface value fields (composite score, F-Score, the four
yields) when present.

**Rationale**: FR-016 requires the value strategy to export through 004; the
builder already reads the live `Strategy` declaration and `gate_results`
generically, so only these two momentum-specific assumptions need lifting. Keeps
one builder as the single source of truth for both strategies.

---

## Resolved unknowns summary

| Unknown | Resolution |
|--------|-----------|
| Which value metrics | Composite of book/market, earnings, cash-flow, sales **yields** (D1) |
| Value-trap filter | Piotroski F-Score ≥ 6 (D2) |
| Cross-sectional stability | Reference-threshold cache reuse (D3) |
| Financials/REITs | Within-sector composite ranking (D4) |
| Negative/zero inputs | Yields + percentile ranks sort them correctly (D5) |
| Regime stance | Neutral/Favorable/Neutral (D6) |
| Holding & levels | Mid-term 60–180d; momentum level machinery; R-multiple 4.0 (D7) |
| Data pipeline | `value_metrics_as_of` + `NEEDED_TAGS` extension (D8) |
| Backtest & bias | 2008–2024 walk-forward; survivorship + pre-2011 sparsity surfaced honestly; disabled by default (D9) |
| Advisor export | Generalize builder backtest path + diagnostics (D10) |
