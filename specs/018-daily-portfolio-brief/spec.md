# Feature Specification: Daily AI Portfolio Brief (Email Digest)

**Feature Branch**: `018-daily-portfolio-brief`  
**Created**: 2026-07-08  
**Status**: Draft  
**Input**: User description: "i want to create ai loop to get daily news that may affect us stock and check my portfolio and give me summary of its status and five clear direct recommendations and summarize my portfolio and send result to my email"

## Overview

An automated, once-per-trading-day cycle ("the daily brief loop") that, without the owner
having to open the app, assembles a single self-contained brief covering: (a) daily market
news and sentiment that may affect US stocks the owner holds or watches, (b) a summary of the
owner's portfolio status (value, profit/loss, risk exposure, and holdings that need
attention), and (c) a short, prioritized list of exactly five clear next-step
recommendations. The brief is delivered to the owner's own email address. It is a synthesis
and delivery feature over analysis the app already produces — it introduces **no** new
screening rule, gate, indicator, citation, sizing model, or backtest baseline.

## Clarifications

### Session 2026-07-08

- Q: Where should the daily loop run (this decides whether direct recommendations are allowed)? → A: On the hosted deployment (always-on).
- Q: What time window of news does each brief cover? → A: News since the last delivered brief (typically ~1 trading day), widening to cover the elapsed period across market holidays/gaps, so items are not repeated day to day.
- Q: How are the five recommendations selected and ordered? → A: Rule-ranked deterministically from the app's existing signals — holdings-attention triggers first (risk/heat breach, stop proximity, pipeline stage change), then news/sentiment materiality, then portfolio-level actions to fill out five. Any AI narrative model only phrases the items; it never selects them and never invents signals.
- Q: What triggers the daily brief generation/send? → A: It runs immediately after the existing daily data-refresh job completes (feature 011 CI cron), so the brief reflects the freshest snapshot and is ready before the next market open. It targets the just-refreshed completed session.
- Q: How should the brief email be sent from an unattended daily job? → A: Gmail SMTP using an app password, supplied as a process-local secret (never committed/logged), sending to the owner's own inbox. No new third-party email service.
- Q: Direct vs neutral recommendation wording, given hosted execution? → A: Direct (directive) wording is desired. The constitution was amended to v1.2.0 to permit the personal-use directive exception on a single-owner, access-gated hosted instance (output reaching only the owner). Direct wording is therefore allowed here, gated behind the personal-use directive flag and the single-owner access gate, and each item still carries citation, data-as-of, and the non-advice disclosure. Neutral framing remains the default when the flag is OFF and is mandatory if the instance ever becomes multi-user/shared/third-party-exposed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Daily portfolio status arrives in my inbox (Priority: P1)

As the single owner, I receive one email each trading day that summarizes my portfolio's
current status — total value, overall and per-holding profit/loss, my current risk exposure,
and which holdings need attention — so I stay informed without opening the app.

**Why this priority**: This is the core value and the smallest viable slice. Even with no news
overlay and no recommendation list, a reliable daily portfolio-status email delivered to the
owner is independently useful and is the foundation the other stories extend.

**Independent Test**: Enable the daily brief for an owner who has an imported portfolio, let
the loop run for a trading day, and confirm a single email arrives containing total value,
profit/loss, risk exposure, and an attention list — with data-as-of and the non-advice
disclaimer present.

**Acceptance Scenarios**:

1. **Given** the owner has holdings and the daily brief is enabled, **When** the loop runs for
   a completed trading session, **Then** exactly one email is delivered to the owner's
   allowlisted address containing the portfolio value, overall profit/loss, per-holding
   profit/loss, current risk exposure, and a list of holdings needing attention.
2. **Given** the same portfolio and the same data snapshot, **When** the brief is generated
   twice, **Then** the two briefs are identical (deterministic output).
3. **Given** the owner has no holdings recorded, **When** the loop runs, **Then** the email is
   still delivered and clearly states the portfolio is empty rather than failing silently.
4. **Given** every generated email, **When** it is opened, **Then** it carries the data-as-of
   date and the plain-language non-advice disclaimer.

---

### User Story 2 - News and sentiment that may affect my stocks (Priority: P2)

As the owner, the daily brief includes market news and sentiment items that may affect the US
stocks I hold or watch — plus the overall market regime/context — with each item tied to the
tickers it touches, so I understand what changed today and why it matters to me.

**Why this priority**: The "news that may affect US stocks" is the owner's explicit motivation
and materially increases the brief's value, but it builds on the P1 status email and can be
added without changing delivery.

**Independent Test**: For an owner holding at least one ticker with recent news/sentiment
coverage, run the loop and confirm the brief lists the relevant news/sentiment items mapped to
the affected holdings, plus a short market-context note, each with its source and as-of date.

**Acceptance Scenarios**:

1. **Given** one or more holdings have recent news or a sentiment/narrative signal, **When**
   the brief is generated, **Then** those items appear in the brief, each attributed to the
   ticker(s) it affects and each showing its source and as-of date.
2. **Given** a day with no material news for any holding, **When** the brief is generated,
   **Then** the news section states there is nothing material rather than omitting the section
   or erroring.
3. **Given** the market-regime and market-events context the app already computes, **When**
   the brief is generated, **Then** a concise market-context line is included with its source
   and as-of date.

---

### User Story 3 - Five clear recommendations (Priority: P3)

As the owner, the daily brief ends with a prioritized list of exactly five clear next-step
recommendations drawn from my portfolio status and the day's news, so I know what to consider
acting on first.

**Why this priority**: This is the sharpest, most decision-oriented part of the request, but
it depends on the P1 status and P2 news synthesis being in place, and it is the part most
constrained by the no-advice boundary (see Assumptions), so it is sequenced last.

**Independent Test**: Run the loop for an owner with holdings and news coverage; confirm the
brief contains a clearly labeled list of exactly five prioritized recommendation items, each
tied to a specific holding or portfolio action and each accompanied by the required disclosure.

**Acceptance Scenarios**:

1. **Given** the brief has been assembled, **When** the recommendation section is produced,
   **Then** it contains exactly five items, ordered by priority, each referencing a specific
   ticker or a specific portfolio-level action and a one-line reason grounded in the brief's
   own facts.
2. **Given** the personal-use directive setting is OFF, or the instance is multi-user / shared
   / third-party-exposed, **When** the recommendations are worded, **Then** they use neutral,
   non-directive framing ("candidate for review", "consider reviewing") and contain no
   directive verbs ("buy"/"sell"/"strong buy").
3. **Given** the personal-use directive setting is ON and the deployment is single-owner and
   access-gated so the brief reaches only the owner (per constitution v1.2.0), **When** the
   recommendations are worded, **Then** they may use direct action language, and each still
   carries the strategy citation(s), the data-as-of date, and the non-advice / limitations
   disclosure.
4. **Given** fewer than five holdings or a quiet news day, **When** the recommendations are
   produced, **Then** the list still contains five items by including portfolio-level or
   watchlist items (e.g., "no action indicated for X"), never fabricating signals.

---

### Edge Cases

- **Non-trading day / holiday**: On a day with no completed US trading session, the loop does
  not send a misleading "today's" brief; it either skips with a recorded reason or clearly
  labels the data as the last completed session.
- **Stale or missing data snapshot**: If the underlying data is stale or a required input is
  missing, the brief states the staleness/limitation rather than presenting numbers as fresh.
- **Email delivery failure**: If sending fails, the loop retries within bounds and records the
  failure; a persistent failure raises an owner-visible notification rather than passing
  silently.
- **Duplicate run / re-run**: If the loop runs more than once for the same session, the owner
  receives at most one brief for that session (idempotent delivery).
- **AI narrative budget exhausted**: If the optional AI-narrative budget cap is already
  reached, the brief degrades to the deterministic source-only template and is still delivered
  in full.
- **Recipient not the owner**: The brief is only ever sent to the single owner's allowlisted
  address; it is never sent to any third-party recipient.
- **Feature disabled**: When the daily brief is not enabled, no email is sent and no scheduled
  run occurs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an opt-in daily brief that is OFF by default; when
  enabled it runs once per completed US trading session — triggered immediately after the
  existing daily data-refresh job (feature 011) completes so it reflects the freshest
  snapshot — and when disabled performs no scheduled run and sends no email.
- **FR-002**: The system MUST assemble the brief from data the app already produces
  (portfolio holdings and status, profit/loss, risk exposure, pipeline/attention state, market
  news and sentiment/narrative, market regime and market events) and MUST NOT introduce any
  new screening rule, gate threshold, indicator definition, citation, sizing model, or backtest
  baseline.
- **FR-003**: The portfolio-status section MUST include total portfolio value, overall
  profit/loss, per-holding profit/loss, current risk exposure, and a list of holdings needing
  attention.
- **FR-004**: The news section MUST include news and sentiment items relevant to the owner's
  held and watched tickers, covering the window since the last delivered brief (typically ~1
  trading day, widening to cover the elapsed period across market holidays/gaps so items are
  not repeated across briefs), each attributed to the affected ticker(s) and each carrying its
  source and as-of date, plus a concise market-context line derived from the app's existing
  regime and market-events outputs.
- **FR-005**: The recommendation section MUST contain exactly five prioritized items, each
  referencing a specific ticker or portfolio-level action with a one-line reason grounded only
  in facts already present in the brief (no fabricated signals). Selection and ordering MUST be
  a deterministic rule-based ranking over existing signals — holdings-attention triggers
  (risk/heat breach, stop proximity, pipeline stage change) first, then news/sentiment
  materiality, then portfolio-level actions to fill five. Any AI narrative model MAY only
  phrase the selected items; it MUST NOT select them or introduce new signals.
- **FR-006**: When the personal-use directive setting is OFF, or whenever the instance is
  multi-user, shared, sold, or otherwise exposed to any third party, the recommendations and
  all brief copy MUST use neutral, non-directive framing and MUST contain no directive trading
  verbs.
- **FR-007**: The recommendations MAY use direct action language when ALL of the following
  hold: the personal-use directive flag is ON, the deployment enforces a single-owner access
  gate (the brief reaches only the owner's allowlisted address), and the instance is not
  multi-user/shared (consistent with constitution v1.2.0). Even then, each directive item MUST
  carry the relevant strategy citation(s), the data-as-of date, and the non-advice /
  limitations disclosure.
- **FR-007a**: Because the hosted deployment force-disables the personal-use directive flag
  today (feature 010, FR-009), the implementation MUST add a single-owner-gated carve-out that
  permits the flag to be enabled for this access-gated owner-only host; absent that carve-out,
  the brief MUST fall back to neutral framing (FR-006) rather than silently dropping the
  recommendation section.
- **FR-008**: Every delivered brief MUST carry the data-as-of date and the plain-language
  non-advice disclaimer, and MUST surface any active integrity or staleness warning rather than
  presenting affected numbers as fresh/clean.
- **FR-009**: The system MUST deliver the brief only to the single owner's allowlisted email
  address and MUST NOT send it to any other recipient.
- **FR-010**: The system MUST deliver at most one brief per completed trading session
  (idempotent), even if the loop is triggered more than once for that session.
- **FR-011**: The system MUST NOT send a misleading brief on a non-trading day; it either skips
  with a recorded reason or clearly labels the brief against the last completed session.
- **FR-012**: On email-send failure the system MUST retry within a bounded policy and record
  the outcome; a persistent failure MUST raise an owner-visible notification rather than fail
  silently.
- **FR-013**: Given the same data snapshot and the same portfolio, the generated brief content
  MUST be deterministic (identical on re-run), consistent with the app's determinism guarantee.
- **FR-014**: The system MUST record each run's outcome (delivered / skipped / failed, with the
  session it corresponds to) so the owner can confirm whether today's brief was sent.
- **FR-015**: The brief MUST be sent via Gmail SMTP authenticated with an app password; the app
  password and the recipient address MUST be handled as process-local runtime configuration and
  MUST NOT be written to any committed artifact or logged in plaintext.
- **FR-016**: The brief's content MUST be readable as a standalone message (no dependency on
  opening the app to understand it), while any deep-link references it includes remain optional.

### Key Entities *(include if feature involves data)*

- **Daily Brief**: The assembled message for one trading session — contains the portfolio-status
  summary, the news/sentiment section, the market-context line, the five recommendations, and
  the required disclosures (data-as-of, disclaimer, citations, any warnings).
- **Recommendation Item**: One of exactly five prioritized entries — references a specific
  ticker or a portfolio-level action, carries a priority rank and a one-line fact-grounded
  reason, and is worded per the directive/neutral gating rules.
- **News / Sentiment Item**: A single dated news or sentiment/narrative signal mapped to the
  ticker(s) it affects, with its source and as-of date.
- **Delivery Run Record**: The outcome of one loop execution — the session it targets, the
  status (delivered/skipped/failed), the recipient, and the timestamp, used for idempotency and
  owner-visible confirmation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On each enabled trading day, the owner receives exactly one brief email for that
  session (no missed and no duplicate sends), verified across a multi-day run.
- **SC-002**: Every delivered brief contains all required sections — portfolio status, news,
  market context, exactly five recommendations — plus the data-as-of date and non-advice
  disclaimer; a section is never silently missing.
- **SC-003**: The recommendation list contains exactly five prioritized items in 100% of
  delivered briefs, regardless of portfolio size or news volume.
- **SC-004**: When the directive setting is OFF or the instance is hosted, 0 briefs contain any
  directive trading verb (automated copy lint passes on every brief).
- **SC-005**: Regenerating a brief from the same data snapshot and portfolio produces identical
  content in 100% of checks (determinism).
- **SC-006**: The owner can enable, disable, and confirm the delivery outcome of the daily
  brief without editing code, and disabling it stops all sends within one day.
- **SC-007**: On a simulated email-send failure, the failure is retried and then surfaced to
  the owner within the same run, with no silently dropped brief.
- **SC-008**: On a non-trading day, 0 misleading "today" briefs are sent.

## Assumptions

- **Single owner, personal recipient.** The tool is single-user; the brief is delivered only to
  the owner's own allowlisted email (`dr.mshady@gmail.com` per current configuration) and never
  to third parties. This keeps the "five clear direct recommendations" within the constitution's
  Principle V personal-use directive exception (first-person guidance to the tool's own
  operator), which — per the v1.2.0 amendment — applies to a single-owner, access-gated hosted
  instance whose output reaches only the owner.
- **Directive wording is flag-gated and access-gate-safe.** "Direct recommendations" use action
  language only when the personal-use directive flag is ON and the single-owner access gate is
  enforced (brief reaches only the owner); the default (flag OFF) and any multi-user / shared /
  third-party-exposed context fall back to neutral, non-directive framing with the same five
  items.
- **Reuse of existing analysis.** Portfolio status (value, profit/loss, risk exposure/heat,
  pipeline attention), news and sentiment/narrative, market regime, and market events are taken
  from the app's existing outputs; this feature orchestrates and delivers them and adds no new
  financial logic.
- **Once daily, aligned to the completed session.** The brief targets the last completed US
  trading session and is delivered once per such session on a schedule the owner controls
  (default: after market close / before the next open); intraday updates are out of scope.
- **Email is the delivery channel for v1.** Other channels (SMS, push, in-app-only) are out of
  scope for this feature. The email is self-contained plain content; rich formatting is a
  presentation detail, not a requirement.
- **Determinism and disclosures are inherited obligations.** The brief honors the app-wide
  determinism guarantee and always carries data-as-of and the non-advice disclaimer, consistent
  with all prior features.
- **Runs on the hosted deployment with a single-owner access gate.** The loop runs as part of
  the always-on hosted deployment (feature 010) behind the existing single-email allowlist.
  Direct wording is available there under constitution v1.2.0 once the personal-use directive
  flag is enabled via the single-owner-gated carve-out (FR-007a); without that carve-out it
  degrades to neutral framing automatically per FR-006.

## Dependencies

- The existing single-owner portfolio record and its status/profit-loss/risk outputs.
- The existing AI sentiment & narrative pipeline and news sources (feature 014), including its
  spend-cap/degradation behavior.
- The existing market-regime and market-events outputs.
- Gmail SMTP with an app password (process-local, non-committed credential) for sending to the
  owner's allowlisted address.
- The existing personal-use directive flag and hosted-mode detection that force neutral framing
  when applicable.
