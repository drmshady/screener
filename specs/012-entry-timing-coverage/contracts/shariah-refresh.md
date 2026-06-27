# Contract: Quarterly Shariah Universe Refresh Cadence (US3)

`shariah/refresh_cadence.py` — a pure, clock-injected decision guard consulted **before** any
Halal Terminal network call, plus the manifest interval bump.

## Signature

```python
def should_refresh(now: datetime, last_success_at: datetime | None, *,
                   interval_days: int = 90, force: bool = False,
                   key_present: bool = True) -> RefreshDecision
```

`RefreshDecision = {action: "refresh"|"skip"|"stale", elapsed_days: float|None, reason: str}`
(data-model §4a). Calendar-day basis ("3 months = 90 days", spec Assumption).

## Decision table

| Inputs | `action` |
|--------|----------|
| `force=True`, `key_present=True` | `refresh` (bypass gate) — FR-016/US3.4 |
| `force=True`, `key_present=False` | `stale` (cannot fetch) |
| `last_success_at` missing/unreadable, `key_present=True` | `refresh` (treated as due) — FR-018 |
| `last_success_at` missing/unreadable, `key_present=False` | `stale` (fail-safe toward freshness) — FR-018 |
| elapsed < `interval_days` | `skip` (reuse cache, **zero API calls**) — FR-017/SC-006 |
| elapsed ≥ `interval_days`, `key_present=True` | `refresh` — FR-016 |
| elapsed ≥ `interval_days`, `key_present=False` | `stale` (reuse cache + loud warning) — FR-019/SC-007 |

## Integration

- `data/shariah_halal_terminal.py::seed_halal_terminal_results` and `bulk_screen_universe`
  call `should_refresh(...)` first and **short-circuit** on `skip`/`stale` (no `httpx` call);
  on `stale` they record/propagate the "compliance data stale" condition.
- Manifest metadata `refresh_interval_days` for `halal_terminal` becomes **90** (was 7) so
  `ShariahLookup._source_is_stale` reports staleness on the ~90-day basis (FR-020).
- `scripts/ingest_daily.py` honors a `--force-shariah` flag → `force=True`.
- The API key is only **read for presence** (`key_present`); it is never written to any
  artifact (consistent with [[api-keys-never-write]]).

## Invariants

1. **Determinism (FR-021)**: `action` is a pure function of `(now, last_success_at,
   interval_days, force, key_present)`.
2. **In-window zero calls (FR-017/SC-006)**: every `skip` makes **no** Halal Terminal API
   call — verified by call accounting / an injected `screen_fn` spy.
3. **Annual budget (SC-005)**: over a simulated year of routine refreshes, ≤ ~4 `refresh`
   actions occur (once per ~90-day window) plus any forced refreshes.
4. **Stale surfacing (FR-019/SC-007)**: when the window lapses without a successful refresh,
   the stale condition is surfaced on the relevant response 100% of the time (never silent).
5. **Fail-safe freshness (FR-018)**: a missing/unreadable timestamp is "due", never
   "infinitely fresh".
6. **First run after cadence change**: may consult the source once to establish a baseline
   timestamp, then settle into the 90-day cadence (spec edge case).

## Tests

- Acceptance scenarios US3.1–US3.5 with injected clocks.
- A simulated-year loop asserting ≤ ~4 calls (SC-005) and zero calls within each window
  (SC-006).
- Stale-without-key path surfaces the warning (SC-007); missing-timestamp → due (FR-018).
- Determinism: same inputs → same decision across repeats (FR-021).
