# Honesty & Limitations — read this before trusting any performance number

This is the file that keeps the advisor honest. Every limitation below is real
and current. Surface the relevant ones whenever they bear on an answer — do not
wait to be asked.

## 1. The backtest FAILS its survivorship-bias check (most important)

- The strategy is enabled by an **operator override**
  (`SCREENER_TREAT_STRATEGY_VALID`), *not* because it passed the constitution's
  gates. Its backtest's `survivorship_bias` check is **failing**.
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

- **Low asset-growth gate** — point-in-time asset growth is sparse; missing ⇒
  passes through.
- **Volume confirmation** — missing recent/50-day volume ⇒ passes through.
- **Quality screen** — a name with missing `debt_to_equity` or `fcf_ttm` is not
  evaluated on that gate.

If the user's pasted gate breakdown shows `skipped` or "passed-through," call it
out. A name can look like it "cleared everything" while actually only clearing
the 52-week-high proximity gate on thin data.

## 3. Gross-profitability is "top half of the screened universe"

The gp/assets and asset-growth gates are **cross-sectional** — "top/bottom half"
is relative to the universe being screened that day, not an absolute threshold.
The same stock can pass or fail depending on what else is in the universe.

## 4. Data sources & freshness

- **Current prices:** yfinance (end-of-day).
- **Deep history & delisted-coverage attempts:** Stooq daily-bar bundles
  (but, per #1, no true delisted names on the free tier).
- **Fundamentals / filings:** SEC EDGAR, refreshed within ~2 business days of a
  10-Q/10-K.
- This is an **end-of-day, mid-term** tool. It is not intraday. Prices the user
  pastes may be up to one trading day stale; ask for the as-of date.

## 5. What this strategy is NOT good for

- **Not** day-trading or scalping (it's a 60–180 day holding strategy).
- **Not** multi-year buy-and-hold (out of scope per the project constitution).
- **Not** reliable in a "Trending down" regime — momentum crashes happen exactly
  on the snap-back from a downtrend.
- **Not** a guarantee. Anchoring/underreaction is a statistical edge across many
  names, not a promise about any single stock.

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
