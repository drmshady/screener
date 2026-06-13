# Saudi (Tadawul / TASI) market expansion — data sources & feasibility (Phase 16)

**Status:** feasibility spike (T166–T172). **Personal/test only — not for redistribution.**

## Decision (operator, 2026-06-11)
- **Price data:** "research it" → **yfinance `.SR`** for the test (free, reuses our exact ingest pipeline). Licensed/always-on alternatives noted below.
- **Shariah compliance:** **treat every seeded Saudi name as compliant, test-only, clearly flagged unverified** (source `saudi_all_compliant`). NOT a ruling.
- **Scope:** feasibility spike first; harden later.

## Data-source options researched

| Source | Type | Cost | Notes |
|---|---|---|---|
| **yfinance `.SR`** | scrape (Yahoo) | free | Confirmed: Tadawul on Yahoo with numeric `.SR` codes (Aramco `2222.SR`, index `^TASI.SR`); prices in **SAR**, sector + most fundamentals present. **Personal-use only.** Chosen for the test — reuses our ingest/overlay/staleness code. |
| **SAHMK API** | Tadawul-licensed | free tier (15-min delay, 100 req/day) + paid | REST + WebSocket; history + financials + events. The proper **licensed** path for anything beyond personal testing. |
| **Twelve Data (XSAU)** | API | freemium | EOD + intraday for the Saudi Exchange. |
| **EODHD** | API | ~$20/mo | Covers Tadawul incl. deep history; clean + automatable. |
| **Kaggle Tadawul dataset** | static bulk | free | One-time historical seed (the Saudi analogue of our Stooq bundle) for backtests. |

## What was built (spike)
- `backend/src/data/saudi_universe.py` — curated ~42-name TASI starter list (`.SR`), with provenance. Not exhaustive, not point-in-time.
- `backend/src/data/shariah_saudi.py` — `seed_saudi_all_compliant()` → `saudi_all_compliant` source (TEST ONLY, flagged).
- `scripts/screen_saudi.py` — runs the midterm strategy on the Saudi universe end to end via the yfinance path, SAR-calibrated thresholds, regime gate OFF.

## Reuse, not fork
Passing `parameters.tickers = <Saudi list>` routes `run_strategy` through `build_universe_snapshot` (the yfinance path), which fetches **both** prices and profile fundamentals from Yahoo — so Saudi names flow through the existing liquidity gate, strategy gates, staleness gate, and candidate builder with **no engine changes**.

## Known limitations / caveats (honest)
- **Currency:** prices are in **SAR**, so the liquidity gate must use SAR thresholds (not the US $5 / $1M). The UI still formats values with a `$` prefix — a real SAR-aware formatter is outstanding (T172 UI).
- **Trading calendar:** Tadawul trades **Sun–Thu** (Fri–Sat weekend). The incremental-fetch cutoff (`latest_completed_trading_day`) and the staleness gate use the **US Mon–Fri** calendar. In practice the staleness gate compares each name to the *max Saudi bar in the data*, so fresh names aren't wrongly excluded — but the fetch cutoff is imprecise for Saudi. A market-aware calendar is outstanding.
- **Fundamentals:** yfinance `.info` provides FCF / debt-to-equity / gross profit for most Saudi names, but **banks lack FCF** (as in the US) → the quality gate (fails closed) drops them. Not point-in-time (current snapshot only), so a Saudi **backtest** would need a fundamentals history source (SAHMK/EODHD).
- **Regime:** the regime gate is SPY/US-based and is disabled for Saudi; a TASI regime model is future work.
- **Compliance is fake** (test-only all-compliant) — must be replaced before any real use.

## Feasibility findings (live run, 2026-06-11)

**Verdict: the Saudi expansion is feasible for live screening via yfinance `.SR`.** The midterm strategy ran end-to-end over the 43-name TASI starter universe with **zero engine changes**.

- `data_as_of: 2026-06-11` — **fresh** (yfinance returned the current Saudi session; the US-calendar staleness logic did not wrongly exclude names).
- **3 candidates** (SAR prices), each passing proximity + gross-profitability + sector-strength + volume + 200-SMA trend + quality (low D/E, positive FCF) gates:
  - `2222.SR` Aramco (Energy) — entry 27.18, stop 25.65, tighter 26.84, target 31.76
  - `7010.SR` STC (Communication Services) — entry 44.34, stop 43.28, tighter 42.90, target 47.53
  - `2050.SR` Savola (Consumer Defensive) — entry 29.80, stop 24.81, tighter 25.68, target 44.76
- **Honest data_notes (the real gaps):**
  - fundamentals missing for **10/39** names (banks etc. lack `freeCashflow` on Yahoo) → can't pass the fails-closed quality gate;
  - **asset-growth gate skipped** — `asset_growth` is computed from SEC EDGAR (US-only), so the q-theory gate is inactive for Saudi;
  - 1 name dropped by the quality gate for missing fundamentals.

**Conclusion / next steps to harden:**
1. A Saudi **backtest** needs a fundamentals *history* + deep price history source (SAHMK / EODHD / Kaggle) — yfinance only gives the current fundamentals snapshot (T171).
2. The **asset-growth** and (US) **regime** gates need Saudi equivalents or should be explicitly marked N/A for Saudi.
3. **UI**: a market selector + SAR-aware formatting (T172 UI) — currently the screen is driven from a script.
4. Replace the **fake all-compliant** source with a real Saudi compliance source before any non-test use.

## Saudi backtest (T171, Kaggle history)
Operator supplied the **Kaggle Tadawul dataset** (`Tadawul_stcks.csv.zip`, root): 593,819 bars, 199 symbols, **2001-2020 (incl. the 2008-2009 crisis** the US EDGAR fundamentals couldn't reach). Built into `backend/data/prices/saudi_parquet/` via `scripts/build_saudi_parquet.py` (numeric codes → `.SR`). Backtested via the runner's injectable `prices=` (`scripts/backtest_saudi.py`), writing a `_saudi`-suffixed artifact so US artifacts are untouched.

- **Price-only strategy works**: `shortterm_atr_breakout` on Saudi 2005-2020 → **−6.9%** total, hit 46%, 37 trades, maxDD 17% — **negative**, mirroring the US result that the breakout system loses after costs. (2008-2009 produced no trades: breakouts don't fire in a crash — a sensible outcome, not a bug.)
- **Midterm (fundamentals-gated) can't be backtested on Saudi**: the Kaggle data has OHLCV + sector but no fundamentals, and there's no Saudi point-in-time fundamentals source → the quality/GP/asset-growth gates would empty it (same failure mode as the US pre-2011 fundamentals gap). A Saudi midterm backtest needs SAHMK/EODHD fundamentals history.
- Survivorship still ❌ (Kaggle has no delisted Saudi names — every symbol runs to 2020-04).

**Takeaway:** the Saudi expansion is proven end-to-end for **live screening** (yfinance `.SR`) and for **price-only backtests** (Kaggle history). The gaps to "real" are: Saudi fundamentals history (for the midterm backtest), a real compliance source, a market-aware calendar, and the SAR-aware UI.

## SAHMK free-tier finding (verified 2026-06-11, key used process-locally, not stored)
- Base `https://app.sahmk.sa/api/v1`, header `X-API-Key`.
- **Free tier (100 req/day): `/quote/{symbol}/` + `/market/summary/` ONLY.** `/quote` works well (price, OHLC, volume, inflow/outflow, 15-min delayed).
- **`/financials/{symbol}/` and `/historical/{symbol}/` are paywalled** → 403 `PLAN_LIMIT`: requires **Starter ($149/mo, 5,000/day)**. This is a *tier* block, not the request cap.
- **Implication:** the free SAHMK key does NOT provide Saudi fundamentals or history. For the midterm Saudi backtest, the realistic paths remain: SAHMK **Starter $149/mo**, **EODHD** (~$20–80/mo, cheaper), or an **operator-supplied Argaam/CSV fundamentals export** (free, manual, must include filing dates for point-in-time).
- For the **live Saudi screen**, yfinance `.SR` (free, uncapped, includes a current fundamentals snapshot) is better than SAHMK free for our needs; SAHMK `/quote` only adds value as a *licensed* live-price source if the app is ever hosted/public.

## FMP free-tier finding (verified 2026-06-11, key used process-locally, not stored)
- New keys must use the `/stable/` API (the `/api/v3/` legacy endpoints are deprecated). Auth = `?apikey=`.
- **US financial statements work** (AAPL income statement returns full data with `filingDate`/`period`).
- **Saudi `profile` works** (`2222.SR` → price, market cap, currency SAR, exchange `SAU`, industry, ISIN).
- **Saudi financial STATEMENTS are paywalled**: `income-statement?symbol=2222.SR` → *"Special Endpoint … not available under your current subscription"*. International fundamentals need a paid FMP tier (typically Premium ~$50/mo).
- **Implication:** FMP free does NOT unlock the Saudi midterm backtest either. Net: among the free tiers tried, **only yfinance `.SR` provides Saudi fundamentals (current snapshot)** — good enough for the live screen, but no source tried gives free *point-in-time* Saudi statements for a backtest. Paths to a Saudi midterm backtest remain: FMP Premium (~$50/mo), EODHD (~$20–80/mo), SAHMK Starter ($149/mo), or a free operator/Argaam CSV export (must include filing dates).
