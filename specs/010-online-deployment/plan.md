# Implementation Plan: Online Deployment (Personal, Free)

**Branch**: `010-online-deployment` | **Date**: 2026-06-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/010-online-deployment/spec.md`

## Summary

Make the already-assembled, release-ready screener (feature 009) reachable over
the public internet for the **single owner**, while staying **free**,
**single-user**, and within the constitution. This is a **deployment / access**
feature — **no new strategy and no strategy rule, default, citation, or backtest
baseline change** (FR-013). It deliberately introduces the constitution's
*hosted* mode for the first time, so the hosted-clause obligations re-attach:
directive personal-use mode is **forced OFF and non-waivable** (FR-009), and
data-source + disclosure obligations are preserved (every response keeps
`data_as_of` + `disclaimer`, FR-008).

Three design decisions (clarified with the operator, see Phase 0) shape the whole
feature:

1. **Hosting topology — Render + Vercel (free tiers).** FastAPI backend runs as a
   Render free **web service** (sleeps after idle → accepted cold starts,
   FR-011); the Next.js frontend runs on **Vercel free**. Both expose
   platform-provided HTTPS URLs (FR-016); no custom domain required.
2. **Access gate — NextAuth (Auth.js) Google sign-in + single-email allowlist,
   fronting a BFF proxy.** The browser only ever talks to the Next app
   (same-origin); a NextAuth session gates every page and every API route.
   Server-side Next route handlers proxy to the backend, attaching a
   **process-local shared secret**; the backend rejects any request without it.
   So unauthenticated/non-owner traffic reaches **no** screener data, including
   direct hits to data endpoints (FR-002, FR-003, FR-015).
3. **Snapshot delivery — baked into the deployed backend artifact.** "Publish"
   means: refresh locally with the existing 009 pipeline, bundle the
   `backend/data` snapshot, build a new backend image with that snapshot layer,
   and deploy. The platform performs an **atomic** swap (old image serves until
   the new one is healthy), so the host **never serves a partial/corrupt
   snapshot** (FR-006) and performs **no heavy in-host ingest** (FR-004). Data
   stays read-only; refresh remains a local-then-republish operation (FR-005,
   FR-007).

Determinism is preserved end-to-end: the same published snapshot yields
byte-identical screen / regime / sizing / event / advisor-prompt output as the
local instance (FR-012, SC-004). Momentum stays primary; value stays postponed
(009 scope) but its existing tests still pass.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 15 + React 19 (frontend). No language change.
**Primary Dependencies**: Existing — FastAPI, Pydantic v2, pandas/numpy (backend); TanStack Query, Zod, Tailwind (frontend). **New (access layer only):** `next-auth` (Auth.js) Google provider on the frontend; no new backend runtime dependency (shared-secret check is stdlib + FastAPI dependency). Containerization via a backend `Dockerfile` (Render) — tooling, not a runtime lib.
**Storage**: Unchanged — SQLite (`catalog.db`) + partitioned Parquet prices, EDGAR slim cache, `backend/data/manifest.json`, calendars. The hosted instance serves this tree **read-only**, baked into the image. **No schema migration, no new store.**
**Testing**: pytest (backend; adds auth-gate + hosted-config + snapshot-integrity tests), Vitest (frontend unit; adds proxy/auth-guard + StartupFreshnessGate hosted-mode states), Playwright (e2e; adds owner-gate redirect + no-data-leak checks; existing no-directive lint + `data_as_of`/`disclaimer` presence stay green and now also run against the hosted-mode build).
**Target Platform**: Public web, free tier — **Render free web service** (backend, Docker, sleeps on idle) + **Vercel free** (Next.js frontend, NextAuth route handlers). Platform HTTPS URLs. Local single-user dev runbook unchanged (Windows: `py -3.12`, `npm.cmd`).
**Project Type**: Web application (backend + frontend) — existing repository layout, plus an access/proxy layer in the frontend and deployment manifests.
**Performance Goals**: Warm interactive state **< 3 s** on subsequent loads (SC-006); cold start after sleep returns a usable app with a loading state, no error page (SC-006, Edge Cases). Screen execution stays within the constitution's p95 ≤ 10 s on the snapshot. Startup freshness check stays ≤ 3 s (009, read-only).
**Constraints**: **Read-only host, no in-host ingest** (FR-004); **never serve partial/corrupt snapshot** (FR-006); **directive mode forced OFF, non-waivable** (FR-009); **secrets process-local/runtime only, never in repo or any deployed file** (FR-010, SC-008); **HTTPS only** (FR-016); **$0 within free-tier limits** (SC-005); **determinism preserved** (FR-012). Cold start / sleep acceptable but must not lose or corrupt data (FR-011).
**Scale/Scope**: Exactly one authorized user. Snapshot = the screened (liquid/compliant) universe the local instance already serves (~≤ 1,200-ticker refresh cap + EDGAR cache + precomputed `backtest_runs`); not the full deep Stooq archive (backtests are read from committed `backtest_runs`, not recomputed in-host).

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.1.0. Re-checked after Phase 1 design.*

| Principle | Verdict | Notes |
|-----------|---------|-------|
| **I. Data Integrity & Provenance** (NON-NEGOTIABLE) | ✅ Pass / re-attaches | Hosted mode re-attaches the "licensed/permissive provider" obligation (Principle V hosted clause + Data sources). The host serves **only the owner's own snapshot, accessed only by the owner, never redistributed** (FR-015, spec Assumptions) — no new data source, no scraping, no redistribution. Per-source `data_as_of`/provenance travels in the baked snapshot unchanged; `data_as_of` carried on every response (FR-008). Point-in-time integrity untouched (no in-host ingest, FR-004). |
| **II. Strategy Transparency** | ✅ Pass | No strategy rule, parameter default, ranking expression, or citation changes (FR-013). Strategy code is byte-identical to 009; the deployed artifact runs the same code. |
| **III. Reproducible Backtesting** (NON-NEGOTIABLE) | ✅ Pass | No backtest code or committed baseline change. Determinism is an explicit acceptance criterion: same snapshot → identical outputs incl. byte-identical advisor prompt (FR-012, SC-004). Backtests are served from committed `backtest_runs`, not recomputed in-host. |
| **IV. Test-First for Financial Logic** | ✅ Pass | No indicator/strategy logic added — the new code is access (auth gate, BFF proxy), config (hosted-mode flag forcing, snapshot path), and deployment manifests. These get their own tests (auth deny/allow, secret enforcement, directive-OFF forced, snapshot-integrity guard); the full 009 financial suite must stay green on the deployed code. |
| **V. No-Advice Boundary** (+ hosted clause) | ✅ Pass / enforced | This is the first hosted instance, so the Principle V hosted clause is **actively enforced**: `SCREENER_PERSONAL_USE_DIRECTIVE` is **forced OFF and non-waivable** regardless of env/config (FR-009); the Playwright no-directive lint runs against the hosted build (SC-007). Every response keeps `data_as_of` + `disclaimer` (FR-008). Auth/owner config + provider keys are process-local, never committed (FR-010, SC-008). Single-user, no redistribution, no anonymous access (FR-015). |

**Gate result: PASS — no violations.** Complexity Tracking is empty.

The single sensitive area is the hosted-mode directive clause; the design closes
it by *forcing* the flag off in code (not merely defaulting it), so no
environment misconfiguration can re-enable directive language on the public
instance.

## Project Structure

### Documentation (this feature)

```text
specs/010-online-deployment/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions + rationale (hosting, auth, snapshot, secrets, cold-start)
├── data-model.md        # Phase 1 — Data Snapshot, Authorized Owner Identity, Hosted Instance, Runtime Config/Secrets
├── quickstart.md        # Phase 1 — the deployment runbook (FR-014): stand up, publish, rebuild on free tier
├── contracts/
│   ├── auth-gate.md             # NextAuth Google + owner allowlist; session required for pages + API routes
│   ├── bff-proxy.md             # Next server-side proxy → backend; shared-secret header; no browser→backend path
│   ├── backend-owner-secret.md  # FastAPI dependency: reject requests lacking the shared owner secret
│   ├── snapshot-publish.md      # bake-into-artifact publish + atomic swap + integrity (no partial/corrupt) guard
│   └── hosted-mode-config.md    # forced directive-OFF, required runtime env, secret handling, HTTPS
├── checklists/
│   └── requirements.md  # (existing)
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
backend/src/
├── api/
│   ├── app.py            # MODIFY: register owner-secret dependency / middleware that gates ALL routers when
│   │                     #   hosted mode is on (rejects requests without the shared secret → no data leakage).
│   │                     #   CORS tightened to the deployed frontend origin in hosted mode.
│   └── (routers)         # UNCHANGED behavior; gated centrally so every data-bearing endpoint is covered (FR-003).
├── lib/
│   ├── flags.py          # MODIFY: personal_use_directive() returns False unconditionally when hosted mode is on
│   │                     #   (FR-009, non-waivable); add hosted_mode() + owner-secret config readers.
│   └── hosting.py        # NEW: hosted-mode detection + required-config validation (fail fast if a required
│                         #   secret is missing); read-only/snapshot-path resolution helper.
├── data/
│   └── (stores)          # REUSE: paths already resolve under backend/data; snapshot is the baked tree. No ingest.
└── (no strategy/indicator/backtest changes)

backend/tests/
├── api/                  # NEW: owner-secret gate (deny w/o secret across pages+data endpoints; allow w/ secret),
│                         #   hosted CORS, snapshot-integrity/maintenance-state behavior.
├── lib/                  # NEW: hosted_mode() forces directive OFF even if SCREENER_PERSONAL_USE_DIRECTIVE=1;
│                         #   required-config validation fails fast on missing secret.
└── (existing suites)     # MUST stay green on the deployed code (determinism, integrity, freshness).

frontend/
├── src/
│   ├── auth.ts                  # NEW: NextAuth (Auth.js) config — Google provider + single-owner email allowlist.
│   ├── middleware.ts            # NEW: require a valid owner session for all app routes + /api proxy routes;
│   │                            #   unauthenticated → sign-in (no screener data rendered).
│   ├── app/
│   │   ├── api/auth/[...nextauth]/route.ts   # NEW: NextAuth route handler.
│   │   └── api/proxy/[...path]/route.ts      # NEW: server-side BFF proxy → backend; injects X-Owner-Secret
│   │                                         #   (server-only env); never exposes backend URL/secret to browser.
│   ├── lib/api.ts               # MODIFY: API_BASE_URL → same-origin "/api/proxy" (browser never calls backend
│   │                            #   directly); add hosted-mode awareness; preserve existing error/retry shape.
│   └── components/
│       ├── StartupFreshnessGate.tsx  # MODIFY: in hosted mode, the "refresh" affordance explains refresh is
│       │                             #   performed locally + republished (no heavy in-host ingest) — FR-007.
│       └── DataFreshnessPanel.tsx    # MODIFY: same hosted-mode messaging.
└── tests/
    ├── unit (Vitest)           # NEW: proxy attaches secret server-side only; auth guard redirects; hosted
    │                           #   StartupFreshnessGate copy.
    └── e2e (Playwright)        # NEW: unauthenticated → no data (pages + /api/proxy/*); owner signed-in → full
                                #   access. EXISTING: no-directive lint + data_as_of/disclaimer presence run
                                #   against the hosted-mode build.

deployment (repository root):
├── backend/Dockerfile          # NEW: build the backend image WITH the baked read-only data snapshot layer.
├── render.yaml (or equivalent) # NEW: Render service manifest (backend web service; env = runtime secrets only).
├── .dockerignore / build script# NEW: control what enters the image; ensure NO secret/key files are bundled.
└── specs/010-online-deployment/quickstart.md  # the reproducible runbook (FR-014); README pointer updated.
```

**Structure Decision**: Existing web-app layout (backend + frontend). The feature
adds an **access layer** (NextAuth + BFF proxy + backend owner-secret gate), a
**hosted-mode config layer** (forced directive-OFF, required-secret validation),
and **deployment manifests** (backend `Dockerfile` with baked snapshot,
`render.yaml`, Vercel project config). It changes **no** strategy, indicator,
backtest, or screening logic — those modules run byte-identical to 009. The only
backend behavior change is *central gating* (reject unauthenticated requests in
hosted mode) and *forcing* directive-OFF; the only frontend behavior change is
*routing API traffic through a same-origin authenticated proxy* instead of
directly to the backend.

## Phase 0 — Research

See [research.md](research.md). Decisions (the three clarified with the operator
plus the derived design choices):

1. **Hosting topology = Render (backend) + Vercel (frontend), free tiers.**
   Both give HTTPS platform URLs and $0 operation; Render free web services sleep
   on idle (the accepted cold-start tradeoff, FR-011/SC-006); Vercel is the
   native, NextAuth-friendly Next.js host. Rejected: all-in-one Render (frontend
   loses Vercel's Next-native edge + simplest NextAuth path); Fly.io (more
   container/CLI overhead for the same $0 outcome).
2. **Access gate = NextAuth Google + single-email allowlist + BFF proxy.** The
   browser talks only to the same-origin Next app; a session is required for
   every page and every `/api/proxy/*` route; server-side route handlers attach a
   process-local shared secret the backend requires. This closes data-endpoint
   leakage (FR-003) without scattering token-verification across backend routers.
   Rejected: backend-verifies-Google-ID-token (backend stays publicly reachable;
   more auth code on the financial-logic surface; CORS-with-credentials
   complexity). Rejected: platform/Cloudflare Access (needs custom domain/DNS;
   spec says no custom domain).
3. **Snapshot delivery = baked into the deployed backend artifact, atomic swap.**
   No runtime mutation, no partial/corrupt window (old image serves until new is
   healthy → FR-006), fully reproducible from local (FR-005/FR-014), no extra
   bucket or credentials. Rejected: object storage + fetch-on-start (adds a
   bucket + access key, a download/verify step, and a partial-download failure
   mode the bake-in approach avoids).
4. **Directive-OFF is forced, not defaulted.** `personal_use_directive()` returns
   `False` whenever hosted mode is active, regardless of
   `SCREENER_PERSONAL_USE_DIRECTIVE` — so no env misconfiguration can re-enable
   directive language on the public instance (FR-009, constitution Principle V
   hosted clause).
5. **Secrets are runtime-only and validated at startup.** Owner email, Google
   OAuth client id/secret, NextAuth secret, and the backend owner-secret are
   supplied as platform environment variables; a fail-fast check refuses to serve
   if a required secret is missing (so the instance never comes up "open"). No key
   is committed or written to any file in the artifact (FR-010, SC-008); a repo +
   image scan is part of release verification.
6. **Read-only + no in-host ingest.** The hosted refresh affordance does not call
   heavy ingest; it surfaces staleness and explains that refresh is done locally
   and republished (FR-007). The existing `POST /data/refresh` heavy path is
   disabled/blocked in hosted mode (or simply unreachable behind the gate and
   documented as local-only).
7. **Determinism is unchanged** because the deployed code and the baked snapshot
   are identical to local; the proxy and auth layers do not touch computation.

## Phase 1 — Design & Contracts

See [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md).

- **Authorized Owner Identity** — the single Google account email on the
  allowlist; NextAuth admits only that email, denies all others (FR-002). Stored
  as a runtime env value, never committed.
- **Hosted Instance** — the running Render backend + Vercel frontend behind
  HTTPS, with hosted mode active (directive forced OFF, owner-secret gate on,
  CORS pinned to the frontend origin).
- **Data Snapshot** — the read-only `backend/data` bundle (prices Parquet,
  `catalog.db` incl. `backtest_runs`, EDGAR slim cache, calendars, `manifest.json`
  with per-source `data_as_of`) baked into the backend image; carries provenance;
  validated for completeness before the new image is marked healthy (FR-006).
- **Runtime Configuration / Secrets** — `SCREENER_HOSTED_MODE`, the backend
  owner-secret, NextAuth/Google client id+secret+session secret, allowed owner
  email, and the backend URL the proxy targets — all platform env vars, never in
  the repo or the deployed files.
- **Auth-gate contract** (`contracts/auth-gate.md`): session required for all
  routes; non-owner email denied; unauthenticated → sign-in with no data.
- **BFF-proxy contract** (`contracts/bff-proxy.md`): browser → same-origin
  `/api/proxy/*` only; server attaches `X-Owner-Secret`; backend URL + secret
  never reach the client.
- **Backend-owner-secret contract** (`contracts/backend-owner-secret.md`): a
  FastAPI dependency/middleware rejects any request lacking the shared secret in
  hosted mode → 401/403 with no screener data, across **all** routers (FR-003).
- **Snapshot-publish contract** (`contracts/snapshot-publish.md`): publish =
  local refresh → bundle → image build → atomic deploy; health check verifies the
  manifest/stores before cutover; partial/missing snapshot → explicit
  maintenance/empty state, last-good image keeps serving (FR-006).
- **Hosted-mode-config contract** (`contracts/hosted-mode-config.md`): directive
  forced OFF and non-waivable; required-secret fail-fast; HTTPS only; CORS pinned.
- **Robustness** — cold start shows a loading state and recovers (no error page);
  empty screen → explicit empty-state (009, preserved); these run against the
  hosted build.

**Agent context update**: the `<!-- SPECKIT START -->…<!-- SPECKIT END -->`
pointer in `CLAUDE.md` is repointed to this plan.

## Complexity Tracking

No constitution violations — none required.
