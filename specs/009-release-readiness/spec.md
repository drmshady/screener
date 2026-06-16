# Feature Specification: Release Readiness — Test, Harden, Refresh-on-Start & Deployment Prep

**Feature Branch**: `009-release-readiness`
**Created**: 2026-06-16
**Status**: Draft
**Input**: User description: "review test app and clean it and scan for bugs make sure app gets latest data on start and app is robust and works as intended and report in AI advisor prompt in detail and prepare app for final deployment"

## Overview

This feature is a **stabilization and release-readiness pass** over the existing screener, not a new strategy or new user-facing capability. The screener already supports mid-term momentum and value strategies, side-by-side compare, advisor-prompt export, portfolio sizing, Shariah filtering, and data-integrity detection (feature 008). The goal here is to make the assembled app **demonstrably correct, robust, and current** for the single operator's final personal-use deployment, and to make the **AI advisor prompt fully self-contained and detailed** so an external advisor receives the complete picture.

Scope is **verification, hardening, freshness, and packaging** — no strategy rule, default, citation, or backtest baseline changes (consistent with the constitution's data-integrity and transparency principles).

## Clarifications

### Session 2026-06-16

- Q: How should the startup refresh execute relative to the operator's first action? → A: Manual-trigger with prompt — on start the app detects staleness and prompts the operator to refresh now or proceed on cached data (refresh is operator-initiated, never silent/automatic).
- Q: What scope should a triggered refresh cover? → A: Incremental / stale-only — refresh only sources/records behind the latest completed session, reusing the existing caches (prices store, EDGAR slim cache, calendars); no full rebuild.
- Q: Max acceptable time for the startup staleness-detection check (before the operator can screen or is prompted)? → A: ≤ 3 seconds (detection reads cached `data_as_of` metadata only).
- Q: What is the minimum fix bar required before final deployment? → A: Block on correctness + crashes — all findings causing wrong output, data-integrity violations, or crashes/hangs in primary flows MUST be fixed before release; cosmetic/minor findings may ship deferred with rationale.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - App opens with fresh data and tells me how fresh it is (Priority: P1)

As the sole operator, when I start the app for a screening session, I want it to automatically bring its market and fundamentals data up to date (or clearly tell me it could not), so that every screen, regime read, and candidate I look at reflects the latest available data rather than a stale snapshot from a previous session.

**Why this priority**: Stale data silently producing confident-looking results is the single highest-risk failure for a decision-support tool. Today the app performs no refresh on start, so freshness depends on the operator remembering to run manual data steps. This is the foundation of "works as intended."

**Independent Test**: Start the app after the data has gone stale (e.g., a day later). Confirm that on first interaction the app reports an updated `data_as_of` for the relevant sources, or surfaces an explicit, non-blocking warning that refresh failed and results are based on cached data dated X.

**Acceptance Scenarios**:

1. **Given** the app was last used and cached data is older than the latest available trading day, **When** the operator starts the app, **Then** the app detects the staleness and prompts the operator to refresh now or proceed on cached data; choosing "refresh" updates the relevant sources so the displayed `data_as_of` reflects the newly fetched data.
2. **Given** a data source is unreachable at startup, **When** the operator starts the app, **Then** the app continues to function using the most recent cached data and surfaces a clear, non-blocking staleness notice stating which source is stale and as of when.
3. **Given** data is already current for the latest trading day, **When** the operator starts the app, **Then** no redundant full refresh delays the session beyond a reasonable threshold and the app indicates data is current.
4. **Given** a refresh is in progress, **When** the operator views any data-bearing surface, **Then** the surface indicates refresh status rather than presenting partial data as final.

---

### User Story 2 - The advisor prompt is complete and detailed enough to stand alone (Priority: P1)

As the operator exporting a candidate to an external AI advisor, I want the generated prompt to contain a complete, detailed, self-contained account of the candidate — its gate results, price levels, regime, the live strategy declaration with citations, data freshness and any integrity warnings, and the mandatory honesty/limitations block — so that the advisor can reason correctly without access to the app and without me hand-editing the prompt.

**Why this priority**: The advisor prompt is the app's primary externally-consumed artifact. If it omits data freshness, integrity flags, or limitations, the external advisor reasons on an incomplete or misleadingly confident basis, which violates the honesty principle. The user explicitly asked for this to be "detailed."

**Independent Test**: Export the advisor prompt for a clean candidate and for an integrity-flagged candidate. Confirm both prompts are self-contained (no dangling references to app-only context), include data-as-of and freshness, surface any integrity warning verbatim, and carry the mandatory honesty/limitations block driven by the real backtest bias check.

**Acceptance Scenarios**:

1. **Given** a candidate produced by a live screen, **When** the operator copies the advisor prompt, **Then** the prompt includes: candidate identity and sector, every gate's pass/fail with values, derived price levels, current market regime, the strategy's declared rules and citations, the data-as-of/freshness for each material input, and the mandatory honesty block.
2. **Given** a candidate that was flagged by the data-integrity detector, **When** the operator copies the advisor prompt, **Then** the prompt prominently includes the per-candidate data-integrity warning so the external advisor cannot miss it.
3. **Given** a strategy whose survivorship/bias check currently fails or warns, **When** the prompt is generated, **Then** that limitation is stated honestly in the prompt's limitations section rather than omitted.
4. **Given** any generated prompt, **When** it is inspected, **Then** it contains zero directive trading language (no "buy/sell/recommended/strong buy") and frames everything as analysis inputs.

---

### User Story 3 - I can trust the app is bug-free and robust because the full suite proves it (Priority: P1)

As the operator preparing for final deployment, I want the entire automated test suite (backend and frontend, unit through end-to-end) to pass green on a clean checkout, with known dead code and obvious bugs removed, so that I have evidence the app works as intended before I rely on it for real decisions.

**Why this priority**: "Review, test, clean, scan for bugs, robust, works as intended" is the core of the request. A green full suite plus a deliberate bug scan is the verifiable proof of readiness.

**Independent Test**: From a clean checkout, run the complete backend and frontend test suites and confirm 100% pass with no skipped financial-logic tests; confirm the bug-scan findings are either fixed or explicitly logged with rationale.

**Acceptance Scenarios**:

1. **Given** a clean checkout on the release branch, **When** the full backend test suite runs, **Then** all tests pass with no errors and no silently skipped financial-logic tests.
2. **Given** a clean checkout, **When** the full frontend unit and end-to-end suites run, **Then** all tests pass including the directive-language lint and the data-as-of/disclaimer presence checks.
3. **Given** a bug scan across the app's runtime surfaces, **When** issues are found (e.g., unhandled error paths, crashes on empty/malformed data, broken navigation), **Then** each is fixed or logged with an explicit, justified decision to defer.
4. **Given** dead code, unused modules, or obsolete artifacts are identified, **When** the cleanup runs, **Then** they are removed without changing any strategy rule, default, citation, or backtest baseline, and the suite remains green.

---

### User Story 4 - The app degrades gracefully instead of breaking (Priority: P2)

As the operator, when something goes wrong at runtime — a data source is down, a screen returns no candidates, a fundamentals record is missing, or a network call times out — I want the app to show a clear, honest message and remain usable, rather than crash, hang, or present a blank/misleading screen.

**Why this priority**: Robustness under real-world failure conditions is what separates "passes tests" from "works as intended" in daily use. It is P2 because it builds on the correctness foundation of P1.

**Independent Test**: Simulate each failure mode (source down, empty result, missing fundamentals, timeout) and confirm the app shows a clear message, keeps the rest of the UI functional, and never presents partial data as authoritative.

**Acceptance Scenarios**:

1. **Given** a screen produces zero candidates, **When** the results render, **Then** the app shows an explicit empty-state explanation rather than a blank or error page.
2. **Given** a candidate is missing a material input (e.g., fundamentals), **When** it is evaluated, **Then** the app handles it deterministically — excluding or flagging it with a stated reason — without crashing the run.
3. **Given** a backend call fails or times out, **When** the frontend receives the error, **Then** it shows a retryable, human-readable error and the rest of the app stays navigable.

---

### User Story 5 - The app is packaged and documented for one-command final deployment (Priority: P2)

As the operator doing the final deployment on my own machine, I want a documented, repeatable runbook and a production build that starts the app cleanly, so that I can deploy and re-deploy without rediscovering steps each time.

**Why this priority**: "Prepare app for final deployment" requires a reproducible packaging/runbook so the validated build is the one that actually runs. P2 because it depends on P1 correctness being established first.

**Independent Test**: Follow the deployment runbook from scratch on the target machine and confirm the app builds and starts in production mode, serves the validated behavior, and the runbook has no missing or incorrect steps.

**Acceptance Scenarios**:

1. **Given** the documented deployment runbook, **When** the operator follows it on a clean environment, **Then** the app builds and starts in production mode without manual fixes.
2. **Given** the production build is running, **When** the operator exercises the primary flows (screen, candidate detail, advisor prompt, portfolio), **Then** behavior matches the test-validated behavior.
3. **Given** the release is finalized, **When** the operator inspects the repository, **Then** working-tree changes are committed on the release branch and the deployment configuration (data directories, optional provider keys handled per process-only convention) is documented.

---

### Edge Cases

- **Stale-on-start with no network**: App must open and operate on cached data with a prominent staleness banner; it must never block the operator out.
- **Partial refresh**: Some sources refresh, others fail — each surface must reflect the freshness of its own inputs, not a single global timestamp that overstates currency.
- **Latest trading day ambiguity** (weekends/holidays): "Latest data" is defined relative to the latest completed trading session, not the calendar day, so a Sunday start does not perpetually report "stale."
- **Advisor prompt for a flagged candidate**: Integrity warning must appear even though the candidate is demoted, never silently dropped.
- **Empty universe after liquidity gate**: Must produce a clear empty-state, not an error.
- **Provider key absent**: Optional paid-provider features stay disabled gracefully; free-tier path remains the default and functional.
- **Refresh slowness**: A long refresh must not make the app appear hung — progress/status must be visible and the operator must retain control.

## Requirements *(mandatory)*

### Functional Requirements

**Data freshness on start**

- **FR-001**: On application start, the system MUST detect whether its material data sources (prices, fundamentals, regime inputs, events/calendar as applicable) are current to the latest completed trading session, and when any are stale it MUST prompt the operator to either refresh now or proceed on cached data. Refresh MUST be operator-initiated, never silent or automatic.
- **FR-002**: When a refresh cannot complete (source unreachable, timeout), the system MUST continue operating on the most recent cached data and surface a clear, non-blocking staleness notice naming the affected source and its `data_as_of`.
- **FR-003**: A triggered refresh MUST be incremental — refreshing only sources/records behind the latest completed trading session by reusing existing caches (prices store, EDGAR slim cache, calendars) — and MUST NOT perform a full universe/fundamentals rebuild. When data is already current, the system MUST skip refresh and report data as current.
- **FR-004**: Every data-bearing surface MUST reflect the freshness of its own material inputs; a global timestamp MUST NOT overstate the currency of any individual input.
- **FR-005**: "Latest data" MUST be defined relative to the latest completed trading session (accounting for weekends/holidays), not the raw calendar date.

**Advisor prompt completeness**

- **FR-006**: The advisor prompt MUST be fully self-contained — it MUST NOT reference context available only inside the app — so an external advisor can reason without the app.
- **FR-007**: The advisor prompt MUST include, for the exported candidate: identity and sector, each gate's pass/fail with the evaluated values, derived price levels, current market regime, the live strategy declaration with citations, and the `data_as_of`/freshness of each material input.
- **FR-008**: When a candidate carries a data-integrity warning, the advisor prompt MUST include that warning prominently and verbatim.
- **FR-009**: The advisor prompt MUST include the mandatory honesty/limitations block driven by the strategy's real backtest bias/survivorship check, stating current known limitations honestly rather than omitting them.
- **FR-010**: The advisor prompt MUST contain zero directive trading language and MUST frame all content as analysis inputs.

**Correctness, bug scan & cleanup**

- **FR-011**: The complete backend test suite MUST pass on a clean checkout with no errors and no silently skipped financial-logic tests.
- **FR-012**: The complete frontend unit and end-to-end suites MUST pass on a clean checkout, including the directive-language lint and the `data_as_of`/`disclaimer` presence checks.
- **FR-013**: The system MUST undergo a deliberate bug scan across its runtime surfaces (API endpoints, screen/candidate/advisor/portfolio flows, data loaders). Every finding that causes wrong output, a data-integrity violation, or a crash/hang in a primary flow MUST be fixed before release; cosmetic or minor findings MAY be deferred with an explicit, logged rationale.
- **FR-014**: Identified dead code, unused modules, and obsolete artifacts MUST be removed without changing any strategy rule, default, citation, or backtest baseline, and the suite MUST remain green afterward.
- **FR-015**: All cleanup and fixes MUST preserve the determinism guarantee: the same data snapshot MUST produce the same screen, regime, sizing, and event output.

**Robustness**

- **FR-016**: A screen that yields zero candidates MUST render an explicit empty-state with a stated reason, never a blank or error page.
- **FR-017**: A candidate missing a material input MUST be handled deterministically — excluded or flagged with a stated reason — without aborting the run.
- **FR-018**: Backend failures and timeouts surfaced to the frontend MUST produce a retryable, human-readable error while keeping the rest of the app navigable.
- **FR-019**: Every API response exposing user-visible data MUST continue to carry `data_as_of` and `disclaimer`, and the layout shell MUST render both unconditionally.

**Deployment readiness**

- **FR-020**: The repository MUST include a documented, repeatable deployment runbook that takes the operator from a clean environment to a running production build without manual fixes.
- **FR-021**: The production build MUST serve the test-validated behavior for the primary flows (screen, candidate detail, advisor prompt export, portfolio).
- **FR-022**: Deployment configuration MUST document data directories and the process-only handling of optional provider keys (keys are never written to any file), consistent with personal-use single-machine scope.
- **FR-023**: At finalization, working-tree changes MUST be committed on the release branch with the app in a known-good, suite-green state.

### Key Entities *(include if feature involves data)*

- **Data Freshness Record**: Per-source freshness state — source name, `data_as_of` (latest completed trading session covered), last refresh attempt outcome (success/failed/skipped-current), and staleness flag. Surfaces drive their freshness display from this.
- **Advisor Prompt Document**: The self-contained exported artifact — candidate facts, gate results, price levels, regime, strategy declaration + citations, per-input freshness, integrity warnings, and the honesty/limitations block.
- **Bug Scan Finding**: A discovered defect or robustness gap — location, description, severity, and resolution (fixed | deferred-with-rationale).
- **Deployment Runbook**: The ordered, reproducible steps and configuration required to build and start the validated production app on the target machine.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Starting the app after data has gone stale results in current data (or an explicit staleness notice) on the first data-bearing interaction, with no silent stale results, in 100% of trials.
- **SC-002**: The startup staleness-detection check completes in ≤ 3 seconds before the operator can screen or is prompted to refresh; when all sources are current, no refresh is performed.
- **SC-003**: When a data source is down at start, the app remains fully usable on cached data and displays a staleness notice in 100% of trials; it never blocks the operator out.
- **SC-004**: 100% of generated advisor prompts are self-contained and include candidate facts, gate results, price levels, regime, strategy citations, per-input freshness, integrity warnings (when present), and the honesty/limitations block.
- **SC-005**: 0 generated advisor prompts contain directive trading language.
- **SC-006**: The complete backend and frontend test suites pass at 100% on a clean checkout, with 0 silently skipped financial-logic tests.
- **SC-007**: 0 correctness, data-integrity, or crash/hang findings remain open in primary flows at release; every other finding is either fixed or logged with explicit deferral rationale — 0 unaddressed findings.
- **SC-008**: Each simulated failure mode (source down, empty result, missing fundamentals, timeout) produces a clear message and a still-usable app in 100% of trials — 0 crashes, hangs, or blank/misleading screens.
- **SC-009**: A first-time follow of the deployment runbook on a clean environment yields a running production build with 0 missing or incorrect steps.
- **SC-010**: The same data snapshot reproduces identical screen, regime, sizing, and event output across repeated runs — determinism preserved at 100%.

## Assumptions

- **Personal-use single-machine deployment**: "Final deployment" means the constitution's v1 scope — one operator, one machine, no redistribution, free-tier data sources by default. Hosted/multi-user deployment is explicitly out of scope.
- **No strategy or baseline changes**: This pass changes only verification, freshness, presentation, robustness, and packaging. Strategy rules, defaults, citations, and backtest baselines are frozen.
- **Existing data sources reused**: Refresh-on-start uses the already-integrated free providers (EDGAR, yfinance/Stooq, SPUS, calendars); no new paid provider is required, though the optional paid upgrade path remains available per-strategy.
- **Latest available data**: Where the free providers themselves lag (e.g., end-of-day only), "latest" means the latest the free tier exposes; the app reports that as-of date honestly rather than implying intraday currency.
- **Determinism and integrity detection (feature 008) remain authoritative**: Integrity-flagged candidates are demoted, never excluded, and their warnings flow into the advisor prompt.
- **Provider keys stay process-local**: Consistent with existing convention, any optional provider key is supplied inline/process-only and never written to a file.
- **Robustness is bounded to known runtime surfaces**: The bug scan targets the app's actual endpoints and primary user flows, not hypothetical future features.
