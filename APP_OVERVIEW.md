# US Stock Screener — App Overview

> A single-owner, rule-based equity screener built for disciplined, risk-aware investing.
> Every result is timestamped, strategy-cited, and carries a non-advice disclaimer.
> No "Buy" / "Sell" language anywhere in the app.

---

## What the App Does

Screens the full US-listed common-equity universe (~6,000 tickers after liquidity filters)
using peer-reviewed, fully documented strategies. For every candidate it shows **entry levels,
stop-loss, take-profit**, and a **risk-aware position size** based on the owner's actual
capital and portfolio. Results are deterministic — the same data snapshot always produces
the same output.

---

## Core Features

### 1. Strategy Screens

| Strategy | Timeframe | Basis |
|---|---|---|
| **52-Week High Momentum** | Mid-term (weeks–months) | George & Hwang (2004); vol-scaled, sector-ranked, quality-gated |
| **Minervini VCP Breakout** | Short-term (days–weeks) | Minervini stage-2 pattern + ADR contraction + volume confirmation |
| **ATR Volatility Breakout** | Short-term (days–weeks) | Chandelier exit + 200-day trend-of-trend filter |

Each strategy card shows:
- **Why it matched** — one-line rule summary per candidate
- **Strategy name + citation** — traceable to published research
- **Regime label** — Favorable / Neutral / Unfavorable given current market conditions
- **Data as-of date + disclaimer** — on every view, unconditionally

---

### 2. Risk Levels Per Candidate

Three price levels are derived from the same volatility inputs, not guessed:

| Level | What it is |
|---|---|
| **Stop-loss** | ATR-based risk cap; attributed to the constraint that actually set it |
| **Take-profit** | Volatility/horizon-aware reward ceiling |
| **Trailing stop** *(open holdings)* | Chandelier exit above cost — a winner's floor |

The UI also surfaces:
- **Risk distance** (% from entry to stop)
- **Reward-to-risk ratio**
- Which constraint was **binding** (e.g. "ATR cap set this stop, not the SMA rule")

---

### 3. Position Sizing

Risk-per-trade backbone — never cap-fill guessing:

- Sizes each position so the **dollar loss to the stop ≤ configured % of capital** (default 1%)
- Shows **recommended shares**, dollar amount, and resulting % of portfolio
- Reports the **binding constraint** (per-position cap, per-sector cap, or heat ceiling)
- Displays **portfolio heat headroom** — how much open risk remains before the aggregate ceiling
- **Conservative fallback** when any input is missing — never silently fills to the position cap

---

### 4. Portfolio Management

- Record holdings: ticker, share count, average cost
- Set total capital; app computes cash balance automatically
- Per-holding view shows **original-plan vs. current-condition** stop/target (purchase-price-anchored)
- **Sector exposure** — dollar + % per sector with concentration flags
- Import holdings from a Google Sheet (buy/sell transaction log → auto-aggregated)
- Watchlist with save / dismiss / "acted on" + free-text notes
- Export and re-import portfolio as a single file

---

### 5. Market Regime

- **SPY 200-day SMA rule** — Trending Up / Neutral / Trending Down
- Shows the exact close, SMA value, and verdict with source and as-of date (never "Unknown")
- Each strategy card is labeled Favorable / Neutral / Unfavorable for the current regime
- Optional **regime-aware risk budget** — scales position risk fraction by regime (opt-in; byte-identical when off)

---

### 6. Shariah-Compliance Filter

- Toggle ON/OFF; default OFF (non-Muslim users unaffected)
- Universe filtered against **SPUS ETF holdings** (FTSE USA Shariah index) + owner-curated inclusion/exclusion lists
- Each compliant result carries a **badge with source name and as-of date**
- Portfolio holdings show "Not Shariah-compliant" or "Compliance changed" tags
- Stale source → warning shown, filtering continues on last-known list

---

### 7. News & Events Awareness

- **Earnings badge** — "Earnings in N days" for candidates within 14 days; links to EDGAR filing
- **Material news badge** — count of 8-K filings in the trailing 30 days
- **Earnings exclusion filter** — per-screen toggle to remove candidates with earnings within N days
- **Market Events panel** (home dashboard) — scheduled FOMC / CPI / NFP / PCE / PPI releases with dates and actual-vs-expected values after release

---

### 8. AI Sentiment & Narrative *(on-request, informational only)*

- Triggered manually by the owner — never automatic
- **Sentiment score** computed by FinBERT (finance-domain ONNX model, baked into the image) with a Loughran-McDonald lexicon fallback
- **Narrative prose** generated once, fingerprint-keyed, served back byte-identically — never regenerated per view
- Narrative model is swappable: Gemini (default free tier), Claude Haiku, or template-only
- Hard **~$5/month spend cap** — degrades to a deterministic template when reached
- Carries a **narrative-risk overlay** (0–100) with neutral labels; never changes any gate, rank, or sizing result

---

### 9. Walk-Forward Backtest Panel

Displayed per strategy under `/strategies/{slug}/backtest`:

- **Walk-forward per-year metrics** — annual return, max drawdown, Sharpe
- **Trade counts per period** + **low-reliability flags** (thin-sample years marked)
- **Explicit cost model** — disclosed per-side transaction cost baked in
- **Finer-than-annual rebalance cadence** — not January-only
- Survivorship-bias check result surfaced honestly (PASS / WARNING / FAIL with explanation)
- Backtest artifact is **baked into the image** at publish time — never computed live on the hosted backend

---

## Honesty & Safety Guarantees

| Guarantee | How it's enforced |
|---|---|
| **Determinism** | Same snapshot → byte-identical output; no hidden randomness |
| **No directive language** | Playwright lint on every page ("Buy", "Sell", "Recommended" are blocked) |
| **Data as-of + disclaimer** | Injected on every API response; rendered unconditionally in the layout shell |
| **Strategy citations** | Each strategy declares NAME, CITATION, TIMEFRAME, PARAMETERS, MODIFICATIONS — registry refuses to load incomplete declarations |
| **Binding-constraint attribution** | Stop/sizing rationale names the rule that actually set the value |
| **Conservative sizing fallback** | Missing modulator → smaller position, never cap-fill |
| **Spend cap** | AI narrative cost enforced *before* every paid call; degrades to template, never exceeds budget |

---

## Access & Deployment

- **Single owner** — Google sign-in (allowlisted email) fronting a same-origin BFF proxy
- **Backend**: Hugging Face Docker Space (FastAPI + baked Parquet snapshot)
- **Frontend**: Vercel (Next.js BFF; browser never talks directly to the backend)
- **Data**: Baked read-only snapshot refreshed locally and published daily via GitHub Actions
- **Secrets**: Runtime environment only — never committed or written to any artifact

---

## Data Sources

| Source | Used for |
|---|---|
| **Stooq daily bundles** | Deep price history (2008–2024) including delisted tickers — required for honest backtests |
| **yfinance** | Current EOD prices, earnings dates, news headlines |
| **SEC EDGAR** | 8-K filings, fundamentals, company catalog |
| **SPUS ETF holdings** | Default Shariah compliance universe |
| **Finnhub / Alpha Vantage** *(optional)* | News backup for sentiment (owner-supplied keys) |

All sources are free or low-budget; personal-use scope only.

---

*Generated 2026-07-02 from branch `015-momentum-risk-hardening`.*
