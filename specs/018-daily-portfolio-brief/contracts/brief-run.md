# Contract: `POST /brief/run` and `GET /brief/status`

Router: `backend/src/api/brief.py`, registered in `app.py`. Both routes sit behind the existing
owner-secret dependency + CORS pin — no new auth surface. Both carry `data_as_of` + `disclaimer`.

## `POST /brief/run`

Assemble and (if not already delivered for the target session) send the daily brief. Called by
the feature-011 CI workflow after a real publish; also invokable manually by the owner.

**Request body**: empty `{}` (the target session and all inputs are derived server-side from the
live snapshot + persisted portfolio blob). Optional `{ "dry_run": true }` assembles + returns the
brief content **without** sending and **without** writing a `delivered` record (for verification).

**Behavior**:
- `brief_enabled()` is **False** ⇒ **404** (feature disabled; endpoint does not exist to callers,
  matching the `pipeline_enabled()`/`sentiment_enabled()` gating idiom). No email, no record.
- Target session = snapshot `data_as_of`. If it is **not** a completed trading session ⇒ record
  `skipped` with reason and return **200** with `status: "skipped"` (FR-011). No email.
- If a `delivered` record already exists for the target session ⇒ **idempotent no-op**: return
  **200** with that record and `status: "delivered"`; send **no** second email (FR-010).
- Otherwise: assemble `BriefModel`, render, send via SMTP (bounded retry), write the resulting
  Delivery Run Record, return **200** with `status: "delivered"`.
- Persistent send failure ⇒ write a `failed` record and return **502** with the redacted failure
  detail so the CI step surfaces it (FR-012, SC-007). The app password is never included.

**Response** (`BriefRunResponse`, 200): `{ status, target_session, record, data_as_of, disclaimer }`.
For `dry_run`, additionally includes the rendered `brief` object (no record written).

**Determinism**: For a fixed snapshot + portfolio + record state, two `dry_run` calls return an
identical `content_hash` (SC-005).

## `GET /brief/status`

Owner-visible confirmation of whether/what was sent (FR-014).

- `brief_enabled()` False ⇒ **200** `{ enabled: false, last_run: null, ... }` (status is readable
  even when the feature is off, so the owner can confirm it is off).
- Enabled ⇒ **200** `{ enabled: true, last_run: <most-recent BriefDeliveryRecord | null>, ... }`.

## Contract tests (`backend/tests/contract/` + `backend/tests/brief/`)

1. Flag OFF ⇒ `POST /brief/run` 404; `GET /brief/status` 200 with `enabled:false`.
2. Enabled, holdings present, trading session ⇒ 200 `delivered`; exactly one email sent (stub
   transport); record written; response carries `data_as_of` + `disclaimer`.
3. Second call for the same session ⇒ 200 `delivered`, **zero** additional emails (idempotent).
4. Non-trading-day target session ⇒ 200 `skipped`, zero emails, reason recorded.
5. Empty portfolio ⇒ 200 `delivered`, brief states portfolio is empty (US1 AC3), still 5 recs.
6. `dry_run` twice on the same snapshot ⇒ identical `content_hash` (determinism, SC-005).
7. Persistent SMTP failure ⇒ 502, `failed` record, response body contains **no** secret.
8. Every response includes exactly five recommendations (SC-003) and, in neutral mode, passes the
   no-directive lint (SC-004).
