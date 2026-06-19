# Contract: Hosted-Mode Configuration

**Layer**: Backend `lib/flags.py` + `lib/hosting.py`, frontend config.
**Satisfies**: FR-008, FR-009, FR-010, FR-016, SC-007, SC-008.

## Directive personal-use mode — forced OFF, non-waivable

- When `SCREENER_HOSTED_MODE` is ON, `personal_use_directive()` returns **`False`
  unconditionally**, ignoring `SCREENER_PERSONAL_USE_DIRECTIVE`.
- No env/config value can re-enable directive language on the hosted instance
  (FR-009, constitution Principle V hosted clause).
- Backstop: the Playwright **no-directive-language lint** runs against the
  hosted-mode build and must pass (SC-007).

## Disclosure preserved

- Every user-visible response carries `data_as_of` + `disclaimer` (FR-008,
  unchanged 001 non-negotiable, still applied by the existing middleware).

## Transport

- HTTPS only on both origins (platform URLs) (FR-016). No custom domain required.

## Secrets

- All secrets are runtime env, **never** in the repo or any deployed file
  (FR-010). A release **secret scan** over the repo + assembled image must find
  zero provider keys / owner secrets (SC-008).
- **Fail-fast**: if hosted mode is on and a required secret is missing, the
  affected service refuses to serve (no open boot). See
  `backend-owner-secret.md` and `auth-gate.md` for the per-service required sets.

## Required runtime env (summary)

This table is the **single canonical list** of required runtime env vars
(`quickstart.md` C1/C2 and `render.yaml` mirror it; they must not diverge).

| Service | Keys |
|---|---|
| Backend (Render) | `SCREENER_HOSTED_MODE=1`, `SCREENER_OWNER_SECRET` (secret), `SCREENER_FRONTEND_ORIGIN` (the Vercel origin, for CORS), (optional provider keys) |
| Frontend (Vercel) | `SCREENER_HOSTED_MODE=1`, `NEXT_PUBLIC_SCREENER_HOSTED_MODE=1` (non-secret UI mode flag), `BACKEND_BASE_URL` (server-only), `SCREENER_OWNER_SECRET` (server-only secret), `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET` (secret), `AUTH_SECRET` (secret), `SCREENER_OWNER_EMAIL` |

## Acceptance

| Given | When | Then |
|---|---|---|
| Hosted mode + `SCREENER_PERSONAL_USE_DIRECTIVE=1` | advisor prompt export | neutral, non-directive output; no take/pass/size framing (FR-009) |
| Hosted build | Playwright no-directive lint | passes (SC-007) |
| Repo + deployed image | secret scan | zero secrets found (SC-008) |
| Any hosted response | inspect body | `data_as_of` + `disclaimer` present (FR-008) |
