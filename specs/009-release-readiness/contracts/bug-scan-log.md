# Contract: Bug-scan findings log

Structure and gate rules for `specs/009-release-readiness/bug-scan-log.md`, the
tracked output of the deliberate bug scan (FR-013) and cleanup (FR-014).
Satisfies SC-007.

## Log entry shape

Each finding is one row:

| Field | Allowed values | Notes |
|-------|----------------|-------|
| `id` | `BUG-NNN` | Sequential. |
| `location` | free text | File / endpoint / flow. |
| `description` | free text | Defect + reproduction. |
| `severity` | `correctness` \| `integrity` \| `crash-hang` \| `minor` | First three = must-fix. |
| `resolution` | `fixed` \| `deferred-with-rationale` | `fixed` cites the commit/test; deferral cites a one-line reason. |

## Scope of the scan (bounded — FR-013, spec Assumptions)

Real runtime surfaces only:

- Endpoints: `/screen`, `/analyze`, candidate detail, advisor-prompt export,
  `/strategies/*`, `/portfolio`, `/data/refresh`, `/meta`, `/data/freshness`.
- Data loaders: prices store, EDGAR slim cache, calendars, manifest.
- Failure modes: source down, empty result, missing fundamentals, timeout.

## Gate rules

1. **Must-fix before release**: every finding with `severity` in
   {`correctness`, `integrity`, `crash-hang`} affecting a primary flow MUST be
   `fixed` before release. 0 may remain deferred (SC-007).
2. **Deferrable**: `minor`/cosmetic findings MAY be `deferred-with-rationale`
   with an explicit one-line justification.
3. **No untriaged findings**: 0 findings without a severity + resolution.
4. **Regression test**: every `fixed` finding adds or updates a test that fails
   before the fix and passes after.
5. **Cleanup constraint** (FR-014): dead-code / obsolete-artifact removal MUST NOT
   change any strategy rule, default, citation, or backtest baseline; the full
   suite stays green afterward (FR-015, SC-010).
