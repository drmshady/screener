# Honesty & Limitations — read this before trusting any performance number

This is the file that keeps the advisor honest. Every limitation below is real
and current. Surface the relevant ones whenever they bear on an answer — do not
wait to be asked.

> **Applies to BOTH mid-term strategies.** Momentum and value are *both*
> enabled by operator override with a failing survivorship check; everything in
> this file applies to whichever strategy is in scope. Differences are flagged
> inline.

## 1. The backtest FAILS its survivorship-bias check (most important)

- The strategy is enabled by an **operator override** (momentum:
  `SCREENER_TREAT_STRATEGY_VALID`; value: `SCREENER_VALUE_TREAT_AS_VALID`),
  *not* because it passed the constitution's gates. Its backtest's
  `survivorship_bias` check is **failing**. (For value, the backtest artifact may
  not even exist yet — in which case survivorship shows as UNCONFIRMED, which is
  *not better* than FAILED; treat any value performance claim as unverified.)
- **Why:** the free Stooq daily-bar bundle contains **no delisted tickers**.
  Companies that went to zero or got acquired are missing from history, so the
  backtest only ever "traded" survivors.
- **Consequence:** historical hit-rate, total return, and average win are
  **optimistic** — the real-world numbers would be worse, especially through
  2008–2009. **State this every time you discuss expected/backtested
  performance.** Never present the backtest stats as if they were clean.

## 2. Free data tier ⇒ several gates "fail open"

When a fundamental is missing, these gates pass the name through rather than
reject it — so a "pass" can mean "we had no data," not "it genuinely passed":

**Momentum (`midterm_52w_high_momentum`):**

- **Low asset-growth gate** — point-in-time asset growth is sparse; missing ⇒
  passes through.
- **Volume confirmation** — missing recent/50-day volume ⇒ passes through.
- **Quality screen** — a name with missing `debt_to_equity` or `fcf_ttm` is not
  evaluated on that gate.

A momentum name can look like it "cleared everything" while actually only
clearing the 52-week-high proximity gate on thin data.

**Value (`midterm_value_composite`):**

- **Leverage sanity** — missing `debt_to_equity` ⇒ passes through.
- **BUT the F-Score gate does the opposite — it FAILS CLOSED.** A name with no
  point-in-time financials can't be scored and is **excluded** (the value-trap
  filter refuses to vouch for an unscoreable name). So a value match that
  survived *did* get scored — but check **how many of the 9 signals were
  evaluable** and **how many of the 4 yields** built its composite. Few of
  either = low confidence, even though it "passed."

If the user's pasted gate breakdown shows `skipped` or "passed-through," call it
out either way.

## 3. Cross-sectional gates are universe-relative, not absolute

Several gates rank a name *against the rest of the universe that day*, so the
same stock can pass or fail depending on what else is screened:

- **Momentum:** the gp/assets and asset-growth gates are "top/bottom half" of
  the screened universe.
- **Value:** the composite is built from **cross-sectional percentile ranks** of
  each yield, and the cheapness cut ("cheapest top half") is a universe quantile
  (or a cached reference-universe threshold). A value composite of 0.80 means
  "cheaper than ~80% of peers in this run," not an absolute cheapness. With
  `within_sector_ranking` on, that percentile is **within the name's sector** —
  so "cheap" means cheap *relative to its sector peers*, which is the point.

## 4. Data sources & freshness

- **Current prices:** yfinance (end-of-day).
- **Deep history & delisted-coverage attempts:** Stooq daily-bar bundles
  (but, per #1, no true delisted names on the free tier).
- **Fundamentals / filings:** SEC EDGAR, refreshed within ~2 business days of a
  10-Q/10-K.
- This is an **end-of-day, mid-term** tool. It is not intraday. Prices the user
  pastes may be up to one trading day stale; ask for the as-of date.

## 5. What this strategy is NOT good for

- **Not** day-trading or scalping (both are 60–180 day holding strategies).
- **Not** multi-year buy-and-hold (out of scope per the project constitution).
- **Regime-specific (they differ!):** *Momentum* is **Unfavorable** in a
  "Trending down" regime — momentum crashes happen on the snap-back from a
  downtrend. *Value* treats a downtrend as **Neutral** (it deliberately enters
  weakness) and is strongest **Range-bound**; its risk is the opposite — a
  **value trap** that stays cheap or gets cheaper, which is exactly what the
  F-Score gate tries to filter.
- **Not** a guarantee. The momentum (anchoring/underreaction) and value
  (mispricing/mean-reversion) edges are statistical, across many names — not a
  promise about any single stock.

## 6. The advisor cannot compute — it interprets

Claude in the app has no access to the screener's code or live data. It must use
the numbers the user pastes. If it does light arithmetic (e.g. reward:risk), it
shows the work and labels it as derived. It must never assert a gate outcome
from its own memory of a stock's price — that memory is stale and unreliable.

## 7. Determinism

The screener is deterministic: the same frozen data snapshot produces the same
screen, regime, sizing, and gate output every run. If two runs disagree, the
input snapshot changed — flag that rather than hand-waving it.

## 8. No-advice boundary (scope reminder)

Directive personalized calls are permitted **only because this is a private,
single-user tool.** If the output is ever shared, hosted, or sold, the
constitution's non-negotiable no-advice boundary applies again: revert to
neutral framing ("screen match," "candidate for further research"), drop
buy/sell language, and keep the disclaimer + citation + as-of date on
everything.

## 9. Data Integrity & Suspect Signals (Feature 008)

- **The screener self-checks its output:** Every candidate is validated against
  an `OutputContract` (coherence, gate satisfaction, score reproduction, level
  sanity, value-domain, and series integrity).
- **Loud flagging:** Any name that violates a check carries a `DATA INTEGRITY
  WARNING` badge and is **demoted** to the bottom of the list.
- **Verification required:** If a name is flagged, **verify its figures manually**
  before acting. The "DATA INTEGRITY WARNING" in the advisor prompt names the
  specific suspect figure (e.g., "unexplained single-session jump").
- **Seam adjustment:** For US momentum, history is stitched from Stooq and
  yfinance; a back-adjustment factor is used to align them. If the seam is
  unstable, it is flagged.

## 10. Bounded levels, fair value & sizing (Feature 011)

- **Levels are risk-bounded, not predictions.** Risk distance is clamped to
  1–4×ATR and the take-profit is a 3R/4R target *capped at a volatility ceiling*.
  These are disciplined risk geometry, **not** forecasts of where the price will
  go. When inputs are missing the candidate shows `levels_state =
  insufficient_data` (no stop/target) — say the levels can't be derived rather
  than inventing one.
- **Fair value is a rough, conservative estimate with limited coverage.** It is
  the **Graham number** from free EDGAR yields (or book value per share) — a
  blunt instrument. It is `trusted` for only ~60% of momentum candidates;
  otherwise `unavailable` / `stale` / `out_of_range`. **Momentum winners
  typically trade well ABOVE Graham fair value** (negative margin of safety) —
  that is expected and is *not* a sell signal. Never present fair value as a
  price target, and only lean on it when its trust flag is `trusted`.
- **Sizing is risk-first and cap-bounded; conviction modulation is OFF.** The
  default `sizing_conviction_signal = none`: a fair-value modulator was tested
  and **rejected for momentum** because it shrank almost every winner. So the
  size reflects the stop width and the caps — nothing more. Don't claim the size
  encodes "conviction."
- **Determinism preserved.** The bounded levels and sizing are deterministic on a
  fixed snapshot (see #7).

## 11. Entry-timing overlay & the news search (Feature 012, MOMENTUM only)

- **It is a diagnostic, not a strategy or a signal.** The `entry-ready /
  not-entry-ready / entry-undetermined` classification and its six components
  change **no gate, threshold, ranking, or citation** — they annotate an
  already-surfaced momentum candidate with an objective technical *state*
  (Minervini 2013; Faber 2007). It is **not** CAN SLIM / O'Neil. It attaches to
  `midterm_52w_high_momentum` only — never value, never short-term. Default OFF.
- **`entry-undetermined` ≠ bad setup.** It means a component could not be
  evaluated (missing data, or a base the geometric classifier couldn't label).
  The overlay is built to **never emit a false entry-ready** — when in doubt it
  abstains. Say "undetermined," don't upgrade it to a pass.
- **Expanded coverage retains, it does not bless.** With `expanded_coverage` on,
  a non-passing *preferred* gate (market regime / sector strength / relative
  strength) is kept but marked `skipped` and **demoted below every clean name**.
  A `skipped` preferred gate is **not** a pass — flag it exactly like a
  fail-open pass (see #2). Essential gates and disqualifiers still exclude /
  force not-entry-ready regardless of the toggle.
- **The short-lived-catalyst flag is structural, not informed.** The overlay can
  see a sharp recent advance; it cannot read *why*. That is what the **news
  search** is for. When you search: **cite and date every source**, treat
  results as possibly stale/wrong/paywalled, and use them only for the
  catalyst/timing-risk narrative — **never** to recompute a gate or to assert a
  price/fundamental the screener didn't produce (see #6, and Custom-Instructions
  rules 8–9).
- **Determinism still holds for the overlay itself** — same snapshot ⇒ same
  classification. (Web-search results are *not* part of that snapshot and are not
  deterministic; keep the two clearly separate.)
