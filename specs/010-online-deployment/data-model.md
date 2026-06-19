# Phase 1 Data Model: Online Deployment (Personal, Free)

This feature introduces **no persistent schema change** (no new SQLite table, no
new Parquet partition). The entities below are *deployment/access* entities:
configuration, an immutable published artifact, and an identity. They model what
must be true at deploy/runtime, not new financial data.

---

## 1. Data Snapshot (published, read-only)

The point-in-time bundle the hosted instance serves read-only. Produced by the
existing local 009 pipeline; **baked into the backend image** at publish time.

| Field / part | Source | Notes |
|---|---|---|
| `prices/parquet/**` | local prices store | Partitioned daily bars for the screened universe. |
| `catalog.db` | local SQLite | Tickers, fundamentals, events, **precomputed `backtest_runs`**. |
| EDGAR slim cache | local | Schema-versioned (v3) fundamentals cache. |
| calendars | local | Trading-session calendars (freshness math). |
| `manifest.json` | local | Per-source `data_as_of` / `last_bar_date` / `is_stale` → drives `GET /data/freshness`. |
| provenance | within above | Source tags + as-of timestamps (Principle I) travel unchanged. |

**Rules**:
- **Immutable at runtime** — no in-host ingest writes to it (FR-004).
- **Complete or not served** — a publish that is partial/corrupt MUST NOT take
  traffic; the prior good image keeps serving, or an explicit maintenance/empty
  state is shown (FR-006). Enforced by an image **health check** that validates
  the manifest + presence of key stores before cutover.
- **Reproducible** — rebuildable from a fresh local snapshot via the runbook
  (FR-005, FR-014); no data loss on free-tier suspension/reset (FR-011).
- **Determinism** — identical bytes → identical screen/regime/sizing/event/
  advisor-prompt output as local (FR-012, SC-004).

**State**: `valid-serving` → (new publish) `staged` → `health-checked` →
`valid-serving` (atomic swap). A `staged` snapshot that fails health stays
non-serving; the instance remains on the last `valid-serving` snapshot.

---

## 2. Authorized Owner Identity

The single identity-provider account permitted to sign in.

| Field | Type | Notes |
|---|---|---|
| `owner_email` | string (env) | The one Google account email allowed. Runtime env, never committed (FR-010). |
| provider | fixed | Google (spec Assumptions). |
| allowlist semantics | single | Exactly one email admitted; **all others denied** with no data (FR-002, FR-003). |

**Rules**: NextAuth `signIn` callback admits the session only if the Google
profile email equals `owner_email` (case-insensitive, verified-email required);
otherwise access is denied and **no screener data** is rendered or proxied.

---

## 3. Hosted Instance

The running online deployment.

| Part | Value | Notes |
|---|---|---|
| backend | Render free web service (Docker) | Sleeps on idle; cold-starts; serves baked snapshot read-only. |
| frontend | Vercel free (Next.js) | NextAuth gate + BFF proxy; same-origin to the browser. |
| transport | HTTPS (platform URLs) | FR-016; no custom domain required. |
| `hosted_mode` | ON | Forces directive OFF (FR-009), enables owner-secret gate, pins CORS to frontend origin. |

**Rules**: When `hosted_mode` is ON: directive personal-use mode is **forced OFF
and non-waivable**; every request to the backend must carry the owner secret;
CORS is restricted to the deployed frontend origin; every response still carries
`data_as_of` + `disclaimer` (FR-008).

---

## 4. Runtime Configuration / Secrets

Process-local values supplied at runtime; **never** in the repo or any deployed
file (FR-010, SC-008).

| Key | Where | Purpose |
|---|---|---|
| `SCREENER_HOSTED_MODE` | backend + frontend | Activates hosted behavior (gate on, directive forced OFF). |
| `SCREENER_OWNER_SECRET` | backend (private) + Vercel server-only | Shared secret the proxy injects and the backend requires. |
| backend base URL | Vercel server-only | Target the BFF proxy forwards to; never exposed to the browser. |
| `AUTH_GOOGLE_ID` / `AUTH_GOOGLE_SECRET` | Vercel server-only | Google OAuth client. |
| `AUTH_SECRET` (NextAuth) | Vercel server-only | Session signing secret. |
| `SCREENER_OWNER_EMAIL` | Vercel server-only | The allowlisted owner email. |
| (optional) provider keys | backend env | Optional paid/cross-check stays disabled if absent (Edge Cases). |

**Rules**:
- **Fail-fast**: backend refuses to serve if `SCREENER_HOSTED_MODE` is on and
  `SCREENER_OWNER_SECRET` is missing; frontend auth refuses to operate without
  Google client + `AUTH_SECRET` + `SCREENER_OWNER_EMAIL`. No silent "open" boot.
- **No persistence to file**: secrets read from env only; never written to the
  snapshot or any artifact file.
- `SCREENER_PERSONAL_USE_DIRECTIVE` is **ignored** when hosted mode is on (forced
  OFF) — it is intentionally not in the required set and cannot re-enable
  directive output (FR-009).

---

## Relationships

- A **Hosted Instance** serves exactly one `valid-serving` **Data Snapshot** and
  admits exactly one **Authorized Owner Identity**, configured by **Runtime
  Configuration / Secrets**.
- Publishing a new **Data Snapshot** replaces the served one via atomic swap; it
  does not touch identity or secrets.
- Losing the instance (free-tier reset) loses no data: the snapshot is rebuilt
  from local and re-deployed; secrets are re-supplied as env.
