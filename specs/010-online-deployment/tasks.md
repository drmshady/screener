---
description: "Task list for feature 010 â€” Online Deployment (Personal, Free)"
---

# Tasks: Online Deployment (Personal, Free)

**Input**: Design documents from `specs/010-online-deployment/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (auth-gate, bff-proxy, backend-owner-secret, snapshot-publish, hosted-mode-config), quickstart.md

**Tests**: INCLUDED. The plan's Testing section and Constitution Principle IV
explicitly require new tests for the access/config layer (auth deny/allow,
owner-secret enforcement, forced directive-OFF, snapshot integrity, proxy/auth
guard). The full 009 financial suite must stay green on the deployed code.

**Scope guardrail (FR-013)**: This feature changes **no** strategy rule, default,
citation, indicator, or backtest baseline. All tasks are access-layer, hosted-mode
config, robustness, or deployment manifests. Computation paths stay byte-identical
to 009.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4 (maps to spec.md user stories)
- Paths are repo-relative: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Bring in the only new dependency and scaffold the hosted-mode module.

- [X] T001 Add `next-auth` (Auth.js) to `frontend/package.json` dependencies and update the lockfile via `npm.cmd install` (no other dependency changes).
- [X] T002 [P] Scaffold `backend/src/lib/hosting.py` with module docstring and signatures/stubs for `hosted_mode()`, `owner_secret()`, `snapshot_root()`, and `require_hosted_config()` (no logic yet).
- [X] T003 [P] Create `backend/tests/lib/` and `frontend/tests/unit/` directories (with `__init__.py` where needed) if absent, to hold the new hosted-mode/auth tests.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Hosted-mode detection, forced directive-OFF, and fail-fast secret
validation. **Every user story depends on this.**

**âš ï¸ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational (write first, ensure they FAIL)

- [X] T004 [P] Write `backend/tests/lib/test_hosting.py`: `hosted_mode()` reflects `SCREENER_HOSTED_MODE`; `require_hosted_config()` raises when hosted mode is on and `SCREENER_OWNER_SECRET` is unset/empty; passes when present (fail-fast, no open boot).
- [X] T005 [P] Write `backend/tests/lib/test_flags_hosted.py`: `personal_use_directive()` returns `False` when hosted mode is on **even with** `SCREENER_PERSONAL_USE_DIRECTIVE=1` set (FR-009, non-waivable); unchanged behavior when hosted mode is off.

### Implementation for Foundational

- [X] T006 Implement hosted-mode detection + config readers + fail-fast validation in `backend/src/lib/hosting.py` (`hosted_mode()` from `SCREENER_HOSTED_MODE`; `owner_secret()`; `snapshot_root()` resolving the read-only `backend/data` tree; `require_hosted_config()` raising on missing required secret).
- [X] T007 Modify `backend/src/lib/flags.py` so `personal_use_directive()` returns `False` unconditionally when `hosting.hosted_mode()` is on, ignoring `SCREENER_PERSONAL_USE_DIRECTIVE` (FR-009; import from `lib/hosting`).
- [X] T008 [P] Add `frontend/src/lib/config.ts`: hosted-mode awareness + server-only readers for `BACKEND_BASE_URL` and `SCREENER_OWNER_SECRET` (must NOT be `NEXT_PUBLIC_*`), and `SCREENER_HOSTED_MODE`.

**Checkpoint**: Hosted-mode config is enforceable and fail-fast; directive is provably forced OFF. User stories can now begin.

---

## Phase 3: User Story 2 - Only the owner can get in (Priority: P1) ðŸŽ¯ MVP-critical

**Goal**: The public instance admits only the single authorized owner; everyone
else (unauthenticated or non-owner) reaches **no** screener data, including direct
hits to data endpoints.

**Independent Test**: From an unauthenticated session and from a non-owner Google
session, attempt any page and `/api/proxy/*` data endpoint â†’ denied, no data; then
sign in as the owner â†’ access granted. Direct-hit the backend without the secret â†’
401/403.

> US2 is sequenced before US1 because exposing the app publicly without the access
> gate would leak data (spec: "Security is non-negotiable the moment it is public").

### Tests for User Story 2 (write first, ensure they FAIL)

- [X] T009 [P] [US2] Write `frontend/tests/unit/auth-signin.test.ts` (Vitest): NextAuth `signIn` callback admits a session only when the Google profile email is verified AND equals `SCREENER_OWNER_EMAIL` (case-insensitive); denies any other email.
- [X] T010 [P] [US2] Write `backend/tests/api/test_owner_secret_gate.py`: hosted mode + missing/wrong `X-Owner-Secret` â†’ 401/403 with no screener data on representative data endpoints (strategies, candidates, data, regime); correct secret â†’ normal response; hosted mode + missing `SCREENER_OWNER_SECRET` env â†’ app refuses to start; local mode (hosted OFF) â†’ gate inactive, unchanged.
- [X] T011 [P] [US2] Write `backend/tests/api/test_hosted_cors.py`: in hosted mode `allow_origins` is pinned to the deployed frontend origin only (not the localhost list).
- [X] T012 [P] [US2] Write `frontend/tests/e2e/owner-gate.spec.ts` (Playwright): unauthenticated â†’ redirected to sign-in with zero screener data on pages and `/api/proxy/*`; non-owner session â†’ denied; owner session â†’ full app.

### Implementation for User Story 2

- [X] T013 [US2] Create `frontend/src/auth.ts`: NextAuth (Auth.js) config with Google provider and the single-owner `signIn` allowlist callback (verified email == `SCREENER_OWNER_EMAIL`, case-insensitive); fail-closed if `AUTH_GOOGLE_ID`/`AUTH_GOOGLE_SECRET`/`AUTH_SECRET`/`SCREENER_OWNER_EMAIL` missing.
- [X] T014 [US2] Create `frontend/src/app/api/auth/[...nextauth]/route.ts` NextAuth route handler wired to `auth.ts`.
- [X] T015 [US2] Create `frontend/src/middleware.ts`: require a valid owner session for all app routes and all `/api/proxy/*` routes; unauthenticated â†’ redirect to sign-in with no SSR data and no proxied call; allow only `/api/auth/*` and static assets unauthenticated.
- [X] T016 [US2] Add the backend owner-secret gate in `backend/src/api/app.py`: a dependency/middleware applied to **all routers** that, when `hosting.hosted_mode()` is on, requires `X-Owner-Secret` to equal `SCREENER_OWNER_SECRET` (constant-time compare) â†’ else 401/403 with no screener data; call `require_hosted_config()` at startup for fail-fast.
- [X] T017 [US2] In `backend/src/api/app.py`, pin CORS `allow_origins` to the deployed frontend origin (from env) when hosted mode is on; keep the localhost list when off.

**Checkpoint**: The public surface is closed â€” only the owner gets data; backend rejects any request lacking the secret.

---

## Phase 4: User Story 1 - Use the screener from anywhere (Priority: P1) ðŸŽ¯ MVP

**Goal**: The signed-in owner opens the hosted URL from any device (even one that
never ran the project), runs a momentum screen, and gets the same candidates,
levels, gates, regime, freshness, `data_as_of`, and disclaimer as locally â€” with a
graceful cold-start/loading and empty state.

**Independent Test**: From a fresh remote device, open the hosted URL, sign in as
owner, run `midterm_52w_high_momentum`; candidates render with levels, gates,
per-source freshness, `data_as_of`, disclaimer, zero directive language.

### Tests for User Story 1 (write first, ensure they FAIL)

- [X] T018 [P] [US1] Write `frontend/tests/unit/proxy-route.test.ts` (Vitest): the BFF proxy forwards method/path/query/JSON body, injects `X-Owner-Secret` server-side, strips hop-by-hop headers, and returns backend status/body unchanged (preserving `data_as_of`/`disclaimer` and `ApiError` retry semantics); `BACKEND_BASE_URL` and secret never appear in client-visible output.
- [X] T019 [P] [US1] Write `backend/tests/api/test_hosted_determinism.py`: for a fixed snapshot, hosted-mode (gated) screen output ordering and the advisor-prompt export are byte-identical to the ungated local path (FR-012, SC-004).
- [X] T020 [P] [US1] Write `frontend/tests/e2e/hosted-usable.spec.ts` (Playwright, hosted-mode build): owner signed in â†’ momentum screen renders candidates with levels/gates/freshness/`data_as_of`/disclaimer; empty screen â†’ explicit empty-state (not error/blank); transient backend unreachability shows a loading state, not an error page.

### Implementation for User Story 1

- [X] T021 [US1] Create `frontend/src/app/api/proxy/[...path]/route.ts`: server-side BFF handler that requires the owner session, forwards method/path/query/JSON body to `${BACKEND_BASE_URL}/<path>`, injects `X-Owner-Secret`, strips hop-by-hop headers, sets `Content-Type: application/json`, and returns the backend status/body unchanged.
- [X] T022 [US1] Modify `frontend/src/lib/api.ts`: flip `API_BASE_URL` to same-origin `'/api/proxy'`; preserve existing `fetchApi`/Zod call sites and `ApiError.retryable` (5xx/408/429) semantics; ensure the browser never references the backend URL/secret.
- [X] T023 [P] [US1] Modify `frontend/src/components/StartupFreshnessGate.tsx`: in hosted mode the refresh affordance explains refresh is performed **locally and republished** (no heavy in-host ingest) and still offers "proceed on cached data" (FR-007); keep cold-start loading state (no error page).
- [X] T024 [P] [US1] Modify `frontend/src/components/DataFreshnessPanel.tsx`: same hosted-mode "refresh is local-then-republish" messaging.
- [X] T025 [US1] Create the backend `backend/Dockerfile` (Python 3.12 base) that copies the app and runs uvicorn, exposing the health-check path; create root `render.yaml` (or equivalent) declaring the Render free Docker web service with env = runtime secrets only (no secret values committed).
- [X] T026 [P] [US1] Create `frontend/vercel.json` / project config and document the Vercel root = `frontend/`; confirm a production build runs headless (per Windows dev runbook) so the hosted build is testable.

**Checkpoint**: A signed-in owner can run a screen end-to-end through the same-origin proxy with identical output to local; US1 + US2 both work.

---

## Phase 5: User Story 3 - Publish fresh data from local (Priority: P2)

**Goal**: The owner refreshes data locally, bakes it into a new backend image, and
the hosted app serves the fresher snapshot read-only â€” never a partial/corrupt one
â€” clearly showing how current it is.

**Independent Test**: Note hosted `data_as_of`; refresh locally + republish; reload
â†’ `data_as_of` advances. Interrupt a publish â†’ last good snapshot or explicit
maintenance/empty state, never partial.

### Tests for User Story 3 (write first, ensure they FAIL)

- [X] T027 [P] [US3] Write `backend/tests/api/test_snapshot_integrity.py`: the health check (`/data/freshness` or `/health`) validates that `manifest.json` parses and key stores (prices parquet, `catalog.db`, EDGAR cache, calendars) are present; missing/partial snapshot â†’ explicit maintenance/empty state, never a partial/corrupt response (FR-006).
- [X] T028 [P] [US3] Write `backend/tests/api/test_refresh_blocked_hosted.py`: in hosted mode the heavy `POST /data/refresh` ingest path is disabled/blocked (read-only host, FR-004); `GET /data/freshness` still runs.

### Implementation for User Story 3

- [X] T029 [US3] Extend `backend/Dockerfile` to bake the snapshot scope as a read-only layer (`prices/parquet/**`, `catalog.db` incl. `backtest_runs`, EDGAR slim cache, calendars, `manifest.json`); add root `.dockerignore` + explicit copy list so **only** snapshot/data files enter the image and **no** key/secret file is bundled (FR-010, SC-008).
- [X] T030 [US3] Add/confirm a backend health check that validates manifest + key stores before the platform marks the image healthy (atomic swap: old image serves until new passes), in `backend/src/api/app.py` (or a small `/health` route); wire Render `healthCheckPath` to it in `render.yaml`.
- [X] T031 [US3] Block the heavy ingest path in hosted mode in `backend/src/api/data.py`: `POST /data/refresh` returns a clear "refresh is local-only / republish" response when `hosting.hosted_mode()` is on; `GET /data/freshness` stays read-only and active.
- [X] T032 [US3] Ensure the no-valid-snapshot path renders an explicit maintenance/empty state end-to-end (backend signals it; frontend shows it, not an error/blank page) â€” reuse the 009 empty-state handling.

**Checkpoint**: Republishing advances `data_as_of`; a partial/corrupt publish is never served.

---

## Phase 6: User Story 4 - Reproducible free deployment (Priority: P3)

**Goal**: The owner can stand up, publish to, and rebuild the instance on a free
tier by following the runbook, with all secrets supplied at runtime and none in the
repo or artifact.

**Independent Test**: On a clean free-tier account, follow the runbook end-to-end â†’
running, owner-gated instance serving a published snapshot, no undocumented steps.

### Tests for User Story 4 (write first, ensure they FAIL)

- [X] T033 [P] [US4] Add a secret-scan verification (script `scripts/secret_scan.ps1` or a test) that scans the repo and the assembled image's copy list for provider keys / owner secrets and fails on any hit (SC-008); include it as a release check.

### Implementation for User Story 4

- [X] T034 [US4] Finalize `specs/010-online-deployment/quickstart.md` as the authoritative runbook (one-time Google OAuth + secret generation, publish-snapshot, deploy backendâ†’Render + frontendâ†’Vercel, smoke verification, rebuild/restore) â€” verify every step is reproducible with no undocumented manual action (FR-014, SC-009).
- [X] T035 [P] [US4] Update `README.md` to point to the 010 deployment runbook and note hosted-mode constraints (read-only host, single-user, directive forced OFF); do not include any secret values.
- [X] T036 [US4] Verify all required runtime env vars are documented exactly once (backend Render set + frontend Vercel server-only set per `hosted-mode-config.md`) and that nothing in the repo or deployed files contains a secret value (cross-check with T033).

**Checkpoint**: A clean free-tier account can reproduce the running, owner-gated instance from the runbook alone.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Prove the deployed code is correct, deterministic, leak-free, and that
nothing regressed.

- [X] T037 Run the existing Playwright no-directive lint and the `data_as_of`/`disclaimer`-presence checks against the **hosted-mode build**; confirm both pass (SC-007, FR-008). **DONE**: hosted-mode `owner-gate` + `hosted-usable` specs 5/5 green (owner screen-run renders candidates + `data_as_of` + canonical disclaimer + freshness + zero directive language); default-mode `no-directive-copy` + `disclaimer-everywhere` 16/16 green. Fixed two over-specified 010 e2e assertions in `hosted-usable.spec.ts` (loading affordance is the `Running...` button label; UI renders the canonical disclaimer, not the per-response `disclaimer` field verbatim).
- [~] T038 Run the full backend pytest suite and frontend Vitest + Playwright on a clean checkout in hosted-mode config; confirm 0 silently-skipped financial-logic tests and the 009 determinism/integrity/freshness suites stay green on the deployed code. **010 deployed code GREEN**: all 010 access-layer + 009 determinism/integrity/freshness/robustness suites pass (41/41 targeted; all `api` tests pass), frontend Vitest 21/21, hosted/lint e2e green. **Caveat — 7 pre-existing, non-010 backend failures** (do NOT block on 010; FR-013 forbids touching strategy/backtest code to "fix" them): (a) 5 `validation/` tests fail only inside the full session due to **in-process state pollution from the offline `contract` (OpenAPI/Schemathesis) fuzz suite** — they pass in isolation (`8 passed`) and in `api+validation` (`42 passed`); the corruption does not persist to disk; (b) 2 tests (`integration/test_perf.py`, `contract` `GET /candidates/{ticker}`) hardcode reference ticker **HFRO, which has dropped out of the current SPUS-derived compliant universe (586 names)** — data drift. Both causes are unchanged by the 010 access-layer diff (the only momentum change is an added post-hoc integrity invariant that cannot affect `rules()` selection). Run from the repo root (`py -3.12 -m pytest`) per README/009 quickstart, not from `backend/`.
- [X] T039 [P] Run the secret scan (T033) over the repo + assembled image and inspect the built browser bundle/network to confirm the backend URL and owner secret are absent (SC-008). **DONE**: `scripts/secret_scan.ps1` PASSED (repo + 13-path image copy list, zero findings). Static bundle-leak check: `BACKEND_BASE_URL` + `SCREENER_OWNER_SECRET` are read only in server-only `frontend/src/lib/config.ts` (no `NEXT_PUBLIC_` prefix → never bundled to the browser); the only `NEXT_PUBLIC_` reference is the non-secret hosted-mode flag. Live deployed-bundle/network tab inspection remains part of T041.
- [X] T040 [P] Repoint the `<!-- SPECKIT START -->â€¦<!-- SPECKIT END -->` pointer in `CLAUDE.md` to `specs/010-online-deployment/plan.md` (if not already) and confirm the agent-context summary reflects 010. **DONE**: pointer already targeted 010; added a `## Active feature: 010-online-deployment` summary section and demoted 009 to `## Prior feature`.
- [~] T041 Execute the `quickstart.md` smoke verification (Section D) against a live deploy: owner access, deny non-owner/unauthenticated incl. direct backend hit, fresh-snapshot advance, determinism (byte-identical advisor prompt), cold-start usable, directive forced OFF. **LOCAL EVIDENCE RE-RUN 2026-06-19; live cloud round-trip BLOCKED — operator action** (requires a real Render+Vercel deploy and a Google OAuth client; no cloud accounts/credentials in this environment). Freshly executed this session against the local hosted-mode build: D.7 `secret_scan.ps1` → exit 0, zero findings; D.2 deny non-owner/unauthenticated + direct-hit 401/403 → `owner-gate.spec` 3/3 + `test_owner_secret_gate` (in 16/16 backend hosted suites); D.4 byte-identical advisor prompt → `test_hosted_determinism`; D.6 directive forced OFF → `test_flags_hosted` + hosted-usable directive-count-0; D.1 owner run → `hosted-usable` owner-flow; D.5 cold-start/empty usable → `hosted-usable` empty-state. Backend hosted suites 16/16; hosted e2e 5/5. **Remaining for operator only**: live cloud round-trip (real cold start, Vercel URL, Google sign-in) and D.3 republish-advances-`data_as_of` after a real B+redeploy.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies â€” start immediately.
- **Foundational (Phase 2)**: Depends on Setup â€” **blocks all user stories** (hosted-mode detection, forced directive-OFF, config readers).
- **US2 (Phase 3, P1)**: Depends on Foundational. Sequenced first among stories (security gate before public exposure).
- **US1 (Phase 4, P1)**: Depends on Foundational; integrates with US2 (the proxy injects the secret US2's backend gate requires, and reuses the US2 session guard). Best done after US2.
- **US3 (Phase 5, P2)**: Depends on Foundational; extends the `Dockerfile` first created in US1 (T025 â†’ T029) and the app health/data routes.
- **US4 (Phase 6, P3)**: Depends on US1â€“US3 manifests/behavior existing to document and verify them.
- **Polish (Phase 7)**: Depends on all targeted stories being complete.

### Within Each User Story

- Tests are written first and must FAIL before implementation.
- Backend gate/config before frontend routing that relies on it.
- Story complete and independently testable before moving to the next priority.

### Parallel Opportunities

- Setup: T002 and T003 are [P].
- Foundational tests T004/T005 are [P]; impl T006/T007 are sequential (same concern, flags imports hosting), T008 is [P].
- US2 tests T009â€“T012 are all [P] (different files). Impl: T013â†’T014â†’T015 (frontend auth chain), T016/T017 backend (T017 after T016, same file `app.py`).
- US1 tests T018â€“T020 are [P]. Impl: T023/T024/T026 are [P]; T021â†’T022 sequential-ish (api.ts targets the proxy route).
- US3 tests T027/T028 are [P].
- Polish: T039/T040 are [P].

---

## Parallel Example: User Story 2

```text
# Launch all US2 tests together (different files, all should FAIL first):
Task: "Vitest signIn allowlist in frontend/tests/unit/auth-signin.test.ts"
Task: "Owner-secret gate in backend/tests/api/test_owner_secret_gate.py"
Task: "Hosted CORS pin in backend/tests/api/test_hosted_cors.py"
Task: "Playwright owner-gate in frontend/tests/e2e/owner-gate.spec.ts"
```

---

## Implementation Strategy

### MVP First (US2 + US1 â€” both P1)

1. Phase 1 Setup â†’ Phase 2 Foundational (forced directive-OFF + fail-fast config).
2. Phase 3 US2: close the public surface (auth gate + backend owner-secret).
3. Phase 4 US1: route the app through the authenticated same-origin proxy; verify identical-to-local output.
4. **STOP and VALIDATE**: owner runs a screen remotely; non-owner/unauthenticated get nothing. Deploy the MVP.

### Incremental Delivery

1. Foundational â†’ US2 â†’ US1 = the deployable, secure MVP (remote use, owner-only).
2. Add US3 â†’ fresh-data publish via baked snapshot + never-serve-partial.
3. Add US4 â†’ reproducible runbook + secret-scan release verification.
4. Polish â†’ hosted-build lint, full-suite green, leak scan, runbook smoke.

---

## Notes

- [P] = different files, no dependency on an incomplete task.
- Every task is access-layer / hosted-config / robustness / deployment â€” **no** strategy, indicator, or backtest change (FR-013); the 009 financial suite must stay green on the deployed code.
- Secrets are runtime env only â€” never commit a value or write one to any file in the artifact (FR-010, SC-008).
- Commit after each task or logical group; stop at any checkpoint to validate the story independently.
