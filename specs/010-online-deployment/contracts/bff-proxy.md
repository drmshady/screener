# Contract: BFF Proxy (Next server-side → backend)

**Layer**: Frontend server (Next route handler `app/api/proxy/[...path]/route.ts`).
**Satisfies**: FR-003, FR-010, FR-012.

## Behavior

- The browser calls **only** the same-origin `/api/proxy/<backend-path>`; it never
  knows the backend URL or the owner secret.
- The route handler runs server-side, requires a valid owner session (shares the
  `middleware.ts` guard), then forwards the request to
  `${BACKEND_BASE_URL}/<backend-path>`:
  - Forwards method, path, query string, and JSON body verbatim.
  - **Injects `X-Owner-Secret: ${SCREENER_OWNER_SECRET}`** (server-only env).
  - Strips hop-by-hop / sensitive request headers; sets `Content-Type: application/json`.
  - Returns the backend's status code and body **unchanged**, preserving the
    backend's `data_as_of` + `disclaimer` middleware output and the existing
    `ApiError` retry semantics (5xx/408/429 retryable).
- `BACKEND_BASE_URL` and `SCREENER_OWNER_SECRET` are **server-only** env (not
  `NEXT_PUBLIC_*`), so they are never shipped to the browser bundle.

## Frontend change

- `frontend/src/lib/api.ts`: `API_BASE_URL` → `'/api/proxy'` (same-origin). All
  existing `fetchApi`/Zod call sites work unchanged against the proxy.

## Acceptance

| Given | When | Then |
|---|---|---|
| Owner session | browser `GET /api/proxy/strategies/midterm_52w_high_momentum/...` | proxied with secret; backend data returned unchanged |
| Inspect browser bundle/network | any call | backend URL + owner secret **absent**; only same-origin `/api/proxy/*` visible |
| Same snapshot, local vs hosted | identical screen | byte-identical advisor prompt + identical ordering (FR-012, SC-004) |

## Notes

- The proxy is the single browser↔backend path; combined with the backend
  owner-secret gate (`backend-owner-secret.md`), there is no unauthenticated route
  to screener data.
