# Contract: Email Delivery (Gmail SMTP) + Secrets + Idempotency

Module: `backend/src/brief/email.py`. Sends the rendered brief to the single owner via Gmail
SMTP with an app password. Store helper: `backend/src/data/brief_store.py`.

## Transport

`send_brief(subject, text_body, html_body, *, transport=None) -> None`
- Default transport: `smtplib.SMTP(host, port)` + `starttls()` + `login(user, password)` +
  `send_message(EmailMessage)`; `host/port/user/password/recipient` from env (see below).
- `transport` is injectable so tests substitute a stub (no live network).
- **Recipient guard**: the `To:` address is forced to `SCREENER_BRIEF_RECIPIENT`. If a caller ever
  passes a different address, it is ignored/overridden — the brief can only go to the owner
  (FR-009).
- **Bounded retry**: up to 3 attempts with short backoff on transient SMTP errors; after the last
  failure, raise so `POST /brief/run` records `failed` and returns 502 (FR-012, SC-007).

## Secrets handling (FR-015, non-negotiable)

- `SCREENER_BRIEF_SMTP_USER`, `SCREENER_BRIEF_SMTP_PASSWORD`, `SCREENER_BRIEF_RECIPIENT` are read
  from process env only, via `lib/flags.py` accessors — never written to any file and never
  logged. Failure/skip records store a **redacted** reason (SMTP error class, not the password).
- Configured as HF Space runtime secrets alongside the feature-014 sentiment keys. Covered by the
  existing release secret scan (`scripts/secret_scan.ps1`) — it must stay clean.

## Idempotency / run record (`brief_store.py`)

- `load_last_delivered(target_session) -> BriefDeliveryRecord | None`
- `record_run(BriefDeliveryRecord) -> None` — atomic write of `brief_runs.json` under
  `SCREENER_DATA_DIR` (tmp-then-replace, like `portfolio_store.save_portfolio_state`).
- At most one `delivered` record per `target_session` (FR-010). See research Decision 2 for why
  session-keying makes this correct even if the file is ephemeral across factory rebuilds.

## CI trigger step (`.github/workflows/daily-refresh.yml`)

- New final step, runs only when the publish step signalled a real publish
  (`published == 'true'`, research Decision 3) — not on a guard `noop`.
- `curl -fsS -X POST "$BACKEND_URL/brief/run" -H "X-Owner-Secret: $SCREENER_OWNER_SECRET"`
  (secret from repo secrets; backend URL is the Space/backend origin). `-f` makes an HTTP error
  fail the step so the owner is notified (reuses feature-011 failure surfacing).
- The step is scoped so a brief-send failure is reported **without** failing/rolling back the
  already-successful publish job (the fresh snapshot stays live) — see research Decision 6.

## Tests

1. `send_brief` calls the transport once with the owner recipient; a passed-in foreign recipient
   is overridden to `SCREENER_BRIEF_RECIPIENT` (FR-009).
2. Transient failure retries within bound then succeeds ⇒ one delivered record; permanent failure
   raises after the bound ⇒ `failed` record, no secret in the message (FR-012, FR-015).
3. `record_run` / `load_last_delivered` round-trip; a second `delivered` for the same session is a
   no-op at the `POST /brief/run` layer (idempotency, FR-010).
4. `automation` test: the workflow trigger fires only on `published == true` and not on a `noop`
   day (SC-008), mirroring the feature-011 automation tests.
