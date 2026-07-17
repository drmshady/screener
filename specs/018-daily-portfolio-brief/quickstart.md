# Quickstart: Daily AI Portfolio Brief

Local dev runbook, manual verification, and deploy notes for feature 018. Assumes the feature-010
hosted architecture and the Windows dev conventions (`py -3.12`, run pytest from repo root).

## 1. Configuration (runtime env only — never commit)

Enable the feature and provide the Gmail SMTP credentials as process env / HF Space runtime
secrets. A Gmail **app password** (Google Account → Security → 2-Step Verification → App
passwords) is required — not the account password.

```
SCREENER_BRIEF_ENABLED=1
SCREENER_BRIEF_SMTP_HOST=smtp.gmail.com      # default
SCREENER_BRIEF_SMTP_PORT=587                 # default (STARTTLS)
SCREENER_BRIEF_SMTP_USER=dr.mshady@gmail.com
SCREENER_BRIEF_SMTP_PASSWORD=<gmail-app-password>
SCREENER_BRIEF_RECIPIENT=dr.mshady@gmail.com   # single allowlisted owner address

# Optional: direct (directive) wording. Requires the single-owner access gate (owner secret).
SCREENER_PERSONAL_USE_DIRECTIVE=1
```

These are read by `lib/flags.py` accessors and never written to any file or log (FR-015). The
release secret scan (`scripts/secret_scan.ps1`) must stay clean.

## 2. Run the backend suite (test-first)

```
# from repo root
py -3.12 -m pytest backend/tests/brief backend/tests/contract backend/tests/automation -q
```

The two new pure units (five-item ranker, renderer) and the directive carve-out ship with tests
that fail before the implementation lands (Principle IV discipline).

## 3. Local manual verification (no email sent)

With an imported portfolio present in the persisted blob, dry-run the assembly:

```
# backend running locally with SCREENER_BRIEF_ENABLED=1 (+ owner secret if hosted-mode simulated)
curl -sS -X POST http://localhost:8000/brief/run \
  -H "X-Owner-Secret: $SCREENER_OWNER_SECRET" \
  -H "content-type: application/json" \
  -d '{"dry_run": true}' | python -m json.tool
```

Confirm the returned brief has: portfolio status (value, overall + per-holding P&L, risk/heat,
attention list), a news section (or explicit "nothing material"), a market-context line with
source + as-of, **exactly five** recommendations, `data_as_of`, and the disclaimer. Run it twice
and confirm identical `content_hash` (determinism, SC-005).

To exercise a real send locally, drop `dry_run` and point the SMTP env at Gmail; the email arrives
in the owner inbox only.

## 4. Check delivery status

```
curl -sS http://localhost:8000/brief/status -H "X-Owner-Secret: $SCREENER_OWNER_SECRET"
```

Returns `{ enabled, last_run, ... }` so the owner can confirm whether today's brief was sent,
skipped (non-trading day), or failed (FR-014).

## 5. Deploy (hosted)

This feature is backend + CI-workflow only; it rides the existing publish chain.

1. **Add HF Space runtime secrets**: `SCREENER_BRIEF_ENABLED`, `SCREENER_BRIEF_SMTP_USER`,
   `SCREENER_BRIEF_SMTP_PASSWORD`, `SCREENER_BRIEF_RECIPIENT`, and (for directive wording)
   `SCREENER_PERSONAL_USE_DIRECTIVE=1`. The Space already has `SCREENER_OWNER_SECRET`.
2. **Add repo secrets** for the CI trigger step: it reuses `SCREENER_OWNER_SECRET` (already a
   repo secret) and reads an optional `SCREENER_BACKEND_URL` for the backend origin. When
   `SCREENER_BACKEND_URL` is absent the step derives the HF Space URL from `SPACE_ID`
   (`occlusion2/screener` → `https://occlusion2-screener.hf.space`). The trigger step is
   `continue-on-error` and gated on `steps.publish.outputs.published == 'true'`, so it fires only
   after a real publish and a send failure never rolls back the snapshot (FR-012).
3. **Ship the code**: this is a code-only change (no snapshot row-schema change). Deploy via the
   existing GitHub Actions **Daily Refresh** workflow with `force_rebuild=true`, which rebuilds the
   image and Factory-reboots the Space (see the deploy memories). Vercel frontend needs no change
   for P1–P3.
4. **Verify end-to-end**: after the next scheduled `daily-refresh` run (or a manual dispatch), the
   new final workflow step calls `POST /brief/run`; confirm the brief arrives in the owner inbox
   and `GET /brief/status` shows a `delivered` record for the session.

## 6. Disable

Set `SCREENER_BRIEF_ENABLED=0` (or remove it). `POST /brief/run` then 404s, the CI trigger step is
a no-op, and no email is sent — within one day (SC-006). No other app behavior changes.

## Notes / gotchas

- **Determinism**: `generated_at` is excluded from the content hash so re-runs on the same
  snapshot compare equal. Everything else in the brief is a pure function of snapshot + portfolio.
- **Ephemeral run record**: `brief_runs.json` may not survive a factory rebuild; idempotency is
  keyed on the target session, so at-most-once still holds (research Decision 2). If you re-trigger
  `POST /brief/run` manually within the same deploy, the in-process record blocks a duplicate.
- **Non-trading day**: the CI step won't fire on a guard `noop`, and `POST /brief/run` independently
  skips/labels against the last completed session — no misleading "today" brief (FR-011, SC-008).
- **Budget cap**: any AI narrative phrasing reuses the feature-014 budget guard and degrades to the
  deterministic source-only template when the cap is reached; the brief is still delivered in full.
