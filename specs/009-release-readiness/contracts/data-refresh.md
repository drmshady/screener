# Contract: `POST /data/refresh` — Incremental, operator-initiated refresh

Formalizes the **existing** endpoint (`backend/src/api/data.py`). This feature
does not change its behavior; it pins the guarantees the startup gate relies on.
Satisfies FR-002 (graceful on unreachable source), FR-003 (incremental, no full
rebuild).

## Request

```jsonc
POST /data/refresh
{
  "market": "US",            // optional: "US" | "SA"; default US
  "tickers": ["AAPL", ...]   // optional explicit list; else the screened universe
}
```

## Response `200`

```jsonc
{
  "refreshed_tickers": 812,
  "fetched_rows": 1624,
  "latest_bar": "2026-06-16",
  "capped": false,           // true if the universe exceeded the 1,200 cap
  "data_as_of": "2026-06-17T05:01:00Z",
  "disclaimer": "…"
}
```

## Guarantees (contract tests)

1. **Incremental only** (FR-003): fetches incremental bars
   (`fetch_incremental_ohlcv`) for stale names; it MUST NOT trigger a full
   universe/fundamentals rebuild. Bounded by the 1,200-ticker cap (`capped`
   flags truncation).
2. **Side effects on success**: persists fetched bars, updates `manifest.json`
   (so `/meta` and `/data/freshness` advance), clears snapshot caches, and
   best-effort refreshes reference thresholds. None of these may raise to fail the
   refresh.
3. **Graceful on unreachable source** (FR-002): a provider outage MUST NOT crash
   the session; the operator keeps the cached data and a non-blocking staleness
   notice. (Refresh returns the best available state; the startup gate continues
   to function on cached data.)
4. **Operator-initiated only** (FR-001): nothing calls this automatically on load;
   it is invoked solely by the operator's *Refresh now* action.
5. **Determinism downstream** (FR-015): after refresh, the same (new) snapshot
   reproduces identical screen/regime/sizing/event output across runs.
