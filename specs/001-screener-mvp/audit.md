---
description: "Remediation audit of Phases 1-3 (T001-T060) - US Stock Screener MVP"
audited: 2026-06-10
remediated_by: Codex
scope: "Phase 1 (Setup), Phase 2 (Foundational), Phase 3 (US1)"
status: "Partially remediated; US1 runs on real data, but the backtest is not constitution-grade yet"
---

# Implementation Audit - Remediation Update

## Update 2026-06-11 - Phase N and Phase 10 implemented

**Scope implemented**

- Implemented Phase 10 data caching and warm-keeper behavior.
  - `backend/src/data/prices_store.py` now upserts affected year partitions instead of deleting all rows in a year partition for unrelated tickers.
  - Added `load_last_dates()` and tests proving duplicate/newer rows win while cross-ticker rows survive.
  - `backend/src/data/prices.py` now performs incremental yfinance fetches by local last bar date, skips warm tickers, batches `yf.download`, and retries with backoff.
  - `backend/src/data/profiles.py` adds a SQLite `ticker_profile_cache` with 7-day TTL for name, sector, FCF, debt/equity, gross profit, assets, and GP/assets.
  - Live quality metrics now prefer the local EDGAR cache through `quality_metrics_as_of` when available; yfinance remains a fallback for missing EDGAR/name/sector data.
  - `scripts/ingest_daily.py` is now the warm-keeper: it updates price/profile caches, writes manifest `last_bar_date_by_ticker`, and warms broad strategy snapshots.
- Implemented broad local Stooq screening for normal non-Shariah screen runs when `backend/data/prices/stooq_parquet/` exists.
  - The previous 20-ticker yfinance default remains only as a fallback when the Stooq archive is absent or when an explicit ticker list is supplied.
  - Optimized Stooq reads with date filters and a vectorized liquidity gate.
  - Added a disk-backed computed snapshot cache in `backend/data/cache/snapshots/`, so a restarted app loads the broad market snapshot from local computed data.
- Implemented `/meta` data freshness surface.
  - `/meta` now derives price source `source_as_of` from `last_bar_date_by_ticker` when present.
  - Price staleness uses the app's conservative latest-completed-trading-day rule to avoid false stale warnings before the next EOD bar is considered complete.
  - Added `frontend/src/components/DataFreshnessPanel.tsx` to show "Prices as of <date>" plus Fresh/Stale status on the home dashboard.
- Implemented Phase N audit tests.
  - Schemathesis contract validation in `backend/tests/contract/test_openapi.py` exercises every OpenAPI endpoint with generated cases and validates responses.
  - Perf budget tests in `backend/tests/integration/test_perf.py` cover broad screen cold-from-disk/warm runs, candidate detail, and home dashboard endpoints.
  - Liquidity gate audit in `backend/tests/integration/test_liquidity_gate.py`.
  - Backtest-window floor audit in `backend/tests/integration/test_backtest_window_floor.py`.
  - Strategy determinism audit in `backend/tests/integration/test_determinism.py`.
  - Frontend strategy-page audit in `frontend/tests/e2e/strategy-page-audit.spec.ts`.
- Updated documentation and coverage.
  - Added top-level `README.md`.
  - Corrected `specs/001-screener-mvp/quickstart.md` for npm, the actual uvicorn app path, Stooq survivorship caveat, warm-keeper behavior, and validation commands.
  - Added `specs/001-screener-mvp/coverage.md` mapping every FR-001 through FR-041 and every SC-001 through SC-018/SC-012a/SC-012b to tasks/tests.

**Validation**

Commands run successfully:

```powershell
py -3.12 scripts\ingest_daily.py --skip-shariah --skip-events
py -3.12 -m pytest backend\tests -q
npm.cmd run lint
npm.cmd run build
npx.cmd playwright test
```

Results:

- Warm-keeper: fetched `0` new yfinance OHLCV rows, refreshed the manifest, and warmed all three broad strategy snapshots.
- Backend tests: `78 passed`.
- Frontend lint: PASS.
- Frontend production build: PASS.
- Playwright: `19 passed`.

Measured performance evidence:

- Broad Stooq mid-term screen first computed build after optimization: about `10.1s` before disk cache existed.
- Fresh Python process after disk snapshot warm: about `0.74s`.
- In-process repeated broad screen runs: about `0.02s`.
- Candidate detail now resolves from broad cached strategy outputs instead of a one-ticker yfinance fetch, avoiding yfinance-only failures on Stooq candidates.

**Remaining honest caveats**

- Only `midterm_52w_high_momentum` is currently `enabled_by_default=true`; the two short-term strategies have valid 2008-2024 windows but remain disabled by the registry because their bias checks still report survivorship failure on the free Stooq bundle.
- The broad screen is now real local Stooq breadth, but the free Stooq archive is still survivor-only per the previous audit. Survivor-bias-free backtests still require T049b or another delisted-inclusive data source.
- Phase 10 materially reduces yfinance dependence, but explicit ticker runs and missing profile/name/sector fallbacks can still call yfinance.
- The Schemathesis tests pass but emit a warning that `.example()` is normally intended for exploration; the cases are pinned to valid live slugs/bodies and still validate every response against the contract.

## Update 2026-06-11 - Phase 8 / US6 market regime implemented

**Scope implemented**

- Implemented regime response models in `backend/src/models/regime.py`.
  - Response includes `regime`, `rule_summary`, frozen `inputs`, `as_of_date`, per-strategy favorability, `data_as_of`, and disclaimer.
- Implemented S&P 500 breadth in `backend/src/regime/breadth.py`.
  - Real constituent source: official State Street SPY daily holdings XLSX at `https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx`.
  - Real price source: yfinance EOD closes for constituent 200-day SMA checks.
  - The constituent and breadth snapshots are cached in `backend/data/regime/` so returning dashboard loads are fast and deterministic.
  - Invalid non-ticker identifiers from the holdings workbook are filtered out; the live refreshed source produced 503 official holding tickers.
- Implemented the regime calculator in `backend/src/regime/calculator.py`.
  - Applies research.md Decision 11:
    - Trending up: SPY above 200-day SMA and breadth above 60%.
    - Trending down: SPY below 200-day SMA and breadth below 40%.
    - Otherwise Range-bound.
  - Uses the existing SPY loader from the T108a master switch, including local Stooq fallback when yfinance is rate-limited.
- Implemented `GET /regime` in `backend/src/api/regime.py` and mounted it from `backend/src/api/app.py`.
  - Endpoint maps each strategy's `regime_favorability` to the current regime and returns labels/explanations.
- Updated `specs/001-screener-mvp/contracts/openapi.yaml` to include the richer frozen input fields and strategy names.

**Frontend implemented**

- Added `frontend/src/components/RegimePanel.tsx`.
  - Renders current regime, rule summary, SPY close, SPY 200-day SMA, breadth percent/counts, as-of date, and per-strategy favorability tags.
  - Includes loading and unavailable states without fabricating a regime.
- Extended `frontend/src/lib/api.ts` with `RegimeResponseSchema`.
- Wired the panel into the home dashboard in `frontend/src/app/page.tsx`.
- Added `frontend/tests/e2e/us6-regime.spec.ts`.
  - Verifies the regime panel renders.
  - Verifies all strategy favorability tags render.
  - Verifies the panel is deterministic across reloads.

**Validation**

Commands run successfully:

```powershell
py -3.12 -m pytest backend\tests -q
npm.cmd run lint
npm.cmd run build
npx.cmd playwright test
```

Results:

- Backend tests: `54 passed`
- Frontend lint: PASS
- Frontend production build: PASS
- Playwright: `18 passed`

Live regime smoke:

```text
Regime: Range-bound
Rule: SPY is above its 200-day SMA; 291/501 eligible S&P 500 constituents (58.1%) are above their 200-day SMA.
Inputs: SPY close 737.11, SPY SMA200 684.9398, 503 official SPY holding tickers, State Street holdings as of 09-Jun-2026.
```

**Remaining honest caveats**

- Breadth is calculated from SPY ETF holdings as the practical current S&P 500 constituent proxy. This is close to the intended S&P 500 breadth input, but it is technically ETF holdings rather than a licensed S&P Global constituent feed.
- yfinance still emits intermittent `HTTP Error 401` / crumb warnings during unrelated candidate/event calls. The regime calculator cached the breadth snapshot successfully and uses local Stooq fallback for SPY trend when yfinance SPY is unavailable.
- The first uncached breadth calculation can take tens of seconds because it fetches hundreds of constituent price histories. Returning dashboard loads use the local breadth cache.

## Update 2026-06-11 - Phase 7 / US5 portfolio and sizing implemented

**Scope implemented**

- Implemented backend portfolio exposure models in `backend/src/models/portfolio.py`.
  - Request holdings are explicit user/client inputs; no server-side user portfolio store was added.
  - Decimal money fields are kept as decimal/string-compatible values for API responses.
- Implemented sector exposure and concentration flags in `backend/src/portfolio/exposure.py`.
  - Computes total invested, cash, per-sector dollar value, percent of capital, sector cap flags, and individual position cap flags.
- Implemented deterministic whole-share sizing in `backend/src/portfolio/sizing.py`.
  - Uses the lower remaining room between per-position and per-sector caps.
  - Floors to whole shares.
  - Returns zero shares with "Cannot size without breaching cap" when one share would breach either cap.
- Implemented `POST /sizing` in `backend/src/api/sizing.py` and mounted it from `backend/src/api/app.py`.
  - Returns `200` for cap-respecting sizing.
  - Returns a structured `422` `SizingResponse` body for cap-breach cases so the frontend can still render the exact reason.

**Frontend implemented**

- Extended `frontend/src/lib/store.ts` to schema version 3.
  - Portfolio now tracks total capital, holdings, optional cash override, created/updated timestamps, local-storage warning acknowledgement, sector/current price/20-day-dollar-volume fields, watchlist, and settings.
  - Migration fills older holdings with `current_price = avg_cost` and `sector = "Unclassified"` when those fields are missing.
  - Store exports and imports one human-readable JSON bundle containing portfolio, watchlist, and settings.
- Rebuilt `frontend/src/app/portfolio/page.tsx`.
  - Supports add/edit/remove holdings.
  - Computes total value, cash, sector exposure bars, position/sector concentration flags, non-compliant/user-marked counts, Shariah badges, and liquidity-gate tags.
  - Shows the required first-save modal: "Holdings are stored locally on this device".
- Extended `frontend/src/app/settings/page.tsx`.
  - Adds Export JSON and Import JSON controls for the combined client-state bundle.
- Extended `frontend/src/app/candidate/[ticker]/page.tsx`.
  - Adds "Size this trade" per strategy match.
  - Sends current local portfolio and current cap settings to `/sizing`.
  - Renders suggested shares, dollar value, resulting position percent, resulting sector percent, caps respected, and reasoning for both success and cap-breach responses.

**Validation**

Commands run successfully:

```powershell
py -3.12 -m pytest backend\tests -q
npm.cmd run lint
npm.cmd run build
npx.cmd playwright test
```

Results:

- Backend tests: `50 passed`
- Frontend lint: PASS
- Frontend production build: PASS
- Playwright: `17 passed`

Focused US5 validation:

```text
npx.cmd playwright test us5-portfolio.spec.ts -> 4 passed
```

**Remaining honest caveats**

- Portfolio holdings are browser-local and manually entered. There is no broker sync, no account import, and no automatic holding-price refresh.
- Sector/current-price/20-day-dollar-volume for holdings are supplied by the user in the portfolio form. The app uses those values for exposure, liquidity tags, and sizing.
- Sizing is stateless and deterministic from the request body. Bad client input can produce bad sizing context, so the UI must keep the request visible and auditable.
- Full-US-market screening remains limited by the earlier full-universe/T017 gap; this phase does not change the screen universe.

## Update 2026-06-11 - Phase 6 / US4 event awareness implemented

**Scope implemented**

- Implemented real SEC EDGAR 8-K event ingestion in `backend/src/data/filings_8k.py`.
  - Real source: SEC submissions JSON at `https://data.sec.gov/submissions/CIK##########.json`.
  - CIK lookup uses the local seeded catalog first and falls back to SEC `company_tickers.json`.
  - The loader stores only recent Form 8-K filings in the configured rolling window and keeps SEC Archives filing URLs.
  - No news sentiment, social feed, or fabricated material-news provider was added.
- Implemented real earnings-calendar ingestion in `backend/src/data/earnings_calendar.py`.
  - Primary source: `yfinance.Ticker(...).calendar`, with support for the dict and DataFrame shapes observed from the live library.
  - Optional fallback: Finnhub earnings calendar only when `FINNHUB_API_KEY` is configured.
  - Unknown earnings dates stay unknown and do not exclude candidates.
- Implemented official macro-event calendar support in `backend/data/econ_calendar.yaml` and `backend/src/data/econ_calendar.py`.
  - Curated official published dates only: Federal Reserve FOMC through June 2027, BLS CPI/NFP/PPI through December 2026, and BEA PCE through December 2026.
  - Seeded 34 macro events into SQLite during validation.
  - No projected 2027 BLS or BEA dates were invented.
- Added `backend/src/models/events.py`, `backend/src/data/events_store.py`, and `backend/src/events/service.py`.
  - Events are cached in SQLite with source status rows and stale-source detection.
  - The service refreshes per-ticker earnings plus 8-K data and reads/seeds the curated macro calendar.
- Added real API routes in `backend/src/api/events.py` and mounted them from `backend/src/api/app.py`.
  - `GET /events/market?days_ahead=N`
  - `GET /events/ticker/{ticker}`
- Wired events into the screening engine in `backend/src/screening/engine.py`.
  - `exclude_earnings_within_days` is applied after strategy rules and before Shariah filtering.
  - Candidates with unknown earnings dates are retained.
  - Candidate results now carry `next_earnings_date`, `days_to_earnings`, `recent_8k_count_30d`, and `events_source_as_of`.
  - Event source warnings are propagated through `stale_sources`.
- Updated daily scripts.
  - `scripts/seed_universe.py` seeds the macro calendar unless `--skip-events` is passed.
  - `scripts/ingest_daily.py` refreshes ticker events and macro events unless `--skip-events` is passed.

**Frontend implemented**

- Added `frontend/src/components/EventsBadge.tsx`.
  - Candidate rows show earnings-in-N-days and recent 8-K material-news count badges when real event data is available.
- Added `frontend/src/components/MarketEventsPanel.tsx`.
  - Home dashboard shows official market events, sorted by date, with stale-source and unavailable states.
  - The panel uses a 60-day horizon from the home page so FOMC, CPI, NFP, PCE, and PPI categories are visible from the current date.
- Updated `frontend/src/lib/api.ts` with event schemas and candidate-detail event typing.
- Updated `frontend/src/components/CandidateRow.tsx`, `frontend/src/app/page.tsx`, `frontend/src/app/screen/[strategy]/page.tsx`, and `frontend/src/app/candidate/[ticker]/page.tsx`.
  - Strategy run controls now include "Exclude earnings within N days".
  - Candidate detail shows ticker events and source-linked filings where available.

**Validation**

Commands run successfully:

```powershell
py -3.12 -m pytest backend\tests -q
npm.cmd run lint
npm.cmd run build
npx.cmd playwright test
```

Results:

- Backend tests: `44 passed`
- Frontend lint: PASS
- Frontend production build: PASS
- Playwright: `13 passed`

Live smoke checks:

```text
/events/market?days_ahead=60 -> 8 official market events, source=econ_calendar_v1, stale=false
/events/ticker/UNH -> next_earnings_date=2026-07-28, days_to_earnings=47, recent_8k_count_30d=1
POST /strategies/shortterm_atr_breakout/run with exclude_earnings_within_days=90 -> candidate_count=0 during the smoke run
Frontend home http://127.0.0.1:3000/ -> HTTP 200
```

**Remaining honest caveats**

- During Playwright validation, yfinance emitted transient `HTTP Error 401: Invalid Crumb` warnings. The app handled the provider failure path without crashing, but yfinance availability is not guaranteed.
- Earnings dates are provider-dependent. If yfinance and Finnhub are unavailable or do not publish a date for a ticker, the app marks earnings as unknown and does not exclude that candidate.
- The macro calendar is curated from official published schedules and should be refreshed as the Fed, BLS, and BEA publish or revise dates.
- The app still does not screen the entire approximately 6,000-stock US market by default; that remains tied to the earlier full-universe/T017 gap.

## Update 2026-06-11 - Phase 5 / US3 Shariah filter implemented with multi-source options

**Scope implemented**

- Implemented a real Shariah source cache in SQLite with composite primary key `(ticker, source_name)` so multiple providers can mark the same ticker without overwriting each other.
- Implemented SPUS loader in `backend/src/data/shariah_spus.py`.
  - Real source: official SP Funds CSV at `https://www.sp-funds.com/wp-content/uploads/data/TidalFG_Holdings_SPUS.csv`.
  - Seed result: 215 SPUS rows in `backend/data/catalog.db`.
  - Honest correction: the old task text mentioned Wahed, but the current live SPUS holdings feed is hosted by SP Funds.
- Implemented Halal Terminal loader in `backend/src/data/shariah_halal_terminal.py`.
  - Real source: `https://api.halalterminal.com/api/results` for cached screening results.
  - Live per-symbol fallback: `POST https://api.halalterminal.com/api/screen/{symbol}` when `HALAL_TERMINAL_API_KEY` is configured.
  - User-provided key was used process-locally only; it was not written into files.
  - Seed result from the live API: 4,100 cached screening rows returned, 1,418 US equities, 459 compliant US-equity rows cached.
  - Honest caveat: Halal Terminal reported many cached rows as stale, so `backend/data/manifest.json` marks `halal_terminal.is_stale=true`.
- Implemented Finispia import support in `backend/src/data/shariah_finispia.py`.
  - Real source mode: user-provided CSV/JSON export path or URL via `FINISPIA_EXPORT_PATH`, `FINISPIA_EXPORT_URL`, or `--finispia-export`.
  - No Finispia rows were seeded in this pass because no Finispia export/API path was provided.
  - No undocumented Finispia endpoint was hardcoded or fabricated.
- Implemented composite `ShariahLookup` in `backend/src/shariah/lookup.py`.
  - Effective verdict: `(active external source match OR user inclusion) AND NOT user exclusion`.
  - Exclusion wins.
  - External source label wins over user inclusion when both exist; user note is preserved.
  - Conflicts are surfaced with `conflict=true`.
- Wired the lookup into `backend/src/screening/engine.py`.
  - `filters.shariah_only=true` now actually filters candidates.
  - `ScreenResult.id` changes when active sources or user include/exclude lists change.
  - Candidate rows carry Shariah provenance fields used by the frontend badge.
  - `stale_sources` surfaces unavailable/stale external sources.
- Added `GET /shariah/status/{ticker}` in `backend/src/api/shariah.py`.
  - Supports `?sources=...&include=...&exclude=...`.
  - Candidate detail now uses this real lookup instead of a hardcoded `not_listed` response.
- Updated seed/ingest scripts.
  - `scripts/seed_universe.py` refreshes SPUS by default, Halal Terminal when `HALAL_TERMINAL_API_KEY` is set, and Finispia when `--finispia-export` is supplied.
  - `scripts/ingest_daily.py` refreshes the same Shariah sources unless `--skip-shariah` is passed.

**Frontend implemented**

- Added `frontend/src/components/ShariahBadge.tsx`.
  - Renders SPUS, Halal Terminal, Finispia, User, excluded-by-user, not-listed, unknown, and stale labels.
- Added `frontend/src/app/settings/page.tsx`.
  - Shariah toggle.
  - Source selector: SPUS holdings, Halal Terminal, Finispia.
  - User include/exclude list manager with optional notes.
  - Conflict warning when a ticker is in both lists.
  - Cap, liquidity, and default-strategy settings.
- Extended `frontend/src/lib/store.ts` to schema version 2 with persisted Shariah include/exclude lists and liquidity settings.
- Updated `frontend/src/app/screen/[strategy]/page.tsx`.
  - Sends active sources and user lists to the backend.
  - Adds the per-run "Show all matches" override.
  - Surfaces Shariah stale-source warnings.
- Added a lean `frontend/src/app/portfolio/page.tsx`.
  - Displays current local holdings with Shariah badges.
  - Displays non-compliant count and user-marked count.
  - Superseded by the full Phase 7 portfolio workflow implemented later on 2026-06-11.

**Validation**

Commands run successfully:

```powershell
py -3.12 -m pytest backend\tests -q
npm.cmd run lint
npm.cmd run build
npx.cmd playwright test
```

Results:

- Backend tests: `34 passed`
- Frontend lint: PASS
- Frontend production build: PASS
- Playwright: `10 passed`

Live source smoke:

```text
SPUS cached rows: 215
Halal Terminal cached compliant US-equity rows: 459
/shariah/status/AAPL?sources=spus_holdings,halal_terminal -> compliant via spus_holdings
```

**Remaining honest caveats**

- The app still does not screen the entire approximately 6,000-stock US market by default; the existing universe loader is still constrained by the earlier 20-ticker default until T017/full-universe work is completed.
- SPUS is only an ETF-holdings proxy, not a full halal universe.
- Halal Terminal gives a much broader cached screened set and live per-symbol screening when the API key is present, but the seeded cached rows contain stale flags from the provider.
- Finispia support is real but import-based until the user supplies a real export/API path. No Finispia data was invented.

## Executive Summary

I implemented the audit remediation plan for the execution blockers, indicator tests, real data ingestion, real US1 screening, and runnable E2E path.

The app now runs against real data:

- `scripts/seed_universe.py` seeded `backend/data/catalog.db` with 20 real ticker rows from SEC company tickers plus yfinance metadata.
- `scripts/ingest_daily.py` fetched and persisted 8,860 real yfinance OHLCV rows into `backend/data/prices/parquet/`.
- `/meta` reads `backend/data/manifest.json`; it no longer invents a mock source.
- `/strategies/midterm_52w_high_momentum/run` reads real Parquet/yfinance prices, computes real 52-week high, ATR, 12-1 momentum, liquidity, and quality inputs, then runs the strategy.
- The legacy `/api/v1/screen` endpoint is now a compatibility wrapper around the real strategy engine. It no longer returns hardcoded AAPL/MSFT rows.

The important honest caveat: **T049 is not complete**. I regenerated backtest artifacts from code, but the artifact says the truth: it used yfinance/current-listed tickers and current provider fundamentals. Its bias check fails survivorship-bias-free coverage and point-in-time fundamentals. Therefore I changed `tasks.md` back to `- [ ] T049`, and the strategy is available but **not `enabled_by_default`**.

## Validation Run

Commands run successfully:

```powershell
py -3.12 -m pip install -e ".[dev]"   # from backend/
py -3.12 scripts\seed_universe.py
py -3.12 scripts\ingest_daily.py
py -3.12 -m pytest backend\tests -q
npm.cmd run lint                       # from frontend/
npm.cmd run build                      # from frontend/
npx.cmd playwright install chromium
npx.cmd playwright test                # from frontend/
```

Results:

- Backend install with Python 3.12: PASS
- Backend tests: `14 passed`
- FastAPI TestClient smoke:
  - `/healthz`: PASS, middleware injects disclaimer/data_as_of
  - `/meta`: PASS, returns yfinance and SEC manifest sources
  - `/strategies/midterm_52w_high_momentum/run`: PASS, returned real candidates (`LLY`, `UNH` during this run)
- Frontend lint: PASS
- Frontend production build: PASS
- Playwright: `3 passed`

## What Changed

### Execution and Packaging

- Added `backend/README.md`, package `__init__.py` files, Hatch wheel package config, and pytest path config.
- Verified Python 3.12 exists and installed the backend with:
  - `py -3.12 -m pip install -e ".[dev]"`
- Corrected `sec-edgar-downloader` dependency from the non-existent `>=13.0.0` to `>=5.1.0`.
- Removed the runtime dependency on `pandas-ta`; indicators are now implemented directly with pandas.

Files:

- `backend/pyproject.toml`
- `backend/README.md`
- `pytest.ini`
- `backend/src/**/__init__.py`

### API Shell and Disclaimer

- Added `backend/src/lib/disclaimer.py` as the single disclaimer source.
- Replaced the no-op middleware with middleware that reads JSON responses and injects missing `disclaimer` and `data_as_of` fields.
- Added CORS for local frontend dev ports `3000` and `3100`.
- Standardized backend imports away from mixed `backend.src...` usage in API runtime modules.

Files:

- `backend/src/api/app.py`
- `backend/src/lib/disclaimer.py`
- `backend/src/api/backtest.py`
- `backend/src/api/candidates.py`
- `backend/src/api/strategies.py`

### Manifest-backed `/meta`

- Replaced the hardcoded yfinance mock response with manifest parsing.
- Current manifest contains real source entries:
  - `yfinance`, 8,860 OHLCV rows
  - `sec_edgar_company_tickers`, 20 seeded ticker rows

Files:

- `backend/src/api/meta.py`
- `backend/data/manifest.json`

### Indicator Library and Tests

- Added real golden-fixture tests for all eight required indicator test files.
- Added property tests for SMA and ATR.
- Corrected ATR to use Wilder's simple-average seed before smoothing.

Files:

- `backend/src/indicators/moving_averages.py`
- `backend/src/indicators/volatility.py`
- `backend/src/indicators/momentum.py`
- `backend/tests/indicators/test_sma.py`
- `backend/tests/indicators/test_ema.py`
- `backend/tests/indicators/test_atr.py`
- `backend/tests/indicators/test_price_action.py`
- `backend/tests/indicators/test_adr.py`
- `backend/tests/indicators/test_chandelier.py`
- `backend/tests/indicators/test_momentum.py`
- `backend/tests/indicators/test_properties.py`

### Real Data Scripts

- `seed_universe.py` now fetches SEC company tickers and yfinance metadata, creates SQLite schema, and writes real catalog rows.
- `ingest_daily.py` now fetches real yfinance OHLCV, writes Parquet partitions, and updates the manifest.
- `refresh_stooq_history.py` now performs the real Stooq ZIP download and extraction. I did **not** run the full Stooq download in this pass.

Files:

- `scripts/seed_universe.py`
- `scripts/ingest_daily.py`
- `scripts/refresh_stooq_history.py`
- `backend/data/catalog.db`
- `backend/data/prices/parquet/`

### Real US1 Screening

- Restored `backend/src/screening/engine.py` after the interrupted previous turn had deleted it.
- Removed `frozen_us1_universe()`.
- Engine now:
  - Reads local Parquet prices first.
  - Fetches missing tickers from yfinance.
  - Applies the liquidity gate.
  - Computes 52-week high, ATR, 12-1 return, and 6-month returns.
  - Fetches actual yfinance profile/fundamental fields concurrently.
  - Runs `midterm_52w_high_momentum.rules()`.
  - Returns deterministic screen IDs from the real parameter/filter/as-of snapshot.
- Legacy `/api/v1/screen` no longer returns hardcoded rows; it delegates to `run_strategy()`.

Files:

- `backend/src/screening/engine.py`
- `backend/src/api/screen.py`
- `backend/src/strategies/midterm_52w_high_momentum.py`

Current real run observed:

```text
candidate_count = 2
candidates = LLY, UNH
data_as_of = 2026-06-08T21:00:00Z
```

### Backtest Infrastructure

- Added regenerable backtest code:
  - `runner.py`
  - `metrics.py`
  - `bias_check.py`
- Regenerated:
  - `backend/data/backtests/midterm_52w_high_momentum.json`
  - `backend/backtests/midterm_52w_high_momentum/summary_metrics.json`
  - `backend/backtests/midterm_52w_high_momentum/yearly_metrics.json`
  - `backend/backtests/midterm_52w_high_momentum/bias_check.md`
  - `backend/backtests/midterm_52w_high_momentum/equity_curve.parquet`

Honest limitation:

- The generated artifact used `yfinance`, because no Stooq bundle was present.
- It used currently listed tickers only.
- It used current provider fundamentals for the quality gate, not point-in-time EDGAR fundamentals.
- The generated `bias_check.md` therefore has unchecked items for survivorship bias and point-in-time fundamentals.
- Because of this, `midterm_52w_high_momentum.enabled_by_default` is now `False`.
- I unmarked T049 in `tasks.md`.

### Frontend and E2E

- Added `frontend/playwright.config.ts` that starts backend and frontend on fresh ports:
  - backend: `127.0.0.1:8100`
  - frontend: `127.0.0.1:3100`
- Installed Playwright Chromium.
- Updated US1 E2E to assert live candidate table fields without relying on old mock tickers.
- E2E now passes against real servers.

Files:

- `frontend/playwright.config.ts`
- `frontend/tests/e2e/us1-midterm-screen.spec.ts`

## Current Task Status by Audit Area

### Fixed or materially remediated

- T002 backend install now works with Python 3.12.
- T007 data directories and real data now exist.
- T014 EDGAR fundamentals loader is no longer an empty stub; it fetches SEC companyfacts and parses common normalized fields.
- T017 seed universe script writes a real SQLite catalog for the selected real ticker universe.
- T018 Stooq script performs a real download/extract when run.
- T019 ingest script writes real yfinance Parquet data and manifest provenance.
- T020-T027 indicator test files are no longer empty.
- T028 indicators run without `pandas-ta`.
- T030 registry enforces the 15-year/2008-2009 backtest window gate.
- T031 screening engine uses real data, not a frozen DataFrame.
- T032-T034 backtest/metrics/bias-check modules are no longer empty.
- T035 middleware really injects disclaimer/data_as_of.
- T037 `/meta` reads the manifest.
- T051 strategy run endpoint runs the real engine.
- T060 Playwright E2E passes.

### Still not fully complete

- T014 is real code, but the live US1 screen still uses yfinance current profile fields for FCF/debt-to-equity rather than point-in-time EDGAR fundamentals.
- T017 currently seeds the selected real ticker set by default (20 tickers), not the full approximately 6,000-name US common-equity universe.
- T018 was implemented but the full Stooq bundle was not downloaded during this pass.
- T049 is not complete. A real artifact exists, but it is not a constitution-grade Stooq/delisted/point-in-time backtest. Bias check fails two items.
- Strategy `enabled_by_default` is false until T049 is genuinely satisfied.
- The backtest runner is an annual, deterministic, price-based validation harness. It is not yet a full production walk-forward simulator with full universe membership reconstruction.

## No Placeholder / Mock Data Check

I ran:

```powershell
rg -n "mock|dummy|placeholder|frozen_us1|MOCK|Stub implementation|stub implementation|hardcoded 4-row|NotImplemented" backend frontend scripts -g '!frontend/node_modules/**' -g '!frontend/.next/**'
```

Runtime result:

- No app/runtime placeholder or mock-data hits.
- Only `@vitest/mocker` appears inside `frontend/package-lock.json`, which is a dependency package name, not application mock data.

## Final Honest State

US1 is now demoable on real data:

- Backend imports.
- Frontend builds.
- Data seed/ingest produces real local artifacts.
- The strategy run endpoint returns real candidates.
- E2E passes.

US1 is **not yet constitution-grade complete** because the backtest evidence is not survivor-bias-free and not point-in-time for fundamentals. The right next step is to run the real Stooq download, extend the runner to reconstruct the full historical universe with delisted tickers, and feed point-in-time EDGAR fundamentals into the quality gate before re-checking T049 and enabling the strategy by default.

## Update 2026-06-10 (b) — T049 backtest rebuilt on real deep history + point-in-time fundamentals

Two of the three "next steps" above are now done; the third (delisted coverage) is blocked on a paid data source.

**What changed**

- **T048a / T048b (US1 strategy modifications):** added a Novy-Marx gross-profitability gate (`gp_to_assets` top-half) and a Faber-style trend confirmation + 200-day-SMA trend exit to `midterm_52w_high_momentum`. The stop is now the 200-day SMA (ATR fallback); the fixed take-profit cap was replaced with an R-multiple reference target.
- **T049a (backtest parity, DONE):** `quality_metrics_as_of` in `fundamentals.py` extracts point-in-time FCF, debt/equity, and GrossProfit→GP/Assets (with `Revenues − CostOfRevenue` fallback), filtering filings to `filed <= as_of` to bar look-ahead. The runner now emits `sma_200` + `gp_to_assets`, so the backtest exercises the *same* gates the live screen runs.
- **Real data ingested:** the operator downloaded the Stooq US daily bundle (510 MB). It was extracted (12,342 files) and the 8,605 common-stock files consolidated into `backend/data/prices/stooq_parquet/` (18.5M bars, 2008-2009 covered). `scripts/build_stooq_parquet.py` is the builder.
- **T049 (PARTIAL):** ran the point-in-time backtest 2008-01-01 → 2024-12-31 over the full Stooq universe with point-in-time EDGAR companyfacts (cached under `backend/data/edgar_cache/`). Near-high pool union = 2,289 tickers; 70 trades across 14 of 17 years (2008-2010 correctly produced no trades — almost nothing sits near a 52-week high in the crash). Window now meets the ≥15-year / 2008-2009 floor.

**Real artifact (`backend/backtests/midterm_52w_high_momentum/`)**

- summary: total_return ≈ 12.33 (concatenated trade returns, not annualized), max_dd ≈ 0.66, hit_rate ≈ 0.63, avg_win ≈ 0.184, avg_loss ≈ 0.154, 70 trades.
- **bias_check = 3/4 PASS** (lookahead ✓, point_in_time_fundamentals ✓, costs ✓).
- **survivorship_bias = FAIL** — verified the *free* Stooq bundle has **no delisted tickers** (0/400 sampled files end before 2023; Lehman/Enron/Bear Stearns absent). The reported numbers are therefore survivor-inflated (real drawdowns/failures understated).

**Status:** `enabled_by_default` stays **false** (registry T030 gate; survivorship not satisfied). Closing it is tracked as **T049b** — re-run against a delisted-inclusive source (EOD Historical Data ~$19.99/mo, paid Stooq, or CRSP), set `delisted_coverage=True`, then all four checks go green.

**Runbook to reproduce / extend**

```powershell
# 1. place the Stooq bundle at backend/data/prices/d_us_txt.zip, then:
py -3.12 scripts\refresh_stooq_history.py --skip-download   # extract
py -3.12 scripts\build_stooq_parquet.py                     # consolidate -> stooq_parquet/
# 2. run the point-in-time backtest (reuses backend/data/edgar_cache/):
py -3.12 backend\src\backtests\runner.py --start 2008-01-01 --end 2024-12-31
```

**Related plan:** Phase 10 (T118–T123) in `tasks.md` adds incremental yfinance caching so the live screen stops re-fetching every run (fix the destructive `save_prices` partition overwrite first).
