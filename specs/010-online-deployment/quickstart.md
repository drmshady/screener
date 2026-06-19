# Quickstart & Deployment Runbook: Online Deployment (010)

The reproducible runbook (FR-014) to stand up, publish data to, and rebuild the
**single-owner, free, online** screener: **Render** (FastAPI backend, Docker,
free web service) + **Vercel** (Next.js frontend, free), gated by **NextAuth
Google sign-in (single-email allowlist)** with a **BFF proxy**, serving a
**read-only snapshot baked into the backend image**.

Personal-use, single-user scope is retained. All secrets are supplied at runtime
as platform environment variables and are **never committed or written to any
file in the artifact** (FR-010, SC-008).

> Prereq: feature 009 is green locally (`py -3.12 -m pytest`, frontend Vitest +
> Playwright). This runbook deploys that release-ready build; it changes no
> strategy rule, default, citation, or backtest baseline (FR-013).

---

## A. One-time setup

### A1. Google OAuth client (owner identity)

1. Google Cloud Console → **APIs & Services → Credentials → Create OAuth client
   ID → Web application**.
2. Authorized redirect URI: `https://<your-vercel-app>.vercel.app/api/auth/callback/google`
   (add it after you know the Vercel URL — see C, then return here).
3. Note the **Client ID** and **Client secret** → used as `AUTH_GOOGLE_ID` /
   `AUTH_GOOGLE_SECRET` (Vercel env, server-only).

### A2. Generate secrets

```powershell
# NextAuth session secret
py -3.12 -c "import secrets; print(secrets.token_urlsafe(32))"   # → AUTH_SECRET
# Shared backend owner secret (proxy ⇄ backend)
py -3.12 -c "import secrets; print(secrets.token_urlsafe(32))"   # → SCREENER_OWNER_SECRET
```

Keep these only in your password manager / platform env. Do **not** put them in
any file in the repo.

---

## B. Publish the data snapshot (bake into the backend image)

1. **Refresh locally** with the existing 009 pipeline so `backend/data` is fresh
   and complete:
   ```powershell
   py -3.12 scripts\seed_universe.py
   py -3.12 scripts\refresh_stooq_history.py
   py -3.12 scripts\ingest_daily.py
   ```
2. Confirm `backend/data/manifest.json` shows current per-source `data_as_of`
   (or run the local app and check the freshness panel).
3. The backend `Dockerfile` copies the snapshot scope into the image
   (`prices/parquet/**`, `catalog.db`, EDGAR slim cache, calendars,
   `manifest.json`). `.dockerignore` excludes everything else — **no key/secret
   file enters the image** (FR-010).

> "Publishing fresher data later" = repeat B then redeploy (C2). The platform
> swaps atomically; the old image serves until the new one passes health check —
> the host never serves a partial/corrupt snapshot (FR-006).

---

> The full required-env list is canonicalised in
> [`contracts/hosted-mode-config.md`](contracts/hosted-mode-config.md) (backend
> Render set + frontend Vercel server-only set). The C1/C2 lists below and
> `render.yaml` mirror it — keep all three in sync.

## C. Deploy

### C1. Backend → Render (Docker web service)

1. Render → **New → Web Service** → connect the repo → **Docker** runtime,
   Dockerfile path `backend/Dockerfile`.
2. Environment (runtime, never committed):
   - `SCREENER_HOSTED_MODE=1`
   - `SCREENER_OWNER_SECRET=<from A2>`
   - `SCREENER_FRONTEND_ORIGIN=https://<your-vercel-app>.vercel.app` — pins CORS
     to the frontend origin (set after C2; redeploy).
   - (optional) provider keys — if absent, the optional paid/cross-check path
     stays disabled and the free path works (Edge Cases).
   These match the `render.yaml` env block (`sync: false` keys are entered in the
   Render dashboard, never committed).
3. Health check path: `/health` (validates `manifest.json` + key stores; returns
   503 maintenance until the snapshot is complete, so the atomic swap keeps the
   last good image serving). Already declared as `healthCheckPath` in `render.yaml`.
4. Deploy → note the backend URL `https://<backend>.onrender.com`.

> Free web service **sleeps after idle**; the first request cold-starts (accepted,
> FR-011/SC-006). No data is lost on sleep — the snapshot is in the image.

### C2. Frontend → Vercel (Next.js)

1. Vercel → **Add New Project** → import the repo → root = `frontend/`.
2. Environment variables (Production; `BACKEND_BASE_URL` + `SCREENER_OWNER_SECRET`
   are **server-only**, NOT `NEXT_PUBLIC_*`):
   - `SCREENER_HOSTED_MODE=1`
   - `NEXT_PUBLIC_SCREENER_HOSTED_MODE=1`
   - `BACKEND_BASE_URL=https://<backend>.onrender.com`
   - `SCREENER_OWNER_SECRET=<same as C1>`
   - `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET` (from A1)
   - `AUTH_SECRET` (from A2)
   - `SCREENER_OWNER_EMAIL=<your Google email>`
3. Deploy → note `https://<your-vercel-app>.vercel.app`.
4. Go back to **A1.2** and add the redirect URI for this Vercel URL; in **C1.2**
   set the backend CORS origin to this Vercel URL; redeploy both if changed.

---

## D. Smoke verification (acceptance)

1. **Owner access** — open the Vercel URL in a fresh browser/profile, sign in with
   the owner Google account → full app (US1, SC-001). Run
   `midterm_52w_high_momentum`; candidates render with levels, gates, per-source
   freshness, `data_as_of`, disclaimer; zero directive language.
2. **Deny non-owner / unauthenticated** (US2, SC-002):
   - Signed out → any page redirects to sign-in; `GET /api/proxy/strategies/...`
     returns no data.
   - Sign in with a **different** Google account → denied, no data.
   - Direct-hit the backend without the secret (`curl https://<backend>.onrender.com/...`)
     → 401/403, no screener data.
3. **Fresh snapshot** (US3, SC-003) — after a later publish (B + redeploy), reload
   → `data_as_of` advances.
4. **Determinism** (SC-004) — same published snapshot: hosted screen ordering
   matches local; advisor-prompt export is byte-identical local vs hosted.
5. **Cold start** (SC-006) — after idle, first load shows a loading state and
   becomes usable (no error page); warm reload < 3 s.
6. **Directive forced OFF** (SC-007) — even with
   `SCREENER_PERSONAL_USE_DIRECTIVE=1` set in env, exported prompt is neutral; the
   Playwright no-directive lint passes against the hosted build.
7. **No secrets leaked** (SC-008) — run the release secret scan over the repo +
   the assembled image copy list; it must exit 0 with zero findings:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\secret_scan.ps1
   ```
   Then inspect the deployed browser bundle/network tab and confirm no backend
   URL or owner secret appears (both are server-only env, never `NEXT_PUBLIC_*`).

---

## E. Rebuild / restore (free-tier reset)

A suspended/reset free instance loses no data because data is reproducible
locally:

1. Re-run **C1**/**C2** (reconnect the repo, re-enter the runtime env from your
   password manager).
2. Republish the snapshot (**B**) and redeploy.
3. Re-verify with **D**.

---

## F. Notes & constraints

- **$0** within Render + Vercel free-tier limits (SC-005); the owner accepts cold
  starts and instance sleep.
- **Read-only host**: no heavy in-host ingest; the freshness "refresh" affordance
  explains refresh is local-then-republish (FR-004, FR-007).
- **Single-user**: one email allowlist; no public/anonymous access; no
  redistribution (FR-015).
- This feature adds only the access layer (NextAuth + proxy + backend secret
  gate), hosted-mode config (forced directive-OFF), and deployment manifests — no
  change to strategy logic, defaults, citations, or backtest baselines (FR-013).
