# Contract: manual buy/sell transaction recording

Two new routes on the existing portfolio router, reusing the feature-013 import validator +
`_assemble_holdings` aggregation so manual entry and Sheet import converge on one holdings model.
The Google-Sheet import (`POST /portfolio/import`) is unchanged and remains the secondary bulk
path. Raw transactions are retained in the owner blob's `transactions` list (already the
persistence shape — `PortfolioTransactionsSlice`).

## `POST /portfolio/transactions`

Append one or more manual transactions.

Request (same row shape the import already accepts):
```json
{
  "rows": [
    { "ticker": "AAPL", "action": "buy",  "quantity": "10", "price": "180.00", "trade_date": "2026-06-01", "fees": "1.00", "source_row": 1 },
    { "ticker": "AAPL", "action": "sell", "quantity": "4",  "price": "210.00", "trade_date": "2026-06-20", "source_row": 2 }
  ]
}
```

Response: `ImportResult` (`accepted_count`, `duplicate_count`, `rejected[]`,
`transactions_total`, `data_as_of`, `disclaimer`).

## `DELETE /portfolio/transactions/{id}`

Remove one transaction by its stable content-hash `id` (correct a mistake), then re-aggregate.
Response: `ImportResult`-style summary of the resulting state. 404 if the id is unknown.

## Invariants (tests — `backend/tests/contract/test_portfolio_transactions.py`)

1. **Validation reuse** — an invalid manual row is rejected with the same reasons/shape as an
   invalid imported row (shared validator).
2. **Aggregation parity** — recording a buy (then a partial sell) in-app yields the *same*
   holding (`net_quantity`, `avg_cost`, `cost_basis`, `realized_pl`, `status`) as the equivalent
   import — SC-010.
3. **Retention** — appended transactions persist in the blob's `transactions` list (needed for
   FIFO realized P&L) and survive a state round-trip.
4. **Delete corrects** — deleting a transaction re-aggregates holdings and P&L to the expected
   post-deletion state; unknown id → 404.
5. **Envelope** — responses carry `data_as_of` + `disclaimer`.
6. **Secondary import intact** — `POST /portfolio/import` still works unchanged (regression).
