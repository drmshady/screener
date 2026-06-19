# Contract: Backend Owner-Secret Gate

**Layer**: Backend (FastAPI `app.py` dependency/middleware). **Satisfies**:
FR-003, FR-015.

## Behavior

- When `SCREENER_HOSTED_MODE` is ON, a FastAPI dependency/middleware applied to
  **all routers** requires header `X-Owner-Secret` to equal `SCREENER_OWNER_SECRET`
  (constant-time compare).
- Missing/incorrect secret → **401** (or 403) with a minimal error body and **no
  screener data** — applies uniformly to every data-bearing endpoint (screen,
  candidates, strategies, backtest, regime, sizing, portfolio, data, meta,
  events, analyze, verify), so there is no unguarded path (FR-003).
- The disclaimer/`data_as_of` middleware still runs, but on a rejected request the
  body carries no candidates/levels/gates.
- When `SCREENER_HOSTED_MODE` is OFF (local dev), the gate is inactive — local
  behavior is unchanged.
- **CORS**: in hosted mode, `allow_origins` is pinned to the deployed frontend
  origin only (not the localhost list).

## Fail-fast

- If `SCREENER_HOSTED_MODE` is ON and `SCREENER_OWNER_SECRET` is unset/empty, the
  app **refuses to start serving** (raises at startup) rather than booting an open
  instance.

## Acceptance

| Given | When | Then |
|---|---|---|
| Hosted mode, no `X-Owner-Secret` | request to any data endpoint | 401/403, no screener data |
| Hosted mode, wrong secret | any data endpoint | 401/403, no screener data |
| Hosted mode, correct secret | any data endpoint | normal response (data + `data_as_of` + `disclaimer`) |
| Hosted mode, secret env missing | app startup | startup fails (no open boot) |
| Local mode (hosted OFF) | any request | unchanged, gate inactive |

## Notes

- The secret is shared only between the Vercel proxy (server-only env) and the
  Render backend env. Never in repo or any deployed file (FR-010, SC-008).
