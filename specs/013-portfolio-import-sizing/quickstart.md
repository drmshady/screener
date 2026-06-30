# Quickstart: Portfolio Import, Purchase-Anchored Levels & Risk-Aware Sizing

Owner runbook for feature 013. Personal-use, single owner, USD only.

## 1. Lay out your Google Sheet

One row per transaction. Headers are matched **case-insensitively** and your descriptive
column names are recognized via aliases; every other column (the sheet's computed columns like
`Cumulative Units`, `Stock Split Ratio`, `Realised Gains/Losses %`) is ignored.

| Your header | Used as | Example |
|-------------|---------|---------|
| `Date` | trade date | `28/7/2025`, `9-Oct-2025`, `2026-02-10` |
| `Type` | action | `Buy`, `Sell` |
| `Stock` | ticker | `MSFT`, `amzn` |
| `Transacted Units` | quantity | `22.0` |
| `Transacted Price (per unit)` | price | `$46.50` |
| `Fees` | fees (optional) | `$2.32` |

- `Type` must be `Buy` or `Sell` (case-insensitive). **`Div` (cash dividend) rows are not
  tracked in v1** — they appear in the import summary as *unsupported / skipped* with a reason
  (they never change your share count). DRIP/split rows are out of scope.
- `Transacted Units` and `Transacted Price (per unit)` must be positive; `$` and thousands
  commas are stripped automatically.
- **Slash dates are read day-first** (`28/7/2025` = 28 July). `9-Oct-2025` and ISO
  `YYYY-MM-DD` also work.
- **Coverage**: most ETFs (SPUS, SLV, IBIT, GLD) are outside the screener's US-common-equity
  universe and show as *out of coverage / not priceable* — your cost facts are kept, but no
  levels/risk are computed for them.

## 2. Connect and import

1. Open the **Portfolio** page → **Import from Google Sheets**.
2. Click **Connect Google** — sign in with your Google account (the same one allowlisted for
   the app) and grant **read-only Sheets** access. The access token is short-lived and stays in
   your browser; it is never saved to disk or sent to the server.
3. Paste/confirm the **spreadsheet link or id** and the **tab/range** (e.g.
   `Transactions!A1:G`). These (not the token) are remembered for one-click re-import.
4. Click **Import**. The browser reads the rows and sends them to the backend, which validates
   and aggregates them.

**Import summary** shows: accepted (net-new) count, skipped duplicates, and any **rejected
rows** with the row number and reason. Fix rejected rows in the sheet and re-import — only the
changes are applied (no double-counting).

## 3. Read your holdings

Each open holding shows:

- **Quantity & average cost** (share-weighted across your buys), **current price**, and
  **unrealized P/L** ($ and %).
- **Two stop/target bases**, each labelled:
  - **Original plan** — fixed from your purchase price and the volatility *as of your earliest
    buy date*. Shows how the plan you entered with is aging.
  - **Current condition** — same purchase price, but stop/target recomputed on the latest data.
  - A holding whose price has crossed a level is flagged **Stop breached** or **Target reached**
    (informational status, not an instruction).
  - Too little price history ⇒ a neutral **Insufficient data** note instead of an error.

## 4. Read the risk view

- **Recommended vs actual size**: recommended uses your capital base and per-trade risk budget
  sized to the current-condition stop (the existing risk-per-trade rules and caps); actual is
  what you hold.
- **Capital at risk**: dollars and % of capital you'd lose if the stop were hit, per holding.
- **Over-risk flag**: positions whose actual capital-at-risk exceeds the per-trade budget or a
  position/sector cap are flagged with the **binding constraint** named.
- **Portfolio totals**: total invested and total capital-at-risk.

Set your **Total capital** at the top of the Portfolio page; sizing recommendations appear once
it's set.

## 5. Clear / replace

Use **Clear portfolio** to empty imported transactions and start fresh. Re-import any time —
the portfolio is the deterministic result of your transactions plus the latest data snapshot.

## Notes & limits

- **Coverage**: current price and volatility come from the screener's existing universe. A
  ticker outside coverage (delisted, non-US, typo) is shown with your cost facts but marked
  **out of coverage / not priceable**.
- **USD only** for v1.
- **Multiple buys of one ticker** aggregate into a single average-cost holding; the earliest
  buy date anchors the original-plan levels.
- Every portfolio view shows the data **as-of** date and the **not-investment-advice**
  disclaimer.

## Developer notes

- Backend: `POST /portfolio/import`, `POST /portfolio/holdings` in
  `backend/src/api/portfolio.py`; pure logic in `backend/src/portfolio/{transactions,
  aggregation,holding_levels,holding_risk}.py`; reuses
  `strategies/levels.derive_bounded_levels`, `portfolio/sizing.size_position`, and
  `screening/engine.build_single_ticker_snapshot(ticker, as_of=…)`. Run from repo root:
  `py -3.12 -m pytest backend/tests -q` (see [[windows-dev-runbook]]).
- Frontend: `frontend/src/lib/googleSheets.ts` (GIS token + Sheets API, browser-only),
  `ImportTransactions.tsx`, extended `app/portfolio/page.tsx`. Prod build for headless e2e per
  [[windows-dev-runbook]]. No Google secret in any build artifact ([[api-keys-never-write]]).
- **Deployment** (GitHub Actions → GHCR → Hugging Face Space `occlusion2/screener` + Vercel):
  no CI/image change — the backend gains no dependency and no ingest. Add one **public** env
  var on Vercel, `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (reuse feature 010's Google OAuth app; add the
  `spreadsheets.readonly` scope and the Vercel domain + `localhost` to its authorized JS
  origins). The import UI disables the Connect button (with a note) when that id or the GIS
  script is absent, so headless/offline builds never require Google. On the HF Space the
  container filesystem is ephemeral and rebuilt daily, so the server portfolio blob is wiped on
  each redeploy and **re-seeded from your browser** by `PortfolioSync` — your imported
  transactions live in the browser's local storage as the durable copy; use Settings
  export/import (or just re-import the sheet) when moving devices.
