# Contract: Daily Automation (US1, FR-001…006)

**Surface:** a scheduled **GitHub Actions** workflow (`.github/workflows/daily-refresh.yml`)
running unattended in cloud CI. No app-runtime API change.

## Schedule & trigger

- Cron fires after the US market close on weekdays (UTC). `workflow_dispatch` also
  allowed for manual runs.
- **Trading-day / new-session guard first:** resolve the latest completed trading
  session from the existing calendar. If it is **not newer** than the currently
  published `data_as_of`, the run is a **documented no-op** — no refresh, build,
  push, or rebuild — and exits success (FR-005). Non-trading days cost ~nothing.

## Steps (reuse the existing publish chain; one shared codepath)

Ordered, **abort-before-publish** on any failure:

1. **Incremental refresh only** — `ingest_daily` (prices + events + Shariah +
   fundamentals on current cadence). The heavy Stooq deep-history bundle is **not**
   on this daily path (separate infrequent job). Append-only delta; reuse EDGAR
   slim cache + event-store memoization (efficiency requirement).
2. **Data-integrity checks (008)** — must pass.
3. **Release secret scan** — must pass; no secret ever written to an artifact
   (FR-002a/006, SC-008).
4. **Build** the backend image (snapshot baked in) — only when the snapshot
   changed.
5. **Push** to GHCR.
6. **Factory-rebuild** the HF Space (`POST .../restart?factory=true`) so it
   re-pulls `:latest` and serves the fresher snapshot.

## Secrets

- Provider keys, GHCR push credential, and the HF deploy token live **only** in the
  Actions encrypted secret store, injected at runtime. Never committed; never
  written into the image or any file (FR-002a/006). The secret scan still gates the
  publish.

## Outcomes

| Condition | Result |
|-----------|--------|
| No new completed session | `noop`; nothing published; `data_as_of` unchanged. |
| All steps pass | New snapshot published + Space rebuilt; `data_as_of` advances (FR-003). |
| Any step fails | **Abort before publish/deploy**; last known-good snapshot stays live; owner **notified** with the failing step (FR-004). |

## Guarantees

- Never serves a partial/corrupt snapshot (atomic image swap, 010 preserved).
- Host runs **no** ingest; only the CI job ingests (FR-001a).
- Snapshot is byte-equivalent to what the local pipeline would produce for the same
  session (determinism, FR-001a/FR-012-equivalent).
- Idempotent: re-running for the same session does not regress `data_as_of` or
  produce a spurious deploy (FR-005).

## Tests

- Guard short-circuits on a non-trading-day / no-new-session input (no build/push).
- A simulated failed step aborts before publish and triggers notification.
- Workflow YAML lints; secrets referenced only via `${{ secrets.* }}`.
