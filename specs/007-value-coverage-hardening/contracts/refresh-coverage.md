# Contract — EDGAR Coverage Refresh (CLI)

`backend/scripts/refresh_edgar_coverage.py` — offline, idempotent, resumable.

## Invocation

```bash
py -3.12 -m backend.scripts.refresh_edgar_coverage \
    [--scope screened|full] \
    [--limit N] \
    [--dry-run] \
    [--report PATH]
```

- `--scope screened` (default): only names in the current liquid screened
  universe; `full`: the entire `edgar_cache/`.
- `--dry-run`: classify and print the CoverageReport, fetch nothing.
- `--report PATH`: also write the JSON CoverageReport (default: stdout summary).

## Behaviour (MUST)

1. Classify every in-scope ticker (D1/D2) into the CacheEntryClassification.
2. Re-fetch SEC companyfacts only for `action = refetch` entries (fixable_stub or
   partial AND common_equity/unknown AND CIK resolvable), writing schema-v3
   payloads with `dei:EntityCommonStockSharesOutstanding` + value `NEEDED_TAGS`.
3. **Write-if-better**: never replace a `complete` payload with a smaller/empty
   one; on fetch failure keep the prior file and record in `refetch_failed`.
4. Throttle ≤ 8 req/s, exponential backoff on 429/5xx, descriptive User-Agent,
   no API key, nothing secret written to disk.
5. Resume safely if interrupted (progress is the cache itself; re-running skips
   now-complete entries).
6. Emit CoverageReport with `counts_before`/`counts_after` so the improvement is
   measurable (SC-001).

## Exit codes

- `0` — completed (even if some `refetch_failed`, which are reported).
- non-zero — only on unrecoverable error (e.g. cannot reach SEC at all).

## Determinism

Given the same cache state + SEC snapshot, classification and the resulting
CoverageReport are identical. The fetch itself depends on SEC's live data (a
later filing legitimately changes a payload); this is the only non-deterministic
input and is sourced + as-of stamped per Principle I.
