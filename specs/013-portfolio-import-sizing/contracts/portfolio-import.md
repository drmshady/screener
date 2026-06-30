# Contract: `POST /portfolio/import`

Validate and apply a batch of transaction rows the **browser** parsed from the owner's Google
Sheet (Decision 1 — the backend never talks to Google). Idempotent: previously-seen rows are
skipped (Decision 3). Router: `backend/src/api/portfolio.py`.

## Request

```jsonc
{
  "rows": [
    {
      "ticker": "AAPL",
      "action": "buy",
      "quantity": 10,
      "price": 175.00,
      "trade_date": "2026-02-10",
      "fees": 1.00,          // optional
      "note": "starter",     // optional
      "source_row": 2         // 1-based sheet row
    }
    // ...
  ],
  "sheet_id": "1AbC...",      // optional, stored non-secret for one-click re-import
  "sheet_range": "Transactions!A1:G"  // optional
}
```

- `rows` is the already-parsed sheet content; the server performs **all** validation.
- **No Google OAuth token is sent.** The token stays in the browser, short-lived (FR-001).

## Behavior

1. Validate each row (`portfolio/transactions.py`, pure) → accepted / rejected; never silently
   drop (FR-003, SC-002).
2. Compute each accepted row's stable `id` (Decision 3).
3. Merge into the persisted `transactions[]`, skipping ids already present (idempotent, FR-005,
   SC-003). Persist via `data/portfolio_store.py` (atomic write).
4. Persist `sheet_id` / `sheet_range` if provided (non-secret).

## Response `200`

```jsonc
{
  "accepted_count": 3,
  "duplicate_count": 12,
  "rejected": [
    { "source_row": 7, "raw": { "ticker": "TSLA", "price": "—" },
      "reason": "price '—' is not a positive number" }
  ],
  "transactions_total": 15,
  "data_as_of": "2026-06-30T21:00:00Z",
  "disclaimer": "For informational purposes only; not investment advice."
}
```

- `200` even when some rows are rejected (partial success is success — the rest applied).
- `422` only when the request body itself is malformed (e.g. `rows` not a list).
- Every response carries `data_as_of` + `disclaimer` (FR-019). Zero directive language (FR-020).

## Notes

- Owner-only: in hosted mode the existing owner-secret middleware + same-origin BFF gate this
  route like every other (feature 010); no change here.
- Determinism: identical `rows` posted twice ⇒ second call is all duplicates, portfolio
  unchanged (SC-003).
