# Contract: Bug B (regime) & Bug C (market events) response deltas

These are **presentation + freshness** deltas over existing endpoints. No strategy rule, default,
citation, indicator, or backtest baseline changes (SC-008). Determinism preserved (FR-B3).

---

## Bug B — `GET /regime` (RegimeResponse.inputs)

The SPY 200-day-SMA inputs MUST be populated from the SPY source that has ≥ `sma_length` usable rows
(prefer yfinance only when long enough; otherwise `baked(daily)`, then `stooq(local)`), so a
short/partial live frame never forces "Unknown" when the daily-baked series can compute the SMA.

### Response delta (`inputs`)

```jsonc
{
  "regime": "Trending up",
  "rule_summary": "Trending up: SPY is above its 200-day SMA; … breadth …",
  "inputs": {
    "spy_close": 561.23,
    "spy_sma200": 542.10,
    "spy_above_sma200": true,
    "price_source_name": "baked(daily)",     // yfinance | baked(daily) | stooq(local)  — never silently empty
    "unavailable_reason": null,              // NEW: string when spy_sma200 is genuinely null
    "…breadth fields…": "unchanged"
  },
  "as_of_date": "2026-07-02"
}
```

- **FR-B1.** When the data to compute close/SMA/verdict exists, all three are numeric and
  `price_source_name` + `as_of_date` identify the SPY series — including hosted + live-feed-down.
- **FR-B2.** When the 200-day SMA genuinely cannot be computed (true insufficient history),
  `spy_sma200`/`spy_above_sma200` are null **and** `unavailable_reason` states the specific reason
  and that the gate fails open — never a bare "Unknown".
- **FR-B3.** Same snapshot ⇒ identical close/SMA/verdict (determinism). Cache stores only a
  fully-resolved reading, so a transient rate-limit doesn't pin Unknown for a day.

### Frontend (`RegimePanel`)
Renders numeric SPY close, computed 200-day SMA, above/below verdict, source name, and as-of date —
or, when unavailable, the explicit `unavailable_reason` (fails-open) instead of "Unknown".

---

## Bug C — `GET /events/market` (MarketEventsResponse)

Freshness accounting is corrected so a re-seeded, still-valid curated calendar is not spuriously
flagged stale, and the curated window is rolled forward with real published dates so the panel does
not empty out.

### Response delta

```jsonc
{
  "events": [ /* FOMC / CPI / NFP / PCE / PPI — unchanged shape, real published dates only */ ],
  "source_name": "econ_calendar_v1",
  "source_as_of": "2026-06-11T00:00:00Z",   // CONTENT as-of (curation date) — unchanged meaning
  "is_stale": false,                        // now reflects the ACTUAL last-reseed time, not the static content date
  "data_as_of": "2026-07-02T21:00:00Z",
  "disclaimer": "…"
}
```

- `EventSource.last_refreshed_at` is stamped to the **actual reseed time** on each daily reseed, so
  `is_stale` (derived: `now - last_refreshed_at > refresh_interval_days`) is `true` only when the
  source is genuinely un-refreshed — not merely because the curated content date is a week old.
- The curated event list is extended forward with **officially-published dates only** (Fed/BLS/BEA);
  when official schedules end, the calendar ends (labeled) rather than fabricating dates or emptying
  silently.

### Frontend (`MarketEventsPanel`)
Shows the "Stale events data" badge **only** when `is_stale` is truly true. When the curated window
ends, shows a clear "schedule extends through <last real date>" note instead of a bare
"No scheduled events in this window."

---

## Bug A — Watchlist parity (no backend contract change)

Bug A is browser-side only: a shared `AddToWatchlist` control on both the results table and the
candidate detail page calls the existing idempotent `saveCandidate` store action (dedup on
`ticker + strategy_slug`), shows an immediate confirmation (FR-A2), and informs the owner when a name
is already watched (FR-A4). The watchlist entry (ticker, strategy, `levels_snapshot`) is already
persisted by `saveCandidate` (FR-A3). No API endpoint is added or changed.
