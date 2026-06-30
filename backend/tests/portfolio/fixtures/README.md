# Portfolio import test fixtures (feature 013)

Shared fixtures for the US1/US2/US3 transaction-import, aggregation, levels, and risk tests.
They are modeled on the owner's **real** Google Sheet and captured in the Google Sheets REST v4
`values` shape (`majorDimension: "ROWS"`, first row is the header) — exactly what the browser
`googleSheets.ts` reader returns. The pure backend parser (`portfolio/transactions.py`) is
responsible for header-alias mapping, `$`/comma stripping, day-first + month-name date parsing,
and case folding.

## Files

- `transactions_sheet.values.json` — the happy-path sheet: descriptive headers
  (`Date / Type / Stock / Transacted Units / Transacted Price (per unit) / Fees`) plus ignored
  spreadsheet-computed columns (`Total Value / Current Price / Market Value`), `$`/comma money
  (`$1,025.32`), day-first slash dates (`28/7/2025`), month-name dates (`9-Oct-2025`), lowercase
  tickers, one `Div` row (unsupported type), and out-of-coverage ETF tickers (SPUS/SLV/IBIT/GLD).
- `transactions_malformed.values.json` — rows that must each be **rejected with a reason** and
  never silently dropped (missing price, unparseable date, non-positive quantity, an unsupported
  action, a placeholder-dash price).

## Expected canonical parse — `transactions_sheet.values.json`

8 accepted transactions; 1 rejected (the `Div` row → unsupported type, no share-count change):

| ticker | action | qty | price     | fees  | trade_date  |
|--------|--------|-----|-----------|-------|-------------|
| SPUS   | buy    | 10  | 30.50     | 0.00  | 2025-07-28  |
| MSFT   | buy    | 5   | 400.00    | 1.00  | 2025-08-15  |
| MSFT   | buy    | 5   | 415.20    | 1.00  | 2025-10-09  |
| AMZN   | buy    | 8   | 1025.32   | 2.50  | 2025-09-20  |
| AMZN   | sell   | 3   | 1100.00   | 2.50  | 2025-10-05  |
| SLV    | buy    | 20  | 27.10     | 0.00  | 2025-06-12  |
| IBIT   | buy    | 15  | 42.00     | 0.00  | 2025-10-03  |
| GLD    | buy    | 4   | 245.00    | 0.00  | 2025-10-09  |

## Expected aggregation (average-cost) — known answers

| ticker | net_qty | avg_cost | earliest_buy | most_recent_buy | realized_pl | priceable |
|--------|---------|----------|--------------|-----------------|-------------|-----------|
| SPUS   | 10      | 30.50    | 2025-07-28   | 2025-07-28      | 0.00        | false (ETF, out of coverage) |
| MSFT   | 10      | 407.60   | 2025-08-15   | 2025-10-09      | 0.00        | true      |
| AMZN   | 5       | 1025.32  | 2025-09-20   | 2025-09-20      | 221.54      | true      |
| SLV    | 20      | 27.10    | 2025-06-12   | 2025-06-12      | 0.00        | false (ETF) |
| IBIT   | 15      | 42.00    | 2025-10-03   | 2025-10-03      | 0.00        | false (ETF) |
| GLD    | 4       | 245.00   | 2025-10-09   | 2025-10-09      | 0.00        | false (ETF) |

Derivations:
- `MSFT.avg_cost` = (5 × 400.00 + 5 × 415.20) / 10 = 4076.00 / 10 = **407.60**.
- `AMZN.realized_pl` = (1100.00 − 1025.32) × 3 − 2.50 fee = 224.04 − 2.50 = **221.54**
  (average-cost method; the sell does not change `avg_cost`).

These are reference expectations for the known-answer tests; if a downstream rule legitimately
differs, update this table alongside the test rather than silently diverging.

## Expected rejections — `transactions_malformed.values.json`

All 6 data rows reject (header row is valid): `nvda` (missing price), `aapl` (unparseable date),
`tsla` buy (quantity 0), `tsla` sell (quantity −2), `meta` (placeholder-dash price), `googl`
(action `Transfer` not in {buy, sell}).
