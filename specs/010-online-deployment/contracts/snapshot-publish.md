# Contract: Snapshot Publish (bake-into-artifact + atomic swap)

**Layer**: Deployment (backend `Dockerfile` + build/deploy). **Satisfies**:
FR-004, FR-005, FR-006, FR-011, FR-012.

## Publish flow (from local)

1. **Refresh locally** with the existing 009 pipeline (seed/ingest/refresh) so
   `backend/data` holds a fresh, complete snapshot.
2. **Bundle** the snapshot scope: `prices/parquet/**`, `catalog.db` (incl.
   `backtest_runs`), EDGAR slim cache, calendars, `manifest.json`. **Exclude** any
   key/secret file (enforced by `.dockerignore` + explicit copy list).
3. **Build** a new backend image with the snapshot as a layer.
4. **Deploy** to Render. The platform performs an **atomic swap**: the new image
   takes traffic **only after** the health check passes; the prior image keeps
   serving until then.

## Read-only / no in-host ingest

- The image is immutable at runtime; nothing writes to the data tree (FR-004).
- The heavy `POST /data/refresh` ingest path is **disabled/blocked** in hosted
  mode; `GET /data/freshness` still runs (read-only) and the UI explains refresh
  is done **locally and republished** (FR-007).

## Integrity (never serve partial/corrupt)

- **Health check** (backend `/health` or `/data/freshness`) validates the
  manifest parses and key stores are present before cutover. A staged image that
  fails health does **not** receive traffic (FR-006).
- If **no** valid snapshot is available at all, the app shows an explicit
  **maintenance/empty state**, never an error/blank page or a partial snapshot.

## Acceptance

| Given | When | Then |
|---|---|---|
| Newer snapshot published from local | owner reloads hosted app | `data_as_of` advances to the new snapshot (SC-003) |
| Publish interrupted / partial image | owner loads app | last good snapshot still served, or explicit maintenance state (FR-006) |
| Same snapshot bytes local vs hosted | identical screen | identical ordering + byte-identical advisor prompt (FR-012, SC-004) |
| Free instance suspended/reset | re-run runbook + redeploy image | instance restored, no data loss (FR-011) |

## Notes

- Snapshot scope deliberately excludes the full deep Stooq archive: hosted
  backtests are served from committed `backtest_runs`, not recomputed in-host.
