# Phase 0 Research: Daily AI Portfolio Brief

All product-level unknowns were resolved in the spec's six Clarifications and Assumptions
(hosted execution, news window, deterministic five-item ranking, trigger after the 011 refresh,
Gmail SMTP app-password, directive wording flag+access-gated). This document records the
**implementation-level** decisions — the ones the plan depends on — with rationale and rejected
alternatives.

## Decision 1 — Compute location & trigger: hosted backend endpoint, called by the 011 CI job

**Decision**: Generate and send the brief on the **hosted backend** via a new owner-secret-gated
`POST /brief/run`. The **trigger** is a new final step in the existing feature-011
`daily-refresh.yml` workflow that runs *after* the successful Factory-rebuild redeploys the fresh
image, POSTing to `POST /brief/run` with the already-provisioned `SCREENER_OWNER_SECRET`.

**Rationale**: The hosted backend is the only place that has, simultaneously, the freshly-baked
read-only snapshot, the persisted single-owner portfolio blob (`portfolio_state.json`, including
transactions), the captured sentiment store, and the runtime secrets. Assembling the brief there
reuses the exact code paths that produce the in-app portfolio/holdings, regime, events, and
sentiment outputs, guaranteeing the brief's numbers are byte-identical to the app's (FR-002,
FR-013). The CI job already owns the "after the fresh session is live" moment, so it is the
natural trigger (spec Clarification: "runs immediately after the existing daily data-refresh job
completes … targets the just-refreshed completed session").

**Alternatives considered**:
- *Assemble the brief inside CI (a workflow job running the backend against the just-baked snapshot).*
  Rejected: CI has the snapshot but **not** the owner's portfolio blob (that lives on the hosted
  instance's runtime disk), so it could not report holdings/P&L/attention without a second fetch,
  and it would duplicate the hosted compute environment. The hosted endpoint is simpler and reuses
  the live code paths.
- *A self-scheduling loop inside the hosted backend (its own cron/APScheduler).* Rejected: adds a
  background-scheduler dependency and a second source of truth for "what session are we on"; the HF
  Space is not a durable scheduler and sleeps/cold-starts. Piggy-backing on the existing, proven
  011 cron keeps one trigger and one freshness contract.

## Decision 2 — Idempotency & the Delivery Run Record across factory rebuilds

**Decision**: Persist a per-session **Delivery Run Record** (`brief_runs.json` under
`SCREENER_DATA_DIR`, next to `portfolio_state.json`) keyed by the **target session date**
(the snapshot's `data_as_of`). `POST /brief/run` is idempotent: if a `delivered` record already
exists for the target session, it returns that record and sends **no** second email (FR-010).
Because the single daily CI trigger fires **once per published session**, at-most-once delivery
holds even though the record may be ephemeral (lost on a factory rebuild): a rebuild only happens
when a *new* session is baked, which is a *different* target-session key, so a stale/lost record
never causes a duplicate for the same session.

**Rationale**: HF Space runtime storage is ephemeral across factory rebuilds (this is the same
property behind the "portfolio re-import after refresh" behavior). Keying idempotency on the
target session — rather than trusting durable state — makes correctness independent of storage
durability: the only way to re-send for session *S* is to re-trigger `POST /brief/run` while *S*
is still the live snapshot, and the record written at send-time (same process lifetime) blocks
that within the run. Manual re-triggers within the same deploy are the realistic duplicate risk,
and the record covers exactly that window.

**Alternatives considered**:
- *Rely on a durable external store (DB/Redis) for idempotency.* Rejected: introduces
  infrastructure the personal deployment does not have and the spec does not want; the
  session-keyed approach is sufficient for a single daily trigger.
- *No record at all (trust the single trigger).* Rejected: a manual workflow re-run or a retried
  step could double-send within one deploy; the in-process record closes that.

## Decision 3 — Distinguishing a real publish from a guard `noop` in the CI step

**Decision**: The brief-trigger step must only fire when the publish chain actually published a
new session. `publish_chain.ps1` currently `exit 0`s on a guard `noop` *and* on a real publish,
so the workflow cannot tell them apart today. Resolve by having the publish step **emit a
GitHub Actions step output** (e.g. `published=true|false`, derived from the guard outcome it
already computes) and gating the new trigger step on `steps.<id>.outputs.published == 'true'`.
On a manual `force_rebuild` dispatch (which passes `-SkipGuard`), treat it as `published=true`.

**Rationale**: Keeps the non-trading-day contract intact (FR-011, SC-008 — no misleading "today"
brief) without adding a second freshness check. The guard already knows the answer; we only need
to surface it. As a defense-in-depth backstop, `POST /brief/run` itself independently checks the
target session against the last delivered record and against the snapshot's trading-day status,
so a spurious call still cannot send a non-trading-day or duplicate brief.

**Alternatives considered**:
- *Always call `POST /brief/run` and let the backend decide.* Partially adopted (backend does
  guard), but still gate the CI step on `published` so a documented no-op day makes no network
  call and leaves a clean run log.
- *Parse the manifest in a second CI step to detect freshness.* Rejected: duplicates the guard's
  logic; surfacing the guard's own outcome is DRY.

## Decision 4 — Directive carve-out: a new `brief_directive_enabled()`, not a change to `personal_use_directive()`

**Decision**: Add a **new** flag helper `brief_directive_enabled()` that returns `True` only when
**all** hold: `SCREENER_PERSONAL_USE_DIRECTIVE=1`, hosted single-owner access gate is enforced
(`owner_secret()` is set), and the instance is not multi-user (no multi-user flag). Leave the
existing `personal_use_directive()` — which every other surface uses and which
`hosted_mode()` force-disables — **unchanged**. The brief uses `brief_directive_enabled()`; when
it is `False`, the brief renders neutral, non-directive copy (FR-006) and still includes all five
recommendations (FR-007a — degrade framing, never drop the section).

**Rationale**: The constitution v1.2.0 Sync Impact Report explicitly instructs feature 018 to
"implement an explicit single-owner-gated directive carve-out (still flag-gated, still
access-gated) rather than a blanket hosted force-off." A separate helper scoped to the brief keeps
the general UI's hosted force-OFF exactly as feature 010 shipped it (no regression, no broadening
of directive output on any third-party-reachable surface), while permitting directive wording on
the one surface whose output provably reaches only the owner's own inbox. This is the minimal,
auditable change that satisfies FR-007/FR-007a and Principle V as re-scoped.

**Alternatives considered**:
- *Relax `personal_use_directive()` to not force-OFF when hosted+single-owner.* Rejected: that
  would silently enable directive wording across the *entire* in-app UI (results, cockpit,
  advisor prompt previews), broadening the exception far beyond the owner-only email and beyond
  what the amendment intends. A brief-scoped helper is the smaller blast radius.
- *A build-time env flag.* Rejected: the frontend uses a Next prod build with no build-time env
  flags (project convention); this is a runtime backend concern only.

## Decision 5 — Email transport: stdlib `smtplib` + Gmail app password, no new dependency

**Decision**: Send via Python's stdlib `smtplib.SMTP` (STARTTLS, `smtp.gmail.com:587`) +
`email.message.EmailMessage`, authenticated with a Gmail **app password**. Host, port, username,
app password, and recipient are read from process env only:
`SCREENER_BRIEF_SMTP_HOST` (default `smtp.gmail.com`), `SCREENER_BRIEF_SMTP_PORT` (default `587`),
`SCREENER_BRIEF_SMTP_USER`, `SCREENER_BRIEF_SMTP_PASSWORD`, `SCREENER_BRIEF_RECIPIENT`
(the single allowlisted owner address). The `email.py` edge accepts an injectable transport so
tests exercise send/retry/failure against a stub with no live network.

**Rationale**: Matches the spec Clarification (Gmail SMTP + app password, no new third-party email
service) and the codebase's "secrets are runtime env only, never written to any file/log"
non-negotiable (FR-015; see the existing feature-014 sentiment-key handling and
`scripts/secret_scan.ps1`). Using the stdlib avoids adding a mail dependency to the baked image.
The recipient is force-checked against `SCREENER_BRIEF_RECIPIENT` so the brief can never be
addressed to a non-owner (FR-009).

**Alternatives considered**:
- *A transactional-email API (SendGrid/SES/Resend).* Rejected: adds a third-party service, an
  account, and a new credential surface the spec explicitly excludes for v1.
- *Gmail API (OAuth).* Rejected: heavier auth (token refresh, consent) for an unattended job than a
  single app password; the spec chose SMTP + app password.

## Decision 6 — Retry, failure surfacing, and non-trading-day handling

**Decision**: `email.py` retries a failed send with a small bounded backoff (e.g. 3 attempts).
On persistent failure, `POST /brief/run` records a `failed` Delivery Run Record and returns a
non-2xx so the **CI trigger step surfaces the failure in the workflow run** (owner-visible via
the same GitHub failure notification path feature 011 already uses), rather than passing silently
(FR-012, SC-007). The trigger step is marked so a brief-send failure is reported **without**
failing/rolling back the already-successful publish job (the fresh snapshot stays live). On a
non-trading day, the CI step does not fire (Decision 3) **and** `POST /brief/run` independently
labels/short-circuits against the last completed session (FR-011).

**Rationale**: Reuses the existing owner-notification channel (workflow failure surfacing) instead
of inventing a new one, satisfying "raise an owner-visible notification rather than fail silently"
without new infrastructure. Separating brief-send failure from publish success preserves the 011
invariant that a failed step must not leave a partial/rolled-back snapshot.

## Decision 7 — News window "since last delivered brief"

**Decision**: Compute the news/sentiment window as **since the `data_as_of` of the last delivered
Delivery Run Record**, widening to the elapsed period across market holidays/gaps (so items are
not repeated day to day), and falling back to a ~1-trading-day lookback when no prior record
exists (first brief, or an ephemeral-record cold start). Items are drawn from the existing
feature-014 captured-sentiment/news pipeline over the owner's held + watched tickers.

**Rationale**: Directly implements FR-004 (window since last brief, widening across gaps, no
repeats). Deriving the boundary from the last *delivered* record — not wall-clock — keeps the
window correct across skipped/holiday days and keeps output deterministic for a given
snapshot + record state.

**Alternatives considered**:
- *Fixed 24-hour or fixed 1-trading-day window.* Rejected: repeats items across a weekend/holiday
  gap or drops items when a day is skipped; the since-last-brief boundary is what the spec asked
  for.

## Decision 8 — Reuse map (no new financial logic)

Confirms FR-002 by naming the existing outputs the brief composes, so no new rule/indicator is
introduced:

| Brief section | Reused existing source |
|---|---|
| Portfolio value, overall + per-holding P&L, risk exposure/heat | `api/portfolio._assemble_holdings` → `PortfolioTotals` (`portfolio/aggregation.py`, `holding_levels.py`, `holding_risk.py`, `pnl.py`) |
| Holdings needing attention (risk/heat breach, stop proximity, pipeline stage change) | `portfolio/holding_risk.py` + `portfolio_heat_ceiling()` + the frontend-derived pipeline stage already synced in the blob (feature 016) |
| News + sentiment per ticker | feature 014 `sentiment/composite.py` + captured store + `api/sentiment.generate_and_capture` (budget-capped, degrade-to-template) |
| Market-context line | `regime/calculator.current_regime_response()` + `events/service.EventsService` (market events) |
| Five recommendations | NEW pure `brief/recommend.py` — deterministic ranking **over the above signals only**; selects nothing new |
| Disclosures (data_as_of, disclaimer, citations, warnings) | `lib/disclaimer`, strategy `CITATION` from the registry, existing integrity/staleness warnings |

**Output**: All NEEDS CLARIFICATION resolved. No open blocking questions remain for Phase 1.
