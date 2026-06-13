# Research: US Stock Screener MVP

**Feature**: 001-screener-mvp
**Date**: 2026-06-10
**Purpose**: Resolve technical unknowns from the Technical Context and record the rationale for each decision so the plan and tasks can proceed deterministically.

The Technical Context in `plan.md` has no `NEEDS CLARIFICATION` markers — every decision was made with a documented rationale below. This file records *why* each choice was made and what alternatives were rejected.

---

## Decision 1: Backend language and framework — Python 3.12 + FastAPI

**Rationale**:
- The screening engine, indicator math, and backtest harness are heavily numerical; Python's pandas / numpy / pyarrow stack is the de-facto choice and aligns with the user's existing Python expertise (per CLAUDE.md memory: Python 3.12.10).
- FastAPI gives typed Pydantic v2 request/response models that double as the contract schema (single source of truth between the OpenAPI doc and the runtime).
- Async-friendly for parallel data fetches (multiple vendor calls during the daily ingest job).
- Mature ecosystem for finance: `pandas-ta` and `talipp` provide reference indicator implementations to test our golden fixtures against (defense in depth for Constitution IV).

**Alternatives considered**:
- **Node.js / TypeScript backend**: Would unify frontend/backend languages, but indicator and backtest tooling in the JS ecosystem is far less mature (and less peer-reviewed) than Python's — direct conflict with Constitution II.
- **Go**: Excellent runtime, but the indicator / pandas equivalent (gota, dataframe-go) is immature; ramp-up cost not justified.
- **Rust**: Best determinism story but slow indicator library development — premature optimization for v1.

---

## Decision 2: Frontend framework — Next.js 15 (App Router) + TypeScript + Tailwind

**Rationale**:
- Spec requires a fast home dashboard (SC-015: ≤ 1 s) including a regime indicator + events panel; Next.js SSR + React Server Components render the dashboard's mostly-static portions on the server, keeping cold-start latency low.
- TypeScript end-to-end (frontend + Zod-validated API client) catches contract drift at build time, supporting Constitution III's determinism gate.
- Tailwind enables a centralized copy/style audit — a single `frontend/src/lib/copy.ts` module aggregates all UI strings, which a CI grep checks for forbidden directive words ("Buy", "Sell", "Recommended") per Constitution V.
- `localStorage` persistence (per spec assumption + Muhallib precedent) is native to the browser; no extra library needed.

**Alternatives considered**:
- **SvelteKit**: Smaller bundle, but smaller ecosystem for the financial-chart libraries (Recharts, visx) we want; reviewer pool smaller.
- **Vite + React SPA**: Lighter, but loses SSR cold-start benefit on the dashboard.
- **Vanilla HTML/JS**: Matches Muhallib v1's simplicity, but the spec's 6 user stories + portfolio + watchlist + candidate detail exceed what vanilla scales to maintainably.

---

## Decision 3: Persistence model — server: SQLite + Parquet; client: `localStorage`

**Decision**:
- Server-side: SQLite (via SQLAlchemy Core) for catalog/reference data — tickers, sector taxonomy, Shariah source rows, event calendars, screen-result snapshots. Parquet (pyarrow) for OHLCV time series, partitioned by year.
- Client-side: browser `localStorage` for the user's portfolio holdings, watchlist entries, and user settings (caps, Shariah toggle, default strategy, exclude-earnings filter).

**Rationale**:
- SQLite is zero-ops, file-based, easy to ship in a Docker image, and supports the catalog/reference query patterns (point-in-time as-of joins, sector roll-ups).
- Parquet is the standard for columnar OHLCV; queries by ticker × date range are 10-100× faster than row-oriented for screening workloads.
- `localStorage` for user state matches the spec's "single-user, no-auth, browser-local" assumption (FR-019, FR-020) and the Muhallib v1 precedent recorded in CLAUDE.md memory. No server-side user accounts means no PII storage — directly satisfies Constitution V's PII rule.
- Manual export/import (FR-019) is implemented by serializing the `localStorage` blob to a single JSON file.

**Alternatives considered**:
- **Postgres**: Overkill for single-user; adds container + ops complexity.
- **DuckDB**: Strong alternative for the analytics path; deferred to a possible v2 if Parquet queries become a bottleneck.
- **Server-side user accounts**: Out of scope per spec; would re-open the auth/PII surface area Constitution V deliberately keeps closed.

---

## Decision 4: Price data sources (v1, personal-use scope) — `yfinance` + `Stooq` behind a `PriceProvider` interface

**Decision**: Two complementary free sources, both behind a `PriceProvider` interface in `backend/src/data/prices.py`:

1. **`yfinance`** — daily refresh for current and recent EOD OHLCV across the active universe.
2. **`Stooq`** — one-time bulk download (~50 MB compressed CSV at `https://stooq.com/db/d/?b=d_us_txt`), refreshed quarterly, used as the deep-history source for backtests including most US delisted tickers. Without delisted tickers, backtests silently survivor-bias their results (Constitution III, NON-NEGOTIABLE).

**Personal-use scope resolves the redistribution caveat** flagged in earlier drafts: this v1 is operated by one user on their own machine and never re-serves vendor data. yfinance's no-redistribution TOS does not apply at this scale. The interface still isolates the source so a future hosted/multi-user deployment can swap in a licensed feed without code changes elsewhere.

**Rationale**:
- Free, no API key required for either source — zero ongoing cost for personal use.
- yfinance gives convenient current EOD + earnings calendar fields; Stooq gives the deep history + delisted coverage that yfinance lacks.
- The `PriceProvider` interface keeps the rest of the codebase indifferent to which source served a particular row; the data layer stamps every row with its actual source (`yfinance` or `stooq`).

**Optional paid upgrade (one item, not committed in v1)**: If/when a strategy's backtest results depend materially on Stooq's delisted coverage (e.g., changing the source changes a metric by more than the documented tolerance), upgrade that strategy's backtest to **EOD Historical Data** ($19.99/mo, 30+ years, broad delisted coverage). Decision criteria are recorded in each backtest's `bias_check.md`. Personal-use scope keeps this as a per-strategy quality decision, not a v1 launch blocker.

**Rejected alternatives for personal-use v1**:
- **Polygon.io ($29-99/mo)**: Excellent quality but overkill for one user; EOD Historical Data covers the same need at a third of the price.
- **Norgate Data ($30-50/mo)**: Gold standard for retail backtesting (survivor-bias-free with point-in-time index membership) but unnecessary unless backtest fidelity becomes the bottleneck. Re-evaluate at v1.x if Stooq + EOD HD prove insufficient.
- **Tiingo (free tier)**: Viable but capped at 500 requests/day, which strains the daily ingest at full universe size; kept as an emergency fallback.
- **Alpha Vantage (free tier)**: 25 requests/day cap is too restrictive for a daily universe pull.

**Refresh cadence**:
- yfinance: daily, post-US-market-close, by `scripts/ingest_daily.py`. Stamps `source=yfinance`, `source_as_of=<UTC fetch time>`.
- Stooq: quarterly, by `scripts/refresh_stooq_history.py`. Stamps `source=stooq`, `source_as_of=<bundle date>`. Manual trigger acceptable for personal use.

---

## Decision 5: Fundamentals source — SEC EDGAR (XBRL company facts API)

**Rationale**:
- Free, authoritative, publicly redistributable (US government data, public domain). Direct alignment with Constitution I.
- Provides quarterly (10-Q) and annual (10-K) filings with structured XBRL data — sufficient for CAN SLIM-style growth screens (earnings growth, ROE) and Piotroski-style value screens (if added later).
- Lag: filings published 35-90 days after period end. Acceptable for mid-term strategies; not a constraint for short-term price-action strategies.

**Implementation**: `sec-edgar-downloader` package for the index + filing fetch; XBRL parsing via `sec-cik-mapper` + a custom XBRL → normalized facts mapper. Cached to SQLite, stamped with `source=sec_edgar`, `source_as_of=<filing_received_date>`.

**Alternatives considered**:
- **Financial Modeling Prep / SimFin / Stockanalysis APIs**: Better ergonomics but paid and non-authoritative.
- **Yahoo Finance fundamentals via `yfinance`**: Convenient but lower fidelity (mixed TTM / GAAP / non-GAAP) and redistribution-restricted.

---

## Decision 6: Sector classification — SIC code → coarse 11-sector taxonomy

**Decision**: Map SEC EDGAR's SIC codes (provided on the company submissions feed) to an 11-sector taxonomy aligned with the widely-used MSCI/S&P sector buckets (Energy, Materials, Industrials, Consumer Discretionary, Consumer Staples, Health Care, Financials, Information Technology, Communication Services, Utilities, Real Estate).

**Rationale**:
- SIC codes are public and ship with every EDGAR filing — no separate license needed.
- An 11-sector bucket is the standard granularity for retail diversification advice (matches the 25%-per-sector cap default).
- Avoids GICS licensing fees ($$$) and a third-party dependency.

**Trade-off**: Some tickers' SIC codes are stale or coarse. We accept "Unclassified" as a valid bucket (per spec edge-case) and surface a count on the dashboard so users can manually correct via a small in-app override table.

**Alternatives considered**:
- **GICS**: Industry standard but proprietary; license cost not justified for v1.
- **Yahoo Finance sector tags**: Convenient but inconsistent over time (companies get reclassified silently).

---

## Decision 7: Indicator library — implement-and-fixture-test, cross-checked against `pandas-ta` / `talipp`

**Decision**: Implement RSI, SMA, EMA, ATR, MACD, ROC, 52-week-high, and Bollinger Bands as pure functions in `backend/src/indicators/`. For each indicator, ship a golden-fixture test (`tests/indicators/test_<name>.py`) with hand-calculated or vendor-published values. Cross-check our outputs against `pandas-ta` (or `talipp`) on a fixed input series in a separate cross-check test — they should agree within a documented tolerance.

**Rationale**:
- Constitution IV mandates fixture-anchored tests. A second independent implementation (the cross-check) is an additional safety net against silent drift.
- Pure functions, no hidden state, no random seeds → directly serves Constitution III.

**Alternatives considered**:
- **Use `pandas-ta` directly as the production path**: Faster to ship but couples us to that library's quirks; harder to enforce determinism if the library updates.
- **TA-Lib (C library)**: Best performance but a binary dependency that complicates Windows installs (a known pain in the user's environment per CLAUDE.md).

---

## Decision 8: Strategy slate for v1 launch — three fully-gated strategies (quality-first)

**Decision (revised)**: v1 ships **three** strategies, each fully gated against its known failure modes. A name-only "lite" version of a multi-signal methodology MUST NOT ship under the original author's citation.

| Strategy slug | Timeframe | Core methodology + citation | Modifications shipped in v1 (each separately cited) |
|---|---|---|---|
| `midterm_52w_high_momentum` | Mid-term | 52-week-high momentum: rank by 12-1 month return; long top decile within 5% of 52w high — *George & Hwang (2004), "The 52-Week High and Momentum Investing", Journal of Finance.* | (a) Risk-managed volatility scaling per *Barroso & Santa-Clara (2015), "Momentum has its moments", Journal of Financial Economics* — position weight ∝ 1 / strategy's trailing 6-month realized vol. (b) Sector-relative ranking with a 30% cap per sector on the result list — reduces sector-concentration failure mode. (c) Quality screen — exclude debt/equity > 1.5 OR negative trailing-4Q free cash flow — per *Asness, Frazzini, Pedersen (2019), "Quality Minus Junk", Review of Accounting Studies.* |
| `shortterm_minervini_vcp` | Short-term | Stage-2 Volatility Contraction Pattern — *Mark Minervini, Trade Like a Stock Market Wizard (2013).* | (a) ADR-ratio test for the contraction: `recent_4w_ADR / prior_4w_ADR < 0.7` — quantifies the otherwise-subjective "tightening" rule. (b) Volume confirmation on breakout: breakout-day volume > 1.5 × 50-day average — present in Minervini's original but easy to omit. (c) Earnings exclusion: skip candidates with earnings in the next 7 days (already wired via US4 default). |
| `shortterm_atr_breakout` | Short-term | ATR-based volatility breakout, initial stop = entry - 1.5 × ATR — *Wilder (1978), New Concepts in Technical Trading Systems*; popularized by the Turtle Trading rules (Dennis / Eckhardt, 1980s). | (a) Trend-of-trend filter (default ON): require close > 200-day SMA and 200d SMA rising — removes ~70% of false breakouts in backtests; user-configurable parameter `require_above_sma200`. (b) Chandelier Exit trailing stop after initial stop is moved to break-even: `stop = highest_close_since_entry - 3 × ATR` — *Chuck LeBeau, popularized in Le Beau & Lucas, "Computer Analysis of the Futures Markets" (1992).* (c) Liquidity gate (handled at the universe level — see Decision 14). |

All three are enabled by default at v1 launch — but only after each passes its walk-forward backtest meeting Decision 15's window requirement (≥ 15 years including 2008-2009). Strategies that fail the window requirement ship as "Available but disabled by default" with a visible "Limited backtest window" warning.

**Why three and not four — CAN SLIM is intentionally deferred**: The earlier `midterm_can_slim_lite` plan dropped the N (new product/management), I (institutional sponsorship), and L (leadership / RS rank against industry) signals — three of the seven CAN SLIM letters. Shipping a four-signal subset under O'Neil's name fails Constitution II's "rules in code match the cited methodology" review gate. CAN SLIM returns in v1.x once we have:

- Form 4 insider-buying ingest from EDGAR (free, already available).
- Analyst-revision data (paid — re-evaluate then).
- A soft valuation guard (P/E or P/S vs sector median) to address CAN SLIM's known bubble-exposure.

**Why these three are defensible**:
- Two factor families covered: pure momentum (52w-high, ATR breakout) and trend-confirmed pattern (Minervini VCP). Low signal correlation.
- Both timeframes covered (one mid-term, two short-term).
- Each modification carries its own peer-reviewed citation, so a reviewer reading the strategy's "Strategy gates" panel (FR-037) can audit every line.
- The shipped gates address each strategy's biggest published failure mode: momentum crashes (vol scaling), pattern fuzziness (ADR ratio), and breakout whipsaw (trend-of-trend filter).

**Rejected (for v1)**:
- **CAN SLIM Lite under O'Neil citation**: see above.
- **Sector momentum / industry rotation**: depends on a robust sector classification we have (SIC) but adds a strategy whose backtest needs sector-history reconstruction; deferred.
- **Earnings-revision momentum**: requires paid analyst data.
- **Value-style screens (Piotroski F-Score, Magic Formula)**: long-term horizon, constitutionally out of scope for v1.

---

## Decision 9: Shariah-compliance source (v1) — composite: SPUS (default external) + user-managed inclusion / exclusion lists

**Decision**: The Shariah compliance lookup in v1 is a **composite** of one or more external sources (SPUS by default) and two user-managed lists held client-side.

```
is_compliant(ticker) ⇔
    (ticker ∈ active_external_sources  OR  ticker ∈ user_inclusion_list)
    AND
    (ticker ∉ user_exclusion_list)
```

**The external source (default: SPUS)**: pulled from the Wahed SPUS ETF holdings page, normalized to `{ ticker, source_name: "spus_holdings", source_as_of, source_url }`, cached in SQLite. The `ShariahSource` abstraction also accommodates HLAL (Wahed Dow Jones Islamic Market US ETF) and other Shariah-screened ETFs as alternate or supplementary external sources.

**Why SPUS alone is not sufficient**: SPUS tracks the **FTSE USA Shariah index** — a Shariah-screen applied to FTSE USA (a large/mid-cap US universe). By construction it excludes:

- US-listed small-caps and micro-caps that may pass the same Shariah ratio tests but are below FTSE USA's market-cap cutoff.
- Recent IPOs that have not yet been reviewed for index inclusion.
- Compliant tickers that Wahed has chosen not to include for index-construction reasons unrelated to compliance.

This is a real product issue: a Muslim investor who has personally vetted a non-SPUS ticker (say, a small-cap industrial passing AAOIFI ratio tests, or a recent IPO) should not be silently filtered out just because SPUS hasn't added it.

**User-managed lists** address this without re-implementing fiqh in code:

- **User inclusion list**: per-ticker entries with `{ ticker, added_at, rationale_note (free text, optional, e.g. a URL to a Shariah-board review the user trusts) }`. Treated as compliant in addition to the active external source(s).
- **User exclusion list**: per-ticker entries the user personally rejects even when SPUS includes them, with `{ ticker, added_at, note }`. Treated as non-compliant even if external sources include them.

**Precedence rules**: exclusion always wins (the user has explicitly said "not for me"). For display: when a ticker is compliant via both User and an external source, the badge shows the more-authoritative external source (e.g., "SPUS") for cleanliness; the user's rationale note is preserved in case the user later removes the external source.

**The app makes no Shariah judgment**: it composes lists. SPUS-listed → delegates to Wahed's Shariah board (a credentialed authority). User-listed → the user is doing their own due diligence, and the badge plainly labels the source as "User" so the provenance distinction is always visible. The product never claims a user-added ticker is compliant in any authoritative sense.

**Where the lists live (no-auth scope)**: both user lists live in browser `localStorage` (like portfolio/watchlist/settings). On every screen-run request the client passes them along with the run parameters; the server is stateless on user state. Both lists are part of the existing settings/portfolio export bundle (FR-019, FR-041).

**Filter still defaults OFF**: per spec assumption, the global Shariah toggle is off by default so non-Muslim users see zero Shariah UI. Turning it on activates the composite lookup.

**Why composite over multi-mode (e.g. strict vs. info-only)**: a "show all candidates, just tag them" mode (info-only) is a different feature — it's about presentation rather than universe membership. v1 keeps a single semantic ("filter ON → restrict universe") with the composite lookup; info-only mode is deferred to a v1.x consideration if the operator wants it.

**Rejected alternatives**:
- **SPUS alone**: rejected — too restrictive (FTSE USA Shariah membership only).
- **User list alone, no external default**: rejected — every new user would face a cold-start setup burden and no curated baseline.
- **Per-ticker financial-ratio screen (AAOIFI rules) implemented in code**: deferred to a future spec. Requires per-ticker quarterly data (we have via EDGAR), but it also requires a credentialed Shariah scholar to fix thresholds and edge cases — not an engineering decision.
- **Server-side user-managed lists**: rejected — would require user accounts, contradicting the v1 single-user, no-auth deployment model.

**Known v1 limitation**: SPUS membership is an indirect signal that lags issuer-level events by a few days; user lists are entirely user-curated and the product cannot verify them. Both limitations are made transparent through visible source labels and as-of dates on every badge.

---

## Decision 10: Events sources — SEC EDGAR (8-K), public earnings calendar, official US economic calendars

**Decision**: Three distinct sources behind a unified `EventsService`:

1. **8-K filings (per-ticker material news)**: SEC EDGAR. Free, authoritative, redistributable. Pulled daily via `scripts/ingest_daily.py`, normalized to `TickerEvent(type="8K", ticker, filed_at, source_url, ...)`.
2. **Earnings calendar (per-ticker next earnings date)**: For v1 prototype, `yfinance`'s `Ticker.calendar` field, cached daily, behind an `EarningsCalendarProvider` interface. Production: paid vendor swap-in. Stale beyond 3 trading days → "Stale events data" warning per FR-032.
3. **Economic calendar (FOMC, CPI, NFP, PCE, PPI)**: Maintained as a curated YAML/JSON file `backend/data/econ_calendar.yaml` seeded from the Federal Reserve's FOMC schedule, BLS's CPI/NFP/PPI release calendar, and BEA's PCE schedule. Each entry carries source URL + as-of date. Updated weekly by `scripts/ingest_daily.py` (or manually for the first ship).

**Rationale**:
- EDGAR is the gold standard for 8-K material news — direct from issuers, no aggregator in the loop.
- Earnings calendars are notoriously heterogeneous across vendors; using `yfinance` for v1 is a pragmatic prototype; the interface keeps swap-out simple.
- Economic calendar is small and slow-moving; a curated file removes a brittle third-party scraping dependency for the first ship.

**Alternatives considered**:
- **News aggregator (NewsAPI, Benzinga)**: Out of scope; v1 only links out and counts 8-Ks, no full-text sentiment.
- **Trading Economics / ForexFactory scraping**: Brittle and TOS-questionable; deferred.
- **Per-vendor earnings calendar (Polygon, FMP)**: Adopt when budget is committed.

---

## Decision 11: Market regime calculator — SPY 200-day SMA + breadth (% S&P 500 stocks > 200-day SMA)

**Decision**: The market regime is computed as a deterministic rule on end-of-day SPY data plus an S&P 500 breadth indicator:

- **Trending up**: SPY close > 200-day SMA AND breadth (% S&P 500 constituents > their 200-day SMA) > 60%.
- **Range-bound**: One condition is true, the other is false, OR breadth is between 40% and 60%.
- **Trending down**: SPY close < 200-day SMA AND breadth < 40%.

Each strategy carries a `REGIME_FAVORABILITY` map: e.g., `midterm_52w_high_momentum` is Favorable in Trending up, Neutral in Range-bound, Unfavorable in Trending down.

**Rationale**:
- 200-day SMA is the canonical long-term trend filter (widely cited in Stan Weinstein's stage analysis, Paul Tudor Jones interviews, IBD).
- Breadth confirms whether the trend is broad (many participants) or narrow (a few mega-caps masking weakness underneath).
- Both inputs are deterministic functions of end-of-day data → satisfies Constitution III.

**Alternatives considered**:
- **VIX-based regime (calm vs. stressed)**: Useful but orthogonal; deferred to a possible "volatility regime" overlay in v2.
- **Ned Davis composite (multiple inputs)**: Stronger but adds 5+ inputs and a non-trivial weight tuning that would need its own backtest.

---

## Decision 12: Testing strategy — pytest + hypothesis (backend), Vitest + Playwright (frontend)

**Decision**:
- Backend unit/integration: `pytest`. Property-based for indicator math: `hypothesis` (e.g., RSI of a constant series is 50 ± epsilon; SMA of N copies of x is x).
- Backend contract: schema tests against `contracts/openapi.yaml` using `schemathesis`.
- Frontend unit: `vitest` + `@testing-library/react`.
- Frontend end-to-end: `playwright` against a running backend + frontend dev pair, including a "no directive copy" lint that grep-checks rendered pages for "Buy", "Sell", "Recommended" (Constitution V).

**Rationale**: Tests-first for financial logic is non-negotiable per Constitution IV; the hypothesis layer catches the silent drift case the constitution warns about. Playwright is the only way to validate the disclaimer / as-of-badge invariant across every page (SC-005).

---

## Decision 13: Daily ingest pipeline — single Python script, idempotent, cron-driven

**Decision**: `scripts/ingest_daily.py` runs once per US trading day post-market-close. It:

1. Fetches updated OHLCV for the universe via `PriceProvider`.
2. Pulls new 8-K filings from EDGAR (since the last successful run).
3. Refreshes the earnings calendar for the next 30 days.
4. Refreshes SPUS holdings.
5. Re-runs the daily ingest manifest, recording per-source success/failure + as-of stamps in `data/manifest.json`.

Idempotent: re-running on the same day is a no-op for already-fetched data. Failures in any single source are isolated — the screen still runs on partial data, with a per-source "Stale" warning.

**Rationale**: One job, one log, one failure surface. Aligns with the "single-user local app" deployment story: a user can run `python scripts/ingest_daily.py` manually if they skipped a day.

---

## Decision 14: Universe-wide liquidity gate — applied before any strategy runs

**Decision**: A universe-wide liquidity gate filters the screenable universe to tickers with trailing-20-day average daily dollar volume ≥ $1,000,000 AND share price ≥ $5.00. Both thresholds are user-configurable in Settings. The gate is applied at the universe loader, not per strategy — every strategy automatically benefits and reviewers do not need to verify it per-strategy.

**Rationale**:
- **Eliminates microcap pump candidates** that disproportionately trigger breakout-style strategies (ATR breakout in particular). The retail-quant literature (e.g., the "below $5" rule used by IBD, the $1M ADV minimum used by most institutional momentum desks) is unanimous that this single filter raises strategy quality more than almost any per-strategy tweak.
- **Resolves a known failure mode of the ATR Breakout strategy**: without a liquidity floor, the strategy fires constantly on small-cap noise and the user's experience is dominated by false signals.
- **Tickers excluded by the gate stay in the user's portfolio** (per FR edge case): they continue to count for sector exposure and concentration flags, just labeled "Excluded by liquidity gate".

**Implementation**: a single `liquidity_gate(ohlcv_df)` function in `backend/src/data/universe.py`, applied after the universe load and before any strategy sees the data. The thresholds live in `UserSettings` and default to `(1_000_000, 5.00)`.

**Rejected alternatives**:
- **Per-strategy liquidity rules**: would let an individual strategy lower its bar; uniform floor is simpler and harder to abuse.
- **Hard-coded thresholds**: gives the user no escape if they specifically want to research micro-caps; user-configurable is the right call.

---

## Decision 15: Backtest window — ≥ 15 years including 2008-2009

**Decision**: Every strategy enabled by default at v1 launch is backtested across a window of at least 15 years that *explicitly includes* the 2008-2009 drawdown. The Stooq deep-history bundle is the v1 data source for this window; EOD Historical Data is the optional paid upgrade per Decision 4 if Stooq's coverage proves insufficient for a particular strategy.

**Rationale**:
- A backtest window of 2014-2024 (the earlier default) is dominated by a tech-megacap bull market following massive central-bank stimulus. Strategies tuned to that period will fail in mean-reverting / value-led regimes — directly violating "reliable trusted strategies" as the project goal.
- Including 2008-2009 surfaces the actual drawdown shape of each strategy. Users care more about "how bad does this get?" than "what's the headline Sharpe?".
- 15 years is the minimum window that contains at least one bear market and one full recovery; longer is better and the loader will use everything Stooq provides for each ticker.

**Operational gate**: A strategy that cannot be backtested across this window (because data is missing for its key tickers) ships as "Available but disabled by default", with a visible "Limited backtest window" warning naming the actual window covered. Constitution III's bias-check checklist explicitly asks the reviewer to confirm the window meets this rule before promoting a strategy to enabled-by-default.

**Rejected alternatives**:
- **2014-2024 default**: rejected — not reliable evidence of strategy quality.
- **Mandatory full history from inception of each ticker**: impractical and pointless for tickers IPO'd after the test window's start.

---

## Decision 16: Walk-forward backtest metrics displayed to the user

**Decision**: Each shipped strategy's detail page in the frontend displays walk-forward backtest metrics — per-calendar-year hit rate, average win, average loss, max drawdown, total return, turnover, and the data window used. The metrics come from the per-strategy backtest artifacts under `backend/backtests/<strategy>/<snapshot_id>/` (which Constitution III already requires), exposed through a new `GET /strategies/{slug}/backtest` endpoint. The "Strategy gates" panel (FR-037) lists every rule and modification applied with its own citation.

**Rationale**:
- Users currently have only a citation as evidence of "reliable" — that's not enough. Per-year metrics turn the backtest from a developer artifact into user-visible proof.
- Honest performance display (including the bad years) sets correct expectations. Without it, the first stretch of underperformance — which is *guaranteed* for momentum strategies — generates "this product is broken" complaints.
- The metrics are deterministic functions of the backtest snapshot, so the display itself does not need its own backtest discipline; reproducibility is inherited from Constitution III.

**Implementation**:
- A new `backend/src/backtests/metrics.py` module computes per-year metrics from each strategy's stored backtest results.
- A new endpoint `GET /strategies/{slug}/backtest` returns the metrics + the data window + source name and as-of dates.
- A `StrategyDetailPage` in the frontend renders the panel under the "Strategy gates" panel.

**Rejected alternatives**:
- **Hide backtest results from users**: was the v1 default; rejected because it makes "reliable trusted strategies" unsubstantiated marketing.
- **Show only headline metrics (Sharpe, total return)**: cherry-picks; rejected.
- **Interactive in-app backtester**: out of scope for v1 (deferred to v2); the static metrics view is the right scope.

---

## Open Questions Deferred to v2

These are explicitly out of scope for v1 and are recorded here so they do not silently re-emerge:

- News sentiment / NLP classification of 8-K items.
- In-app interactive backtesting UI (backtests exist developer-side per Constitution III but are not user-facing).
- Multi-user accounts, cloud portfolio sync, sharing watchlists.
- Brokerage integration / order placement.
- Intraday quoting and intraday strategies.
- Stricter Shariah financial-ratio screening (per-ticker debt and interest-income tests).
- Long-term buy-and-hold strategies (constitutionally deferred until amendment).
- Non-US markets.
