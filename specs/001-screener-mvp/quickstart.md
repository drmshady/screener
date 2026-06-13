# Quickstart: US Stock Screener MVP

**Feature**: 001-screener-mvp
**Audience**: A developer setting up the project for the first time, or a reviewer who wants to validate the v1 happy path locally.

This runbook gets you from a fresh clone to a working screener that runs a mid-term strategy against a real US equity universe and renders results in the browser.

---

## Prerequisites

- Python 3.12 (matches CLAUDE.md memory — `python -m pip install` because system `pip` may link to 3.13).
- Node.js 20 LTS + npm.
- Git.
- ~6 GB free disk for the Stooq archive, consolidated Parquet store, and computed snapshot caches.
- A working internet connection for the first ingest (SEC EDGAR + yfinance + SPUS).

---

## 1. Clone and install

```bash
git clone <repo-url> screener
cd screener

# Backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows PowerShell; on macOS/Linux: source .venv/bin/activate
python -m pip install -e ".\backend[dev]"

# Frontend
cd frontend
npm install
cd ..
```

---

## 2. Seed the universe and reference data (one-time, ~5 minutes)

```bash
python scripts/seed_universe.py
```

What this does:
- Pulls the SEC EDGAR `company_tickers.json` listing (free, public domain) to populate the `Ticker` catalog.
- Maps each ticker's SIC code to the 11-sector taxonomy.
- Pulls the current SPUS ETF holdings (~200 tickers) and writes them as the v1 default `ShariahSource`.
- Seeds the curated economic calendar from `backend/data/econ_calendar.yaml`.

Stamps every loaded row with `source_name` + `source_as_of` per Constitution I.

---

## 3. Pull deep historical price data from Stooq (one-time, ~10 minutes; refresh quarterly)

```bash
python scripts/refresh_stooq_history.py
```

What this does:
- Downloads the Stooq US daily-bar bundle (`https://stooq.com/db/d/?b=d_us_txt`).
- Unpacks per-ticker CSVs into `backend/data/prices/stooq/`.
- Stamps every row `source=stooq`, `source_as_of=<bundle date>`.
- This is the broad free deep-history source that lets backtests cover 2008-2009 and earlier (research.md Decisions 4 and 15). Refresh quarterly; manual is fine for personal use.

**Honest limitation**: the audited free Stooq bundle used by this workspace does **not** include delisted coverage. It is useful broad deep history, but survivor-bias-free backtests still require a delisted-inclusive source such as paid Stooq, EOD Historical Data, or CRSP. yfinance alone is not sufficient for the backtest window the constitution requires.

---

## 4. Run the first daily ingest (~3 minutes)

```bash
python scripts/ingest_daily.py
```

What this does:
- Incrementally fetches only missing end-of-day OHLCV bars for the active yfinance cache universe.
- Refreshes the 7-day ticker profile/fundamentals cache, preferring the local EDGAR cache for quality metrics where available.
- Warms broad Stooq-derived strategy snapshots so a restarted app can serve the screen from local computed data.
- Pulls 8-K filings from EDGAR since the last successful run.
- Refreshes the next 30 days of earnings dates.
- Re-pulls configured Shariah sources (SPUS plus enabled ETF/Halal Terminal/Finispia inputs).
- Updates `backend/data/manifest.json` with per-source success/failure + as-of stamps.

Idempotent — running twice on the same day is a no-op for already-fetched rows.

---

## 5. Start the backend

```bash
py -3.12 -m uvicorn backend.src.api.app:app --reload --port 8000
```

Open `http://localhost:8000/docs` — the FastAPI Swagger UI should match `specs/001-screener-mvp/contracts/openapi.yaml`.

Smoke test:
```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/meta | python -m json.tool       # per-source as-of stamps
curl http://localhost:8000/strategies | python -m json.tool
```

---

## 6. Start the frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000`.

The home dashboard should render with:
- Market regime indicator (Trending up / Range-bound / Trending down) plus the rule that produced it.
- Market Events This Week panel.
- A list of available strategies with per-strategy regime favorability tags.
- The non-advice disclaimer in the footer.

---

## 7. Run your first screen (validates US1, the MVP story)

1. Click the default mid-term strategy (`52-week-high momentum`).
2. Click **Run screen**.
3. Within 10 seconds you should see a ranked candidate list, each row showing:
   - Ticker, name, sector
   - Current price
   - Suggested entry, stop-loss, take-profit
   - One-line "why it matched"
   - As-of date
   - (If applicable) "Earnings in N days" or "Material news (N in 30d)" badges from US4.
4. The disclaimer is visible without scrolling past the result table.

Save a candidate to your watchlist; reload the page; the watchlist entry persists (it lives in `localStorage`).

---

## 8. Try the Shariah filter (US3)

The filter is a **composite** of one or more external sources (SPUS by default) plus two user-managed lists. SPUS is FTSE USA Shariah-screened (large/mid cap US), so it deliberately leaves out smaller compliant names — the user lists are how you extend or override.

1. Open **Settings** → toggle "Shariah-compliant only" ON.
2. Re-run a screen.
3. Every candidate row now carries a badge: "Shariah-compliant (SPUS) — YYYY-MM-DD".
4. **Extend beyond SPUS**: in **Settings → Shariah list manager → Additional compliant tickers**, add a ticker you have personally vetted (e.g., a recent IPO or a small-cap industrial) with an optional rationale note. Re-run the screen — it now appears as a candidate (if it matches the strategy) with badge "Shariah-compliant (User)" and your note on hover.
5. **Override SPUS inclusion**: in **Settings → Shariah list manager → Excluded tickers**, add a SPUS-listed ticker you personally reject. It disappears from screens and is tagged "Excluded by user" in the Portfolio view.
6. Add a non-SPUS, non-user-listed ticker (e.g., `JPM`) to your portfolio — it shows up as "Not Shariah-compliant" in the Portfolio view.
7. Conflict check: add a ticker to BOTH the inclusion and exclusion lists — exclusion wins, and the Settings page surfaces a "Conflicting overrides" warning.

---

## 9. Try the portfolio and sizing (US5)

1. Open **Portfolio**.
2. Enter total capital: `10000`.
3. Add 3 holdings across 2 sectors.
4. Sector exposure percentages should match a hand-calculation.
5. Go back to a screen result, pick a candidate, click **Size this trade**.
6. The suggested share count + dollar position MUST respect:
   - Per-position cap (default 10% of total capital)
   - Per-sector cap (default 25% of total capital)
7. If the candidate's minimum share value exceeds the per-position cap, the response is "Cannot size without breaching cap" with the numbers — not a fractional share.

---

## 10. Validate determinism (Constitution III)

```bash
# Re-run the same strategy twice — id and candidate list should be identical
curl -X POST http://localhost:8000/strategies/midterm_52w_high_momentum/run \
  -H "Content-Type: application/json" -d '{"filters": {"shariah_only": false}}' > /tmp/run_a.json

curl -X POST http://localhost:8000/strategies/midterm_52w_high_momentum/run \
  -H "Content-Type: application/json" -d '{"filters": {"shariah_only": false}}' > /tmp/run_b.json

diff /tmp/run_a.json /tmp/run_b.json     # should be empty
```

---

## 11. Run the tests

```bash
# Backend
py -3.12 -m pytest backend/tests -q

# Frontend
cd frontend
npm.cmd run lint
npm.cmd run build
npx.cmd playwright test
```

The Playwright suite includes a "no directive copy" check that grep-validates rendered pages against `Buy`, `Sell`, `Recommended`, `Strong buy` — Constitution V's enforcement (spec SC-010).

---

## 12. Backtest one shipped strategy (Constitution III + walk-forward gate)

```bash
python -m backend.backtests.run --strategy midterm_52w_high_momentum --start 2008-01-01 --end 2024-12-31
```

Output lands in `backend/backtests/midterm_52w_high_momentum/<snapshot_id>/`:
- `equity_curve.parquet`
- `bias_check.md`  ← the bias-avoidance checklist with each item ticked and justified
- `yearly_metrics.json` ← per-calendar-year hit rate, max drawdown, win/loss — exposed via `GET /strategies/{slug}/backtest` (research.md Decision 16)
- `summary_metrics.json` ← aggregate over the window

**Window discipline (research.md Decision 15)**: a strategy is only allowed `enabled_by_default=true` if the backtest window is ≥ 15 years AND includes the 2008-2009 drawdown. If your data sources can't cover that window for the strategy's universe, the strategy ships as "Available but disabled by default" with a "Limited backtest window" warning on its detail page. This is enforced by the registry validation in `backend/src/strategies/_registry.py`.

This output is what's reviewed — and surfaced to the user — before a strategy is promoted to "Enabled by default".

---

## What's intentionally not in v1

For context — if you see these in code or docs, push back:

- News sentiment / NLP scoring
- In-app interactive backtester UI
- Brokerage integration, order placement
- Multi-user accounts, cloud sync
- Intraday data and intraday strategies
- Stricter Shariah financial-ratio screening (debt, interest income)
- Long-term buy-and-hold strategies (constitutionally deferred)
- Non-US markets
- **CAN SLIM-style growth strategy**: intentionally deferred to v1.x. A name-only "lite" version under O'Neil's citation fails Constitution II — research.md Decision 8 spells out the missing inputs and the conditions for re-introducing it. Slippage-adjusted entry display and soft regime degradation are also deferred (transparency over polish in v1).

---

## Troubleshooting

- **`yfinance` rate-limited / 429**: the ingest script implements backoff. If you trip the limit repeatedly, drop the universe to a smaller list with `--tickers SPY,QQQ,SPUS,AAPL,MSFT,NVDA` for a smoke test.
- **Stooq bundle download fails or is missing tickers your backtest needs**: this is the trigger for the one optional paid upgrade. EOD Historical Data ($19.99/mo) is the recommended drop-in — same `PriceProvider` interface, broader delisted coverage. Decision criteria are recorded in `bias_check.md` per strategy. For personal use, this is a per-strategy quality call, not a v1 launch blocker.
- **EDGAR 403 — User-Agent**: SEC requires a contact-style User-Agent. Set `SCREENER_EDGAR_UA="your-name your-email"` in your env.
- **SPUS holdings fetch failed**: fall back to the committed `backend/data/spus_holdings.<date>.json` snapshot — re-fetch later. The Shariah filter will show "Stale source" until refreshed.
- **Disclaimer missing on a page**: regression in `frontend/app/layout.tsx`. The disclaimer is rendered there unconditionally; tests in `frontend/tests/e2e/disclaimer.spec.ts` enforce this.
