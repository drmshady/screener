# Contract: Owner Auth Gate (NextAuth Google + single-email allowlist)

**Layer**: Frontend (Next.js / Auth.js). **Satisfies**: FR-002, FR-003, FR-015.

## Behavior

- Provider: **Google** (OAuth). Session strategy: JWT cookie (NextAuth default),
  HTTPS-only cookies.
- **Allowlist of one**: the `signIn` callback admits a session **only if** the
  Google profile's email is verified AND equals `SCREENER_OWNER_EMAIL`
  (case-insensitive). Any other email → access denied, no session issued.
- **Route protection** (`middleware.ts`): every app route and every
  `/api/proxy/*` route requires a valid owner session. Unauthenticated requests
  are redirected to sign-in and receive **no screener data** (no SSR data, no
  proxied call). The NextAuth routes (`/api/auth/*`) and static assets are the
  only unauthenticated-reachable paths.

## Acceptance

| Given | When | Then |
|---|---|---|
| No session | GET any page | 302 → sign-in; zero screener data in response |
| No session | GET `/api/proxy/strategies/...` (data endpoint) | 401/redirect; **no** backend call, no data |
| Session with non-owner email | any access | denied; no session persisted; no data |
| Session with `SCREENER_OWNER_EMAIL` | any access | granted; full app |

## Notes

- Required env (server-only on Vercel): `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`,
  `AUTH_SECRET`, `SCREENER_OWNER_EMAIL`. Missing any → auth fails closed (no open
  access). Never committed (FR-010).
- Tested by Playwright (unauthenticated + non-owner → no data; owner → access)
  and Vitest (signIn callback allow/deny on email).
