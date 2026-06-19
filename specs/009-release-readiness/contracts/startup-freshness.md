# Contract: `GET /data/freshness` — Startup staleness detection

Read-only, no-mutation freshness check consumed by the frontend
`StartupFreshnessGate` on app load. Satisfies FR-001 (detect staleness), FR-004
(per-source freshness), FR-005 (latest completed trading session basis),
SC-002 (≤ 3 s, no refresh when current).

## Request

```
GET /data/freshness
```

No parameters. (Market is inferred per source; US is the default.)

## Response `200`

```jsonc
{
  "sources": [
    {
      "source_name": "yfinance",
      "kind": "prices",
      "data_as_of": "2026-06-16",        // latest session the cache covers (date)
      "latest_session": "2026-06-16",    // latest_completed_trading_day()
      "sessions_behind": 0,              // trading sessions behind (>=0)
      "is_stale": false,
      "last_refresh_outcome": "skipped-current"  // success | failed | skipped-current
    }
    // ... one per material source (prices, fundamentals, calendars)
  ],
  "any_stale": false,                    // true iff any source is_stale
  "latest_session": "2026-06-16",
  "data_as_of": "2026-06-17T05:00:00Z",  // envelope (middleware)
  "disclaimer": "…"                       // envelope (middleware)
}
```

## Guarantees (contract tests)

1. **No mutation**: the call writes nothing (no manifest write, no price fetch, no
   cache clear). A second identical call returns identical `sources`.
2. **No network**: staleness is computed from cached manifest metadata +
   `latest_completed_trading_day()`. The endpoint MUST succeed with the network
   disabled.
3. **≤ 3 s** (SC-002): p95 wall-time under the 3 s ceiling on the reference
   manifest. (Practically sub-second; the test asserts the ceiling.)
4. **Trading-session basis** (FR-005): `sessions_behind` uses the trading
   calendar; a weekend/holiday request does not report a current source as stale.
5. **Missing source = stale**: a material source absent from the manifest is
   reported `data_as_of: null`, `is_stale: true` (unknown ≠ current).
6. **Envelope**: response carries `data_as_of` and `disclaimer` (FR-019).
7. **`any_stale`** is the logical OR of the per-source `is_stale` flags and is the
   only signal the startup gate needs to decide whether to prompt.
