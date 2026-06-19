# Feature Specification: Online Deployment (Personal, Free)

**Feature Branch**: `010-online-deployment`
**Created**: 2026-06-19
**Status**: Draft
**Input**: User description: "deploy app to server to work online for personal use free"

## Overview

Make the already-assembled screener reachable over the public internet so the
single owner can use it from anywhere (e.g., from work), instead of only on the
local machine — while keeping it **free**, **single-user**, and within the
constitution's rules. This is a deployment / access feature: **no new strategy
and no strategy rule, default, citation, or backtest baseline change.** Feature
009 declared "no hosted target in v1"; this feature deliberately introduces a
single-owner hosted instance and therefore must honor the constitution's
hosted-mode clauses (directive personal-use mode forced OFF; data-source and
disclosure obligations preserved).

The hosted instance is **read-only over a data snapshot published from the
owner's local environment** — the existing data refresh/ingest pipeline keeps
running locally; the host never performs heavy backfill. Access is gated by
**sign-in with a single owner identity**, and the deployment targets a **free
hosting tier**, accepting cold starts and instance sleep.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Use the screener from anywhere (Priority: P1)

As the owner, I open a URL from any standard browser on any device — including a
machine that has never run the project — sign in, and run a mid-term momentum
screen, getting the same candidates, levels, gates, regime, and disclaimers I
would see locally.

**Why this priority**: This is the entire point of the feature — remote access
to the working tool. Without it nothing else matters.

**Independent Test**: From a remote device that has never run the project, open
the hosted URL, complete owner sign-in, run `midterm_52w_high_momentum`, and
confirm candidates render with `data_as_of`, `disclaimer`, levels, gates, and
per-source freshness.

**Acceptance Scenarios**:

1. **Given** the hosted instance is running and a valid snapshot is published,
   **When** the signed-in owner runs a momentum screen, **Then** candidates
   render with levels, gates, per-source freshness, `data_as_of`, and the
   disclaimer, with zero directive language.
2. **Given** the owner is on a fresh device with no local install, **When** they
   open the hosted URL and sign in, **Then** the app loads and is fully usable
   without any local setup.
3. **Given** a screen returns no candidates, **When** it completes, **Then** an
   explicit empty-state is shown (not an error or blank page).

---

### User Story 2 - Only the owner can get in (Priority: P1)

As the owner, I need the publicly reachable instance to admit only me. Anyone
who is not signed in as my authorized identity sees no screener data at all.

**Why this priority**: The app was built no-auth for localhost. Exposing it to
the internet without an access gate would leak the owner's data and outputs to
anyone with the URL. Security is non-negotiable the moment it is public.

**Independent Test**: From an un-authenticated session and from a session signed
in as a non-owner account, attempt to load any page or data endpoint and confirm
access is denied with no screener data returned; then sign in as the owner and
confirm access is granted.

**Acceptance Scenarios**:

1. **Given** an unauthenticated visitor, **When** they request any page or
   data-bearing endpoint, **Then** they are sent to sign-in and receive no
   screener data.
2. **Given** a visitor signed in with an account that is not the authorized
   owner, **When** they attempt access, **Then** they are denied and shown no
   screener data.
3. **Given** the authorized owner identity, **When** they sign in, **Then** full
   access is granted.

---

### User Story 3 - Publish fresh data from local (Priority: P2)

As the owner, I refresh the data on my local machine using the existing
pipeline, publish the resulting snapshot to the host, and the hosted app then
serves that fresher data — clearly showing how current it is and that it is
serving cached/published data.

**Why this priority**: The hosted instance is read-only by design; this is how
its data stays current without running heavy ingest on a free tier. Needed for
the tool to remain useful over time, but the app is still valuable on a single
snapshot, so it ranks below access.

**Independent Test**: Note the hosted `data_as_of`; refresh locally and publish
a new snapshot; reload the hosted app and confirm `data_as_of` advances to the
new snapshot and freshness reflects it.

**Acceptance Scenarios**:

1. **Given** a newer snapshot has been published from local, **When** the owner
   reloads the hosted app, **Then** it reflects the newer `data_as_of`.
2. **Given** the startup freshness check runs on the hosted instance, **When**
   data is stale, **Then** the app surfaces staleness and offers to proceed on
   cached data, indicating that refresh is performed locally and republished
   (the host does not run heavy in-host ingest).
3. **Given** a snapshot publish is interrupted or partial, **When** the owner
   loads the hosted app, **Then** it serves the last known-good snapshot or an
   explicit maintenance/empty state — never a corrupt or partial snapshot.

---

### User Story 4 - Reproducible free deployment (Priority: P3)

As the owner, I can stand up, publish data to, and rebuild the hosted instance
on a free tier by following a documented runbook, with all secrets supplied at
runtime.

**Why this priority**: Makes the deployment repeatable and recoverable (free
tiers can suspend or reset instances), but is a one-time/occasional operator
task rather than day-to-day use.

**Independent Test**: On a clean free-tier hosting account, follow the runbook
end-to-end and reach a running, owner-gated instance serving a published
snapshot, without undocumented steps.

**Acceptance Scenarios**:

1. **Given** a clean hosting account, **When** the owner follows the runbook,
   **Then** a running, owner-gated instance is reachable over HTTPS.
2. **Given** the free instance was suspended/reset, **When** the owner
   re-runs the runbook and republishes the snapshot, **Then** the instance is
   restored with no data loss (snapshot reproducible from local).

---

### Edge Cases

- **Cold start after sleep**: the first request after idle is slow; the app must
  still load successfully (loading state, no error page) and become fast on
  subsequent loads.
- **Stale snapshot**: the hosted freshness check flags staleness and lets the
  owner proceed on cached data; the "refresh" affordance does not trigger heavy
  in-host ingest, but directs the owner to republish from local.
- **Non-owner / unauthenticated access**: denied with no data leakage, including
  direct hits to data endpoints, not just pages.
- **Partial/interrupted snapshot publish**: never served; fall back to prior
  good snapshot or explicit maintenance/empty state.
- **Free-tier cap or suspension**: owner is not silently broken — instance can
  be restored from the runbook; no permanent data loss because data is
  reproducible locally.
- **Missing provider key on host**: optional paid/cross-check path stays
  disabled; the free-tier path remains the default and functional.
- **Directive personal-use flag set in host config**: forced OFF regardless;
  hosted mode is non-waivable for directive language.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The screener MUST be reachable by the owner over the public
  internet from any standard browser/device with no local installation required.
- **FR-002**: Access MUST require sign-in with a single authorized owner identity
  (an identity-provider account, e.g., Google); only the configured owner account
  is authorized.
- **FR-003**: Unauthenticated or unauthorized requests to any page or
  data-bearing endpoint MUST be denied with no screener data returned (no
  pre-sign-in data leakage).
- **FR-004**: The hosted instance MUST serve a **read-only data snapshot
  published from the owner's local environment** and MUST NOT perform heavy data
  ingestion/backfill itself.
- **FR-005**: The owner MUST be able to publish an updated snapshot from local
  such that the hosted app reflects the new data (advanced `data_as_of`) on the
  next load.
- **FR-006**: The hosted app MUST never serve a partial or corrupt snapshot; if
  no valid snapshot is available it MUST show an explicit maintenance/empty state
  rather than an error or blank page.
- **FR-007**: The 009 startup data-freshness check MUST still run on the hosted
  instance, surface staleness, and offer "proceed on cached data"; because
  refresh is local-only, the hosted refresh affordance MUST NOT attempt heavy
  in-host ingest and MUST indicate that refresh happens locally and is
  republished.
- **FR-008**: Every user-visible response on the hosted instance MUST carry
  `data_as_of` and `disclaimer` (unchanged 001 non-negotiable).
- **FR-009**: Directive personal-use mode (`SCREENER_PERSONAL_USE_DIRECTIVE`)
  MUST be forced OFF on the hosted instance, non-waivable regardless of
  environment/config, and zero directive language MUST remain (constitution
  Principle V hosted clause).
- **FR-010**: Provider/API keys and owner-identity/auth secrets MUST be supplied
  to the host as process-local/runtime configuration and MUST NEVER be committed
  to the repository or written to any file in the deployed artifact.
- **FR-011**: The hosted instance MUST be deployable and operable on a free
  hosting tier; cold starts and instance sleep after idle are acceptable and MUST
  NOT cause data loss or corruption.
- **FR-012**: Output determinism MUST be preserved — the same published snapshot
  yields identical screen, regime, sizing, event, and advisor-prompt output as
  the local instance.
- **FR-013**: This feature MUST NOT change any strategy rule, default, citation,
  or backtest baseline (deployment/access/presentation only).
- **FR-014**: A reproducible deployment runbook MUST document standing up,
  publishing data to, and rebuilding the hosted instance on the chosen free tier,
  including required runtime configuration and the owner-identity setup.
- **FR-015**: The hosted instance MUST remain single-user — it MUST NOT
  redistribute, share, sell, or expose data/output to anyone other than the
  authorized owner, and MUST NOT provide public/anonymous data access.
- **FR-016**: Data in transit to the hosted instance MUST be served over HTTPS.

### Key Entities *(include if feature involves data)*

- **Data snapshot**: the published, point-in-time bundle the hosted instance
  serves read-only (prices store, fundamentals/EDGAR cache, calendars,
  manifest), carrying `data_as_of` provenance; produced by the existing local
  pipeline.
- **Authorized owner identity**: the single identity-provider account permitted
  to sign in; all others are denied.
- **Hosted instance**: the running online deployment (frontend + backend) on the
  free tier, reachable over HTTPS.
- **Runtime configuration / secrets**: process-local provider keys and
  auth/owner config supplied at runtime, never present in the repository or
  deployed files.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a device that has never run the project, the owner can open
  the hosted URL, sign in, and complete a momentum screen in under 3 minutes of
  interaction (excluding any cold-start wake time).
- **SC-002**: 100% of unauthenticated or non-owner access attempts are blocked
  with zero screener data exposed, across both pages and data endpoints.
- **SC-003**: After publishing a fresher snapshot from local, the hosted app
  shows the updated `data_as_of` on the next load.
- **SC-004**: For the same published snapshot, the hosted instance produces
  identical candidate ordering and byte-identical advisor-prompt export versus
  the local instance.
- **SC-005**: Running the hosted instance for personal single-user usage costs
  $0 within the chosen free tier's limits.
- **SC-006**: After idle, a cold start returns a usable app (no error page);
  once warm, the app reaches interactive state in under 3 seconds on subsequent
  loads.
- **SC-007**: 100% of user-visible pages/responses on the hosted build carry
  `data_as_of` + `disclaimer` and contain zero directive language (lint passes
  against the hosted build).
- **SC-008**: No provider key or owner secret appears anywhere in the repository
  or in any file of the deployed artifact (scan passes).
- **SC-009**: Following the deployment runbook on a clean free-tier account
  yields a running, owner-gated instance serving a published snapshot, with no
  undocumented steps required.

## Assumptions

- Single-user personal-use scope is retained: no multi-user accounts, no public
  sharing, no redistribution or sale of data or output.
- Data refresh/ingest continues to run on the owner's local machine using the
  existing 009 pipeline; the hosted instance is read-only over a published
  snapshot.
- Because the served data is the owner's own copy accessed only by the owner and
  is not redistributed or shared, the deployment stays within personal-use
  scope while honoring the constitution's hosted-mode directive-OFF clause and
  all disclosure obligations.
- The owner accepts free-tier constraints: cold starts, instance sleep, and
  monthly usage/compute caps.
- The access gate uses the owner's existing identity-provider account (e.g.,
  Google) with a single-account allowlist.
- A platform-provided HTTPS URL is acceptable; a custom domain is not required.
- Momentum remains the primary strategy; value remains postponed (consistent
  with 009 scope) but its existing tests still pass.
- No change to strategy logic, defaults, citations, or backtest baselines.

## Dependencies

- Feature 009 release-readiness (startup freshness gate, robustness/empty-state
  handling, deployment runbook) as the baseline being deployed.
- The existing local data pipeline/scripts (seed, ingest, refresh) used to
  produce and republish snapshots.

## Out of Scope

- Multi-user accounts, sharing, or any public/anonymous access.
- Real-time/intraday data — the snapshot remains end-of-day, as today.
- A mobile-native app — responsive web only, as-is.
- Custom domain and paid always-on hosting (the owner may opt into these later;
  not required for this feature).
- Any change to strategy rules, defaults, citations, or backtest baselines.
