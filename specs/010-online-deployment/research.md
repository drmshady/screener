# Phase 0 Research: Online Deployment (Personal, Free)

All decisions resolve the spec's implied unknowns (hosting target, access
mechanism, snapshot delivery, secret handling, cold-start behavior). The three
headline choices were confirmed with the operator; the rest are derived.

---

## Decision 1 — Hosting topology: Render (backend) + Vercel (frontend), free tiers

**Decision**: Deploy the FastAPI backend as a **Render free web service** (Docker)
and the Next.js frontend on **Vercel free**. Both expose platform-provided HTTPS
URLs; no custom domain.

**Rationale**:
- Both are $0 within free-tier limits (SC-005) and provide HTTPS by default
  (FR-016).
- Render free web services **sleep after idle** and cold-start on the next
  request — exactly the accepted tradeoff in the spec (FR-011, SC-006, Edge
  Cases). No data is lost on sleep because the snapshot is baked into the image.
- Vercel is the native Next.js 15 host and the simplest place to run NextAuth
  (Auth.js) route handlers + middleware; its edge/CDN makes warm loads < 3 s
  (SC-006) trivial.
- Clean separation lets the BFF proxy live on Vercel (same-origin as the browser)
  and the backend stay private behind the shared secret.

**Alternatives considered**:
- *All-in-one on Render* — workable, but the frontend loses Vercel's Next-native
  build/edge and the simplest NextAuth path; two Render services that both sleep
  add a second cold-start surface for no benefit.
- *Fly.io single app* — equal $0 outcome but more Docker/flyctl overhead and
  machine config for a one-operator tool.

---

## Decision 2 — Access gate: NextAuth Google + single-email allowlist + BFF proxy

**Decision**: Gate the app with **NextAuth (Auth.js)** Google sign-in restricted
to a **single owner email allowlist**. The browser talks only to the same-origin
Next app; **server-side route handlers proxy** all API traffic to the backend and
attach a **process-local shared owner secret**. The backend **requires that
secret** on every request.

**Rationale**:
- Satisfies FR-002 (single authorized identity) and FR-003 (no pre-sign-in data
  leakage, including direct hits to data endpoints) at two layers: the Next
  middleware blocks unauthenticated page/route access, and the backend secret
  blocks anything that bypasses the frontend.
- The browser never learns the backend URL or the secret (both server-only env on
  Vercel), so there is no direct browser→backend path to leak data.
- Centralizes auth at the edge instead of scattering token verification across
  every FastAPI router — keeps the financial-logic surface untouched (Principle
  IV) and the change purely access-layer.
- Google is the operator's existing identity provider (spec Assumptions); a
  single-email allowlist is the minimum viable owner gate.

**Alternatives considered**:
- *Backend verifies Google ID token per request* — leaves the backend publicly
  reachable, adds JWT-verification + JWKS-refresh code on the backend, and needs
  CORS-with-credentials. More attack surface, more code on the wrong layer.
- *Cloudflare Access / platform SSO in front* — strong and near-zero app code,
  but typically needs a custom domain/DNS in front of the origins; the spec
  explicitly does **not** require (and scopes out) a custom domain.

**Implementation notes**:
- `frontend/src/lib/api.ts` `API_BASE_URL` flips from the public backend URL to
  the same-origin `/api/proxy` base; existing error/retry semantics preserved.
- The proxy forwards method, path, query, and JSON body; injects `X-Owner-Secret`;
  strips hop-by-hop headers; returns the backend status/body unchanged so the
  disclaimer/`data_as_of` middleware output is preserved.

---

## Decision 3 — Snapshot delivery: baked into the deployed backend artifact

**Decision**: "Publish data" = refresh locally with the existing 009 pipeline,
bundle the `backend/data` snapshot, **build a new backend image with the snapshot
as a layer**, and deploy. The platform performs an **atomic swap** (old image
serves until the new one passes health check).

**Rationale**:
- **No partial/corrupt window** (FR-006): the running container always holds a
  complete, immutable snapshot; the new image only takes traffic after a health
  check that validates the manifest + key stores.
- **No in-host ingest / read-only** (FR-004): the image is immutable; nothing
  writes to the data tree at runtime.
- **Reproducible** (FR-005, FR-014): rebuilding from the runbook with a fresh
  local snapshot reproduces the instance exactly; a suspended/reset free instance
  is restored by re-deploying the image — no data loss because data is
  reproducible locally.
- **No extra credentials/dependency**: avoids an object-storage bucket + access
  key and the network/partial-download failure mode at cold start.

**Alternatives considered**:
- *Object storage (R2/B2) + fetch-on-start* — decouples data from code and avoids
  image rebuilds, but adds a bucket, a process-local access key, a
  download-and-verify step on every cold start, and a partial-download failure
  mode the bake-in approach structurally avoids. Not worth it for a single
  operator publishing occasionally.

**Implementation notes**:
- The snapshot scope is the **screened universe** the local app already serves
  plus `catalog.db` (incl. precomputed `backtest_runs`), EDGAR slim cache,
  calendars, and `manifest.json` — **not** the full deep Stooq archive, since
  hosted backtests are read from committed `backtest_runs`, not recomputed.
- A `.dockerignore` + an explicit copy list ensure **only** data files (never any
  key/secret file) enter the image (FR-010, SC-008).
- A pre-build/CI **secret scan** over the repo and the assembled image verifies no
  provider key or owner secret is present (SC-008).

---

## Decision 4 — Directive personal-use mode is *forced* OFF, not merely defaulted

**Decision**: When hosted mode is active, `lib/flags.personal_use_directive()`
returns `False` unconditionally, ignoring `SCREENER_PERSONAL_USE_DIRECTIVE`.

**Rationale**: FR-009 and the constitution's Principle V hosted clause make the
no-directive boundary **non-waivable** for any hosted/shared instance. Defaulting
the flag off is insufficient because an env misconfiguration could flip it; the
hosted instance must make directive output *impossible*, not just *unlikely*. The
Playwright no-directive lint runs against the hosted-mode build (SC-007) as the
backstop.

**Alternatives considered**: leaving the existing default-off flag as-is —
rejected: it is waivable by env, which violates the "non-waivable" requirement.

---

## Decision 5 — Secrets: runtime-only, fail-fast validated

**Decision**: All secrets — owner email allowlist, Google OAuth client id/secret,
NextAuth session secret, backend shared owner-secret, and the proxy's backend URL
— are supplied as **platform environment variables** (Vercel project env /
Render env). A **startup validation** refuses to serve if a required secret is
missing, so the instance never boots into an "open" state.

**Rationale**: FR-010 + SC-008 forbid any secret in the repo or in any deployed
file. Process-local env is the project's established pattern (memory:
api-keys-never-write). Fail-fast prevents a silent half-configured deployment
that could leak (e.g., backend up without the owner-secret gate).

**Alternatives considered**: `.env` files in the image — rejected outright
(violates FR-010). Secret managers (Vault/Doppler) — overkill for one operator on
free tiers; platform env vars suffice.

---

## Decision 6 — Cold-start UX and read-only refresh affordance

**Decision**: The frontend shows a **loading state** (not an error) while a slept
backend cold-starts, and retries transient unreachability (the existing
`ApiError.retryable` path already covers 5xx/timeouts). In hosted mode the
StartupFreshnessGate / DataFreshnessPanel **refresh affordance** explains that
refresh is performed **locally and republished**, and does **not** trigger heavy
in-host ingest (FR-007).

**Rationale**: SC-006 requires a usable app after cold start (no error page) and
< 3 s warm; FR-007 requires the 009 freshness check to keep running on the host
but without heavy in-host refresh. Reusing the existing retryable-error and
freshness UI keeps the change minimal and determinism-neutral.

**Alternatives considered**: a keep-warm cron pinger to avoid sleep — rejected:
it can burn the free tier's monthly compute budget (risking SC-005) and the spec
explicitly accepts cold starts.

---

## Cross-cutting confirmations

- **No strategy/indicator/backtest/baseline change** (FR-013, Principles
  II/III/IV): deployment + access + config only; the deployed code is byte-
  identical to 009 for all computation paths.
- **Determinism** (FR-012, SC-004): proxy and auth layers do not touch
  computation; same baked snapshot → identical outputs incl. byte-identical
  advisor prompt.
- **Single-user, no redistribution** (FR-015, constitution): one email allowlist,
  no public/anonymous access, owner's own data only — keeps the deployment within
  personal-use scope while honoring the hosted directive-OFF clause.
