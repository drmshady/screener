# Contract: Deployment runbook

Required contents and acceptance for the deployment runbook
(`specs/009-release-readiness/quickstart.md`, mirrored into README "Run
Locally"). Satisfies FR-020–FR-023, SC-009.

## Required sections

1. **Prerequisites** — Python 3.12 (`py -3.12`), Node + `npm.cmd`, presence of
   the data directories.
2. **Backend bring-up** — editable install of `backend[dev]`; data seed/refresh
   (incremental ingest); start uvicorn on a fixed host/port.
3. **Frontend production build** — `npm run build` then `npm run start` (Next
   **production** mode for headless), with `NEXT_PUBLIC_API_URL` provided **at
   runtime**, never baked into the build.
4. **Configuration** — data directory locations (prices store, EDGAR slim cache,
   `manifest.json`, calendars); optional provider keys supplied
   **process-local/inline only**, never written to a file (FR-022).
5. **Smoke verification** — exercise the primary flows (screen → candidate detail
   → advisor-prompt export → portfolio) and confirm behavior matches the
   test-validated build (FR-021).
6. **Finalization** — commit the working tree on `009-release-readiness` with the
   suite green (FR-023).

## Acceptance (tests / manual)

1. **Zero missing/incorrect steps** (SC-009): a first-time follow on a clean
   environment reaches a running production build without manual fixes.
2. **Production parity** (FR-021): the built app serves the same behavior the
   suites validate for the primary flows.
3. **Key handling** (FR-022): the runbook demonstrates process-local key supply
   and explicitly states keys are never written to any file
   (consistent with the existing convention).
4. **Known-good commit** (FR-023): finalization step leaves the branch
   suite-green and committed.
