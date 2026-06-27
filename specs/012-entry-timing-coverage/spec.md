# Feature Specification: Entry-Timing & Candidate Coverage

**Feature Branch**: `012-entry-timing-coverage`
**Created**: 2026-06-27
**Status**: Draft
**Input**: User description: "I want the update of Halal Terminal universe to be every 3 months to limit usage of the API key; I want the app to expand the list of strategy candidates even if some non-essential gates are skipped; I want to add a feature to determine stocks at a good entry point — pivot proximity (0% ≤ (price − pivot)/pivot ≤ +5%, pivot = high of the latest base or cup-with-handle handle, exclude anything extended >5% above pivot); trend (price above SMA-200); volume confirmation on breakout (≥1.4×, preferably ≥1.5×, the 50-day average volume); base maturity (flat base ≥5 weeks; cup / cup-with-handle / double-bottom ≥7 weeks); base depth (correction from base high to low ≤30–35%); not-extended from SMA-200 ((price − SMA-200)/SMA-200 ≤ 40%)."

## Overview

Three independent slices layered on the live single-owner screener. Each is independently shippable and testable. Listed below by priority (value × criticality), which differs from the order the owner stated them.

- **US1 (P1) — Entry-timing quality overlay.** A neutral, mechanically-defined per-candidate diagnostic that classifies whether a candidate is presently near a sound technical entry (within a small window above a base pivot, in an uptrend, on a confirming-volume breakout, off a mature, shallow base, and not over-extended) — with an optional "entry-ready only" filter.
- **US2 (P2) — Expanded candidate coverage.** Surface more candidates by treating clearly-labelled *non-essential* gates as soft: when such a gate cannot be evaluated or does not pass, the candidate is retained (and ranked below fully-clean candidates) rather than silently dropped, with full transparency about which gates were skipped.
- **US3 (P3) — Quarterly Shariah universe refresh.** Reduce Halal Terminal API-key consumption by refreshing the externally-sourced compliant universe on a ~quarterly (90-day) cadence instead of the current frequent cadence, while continuing to surface staleness honestly.

### Constitutional alignment (non-negotiable, applies to all three slices)

- **No directive language.** The entry-timing overlay classifies *technical state* (e.g. "near pivot", "extended", "immature base"). It MUST NOT emit "Buy", "Strong buy", "Recommended", or any directive framing. "Good entry point" is rendered as an objective, cited classification, never as advice to trade.
- **CAN SLIM stays deferred.** The entry-timing overlay is a post-screen *diagnostic*, not a new gated strategy, and MUST NOT be presented under O'Neil's CAN SLIM citation. Each entry rule is attributed to the specific peer-reviewed / practitioner source it derives from (base-breakout and pivot concepts → Minervini (2013), already cited by the existing `shortterm_minervini_vcp` strategy).
- **Determinism preserved.** Same snapshot → same entry classification, same candidate set, same ordering, same refresh decision. No hidden randomness or wall-clock dependence beyond the explicit refresh-cadence check.
- **`data_as_of` + `disclaimer`** ride every response that exposes new data, and the hosted directive-OFF force is unchanged.
- **Screening/selection rules, defaults, citations, indicators, and backtest baselines for existing strategies are unchanged.** US2 changes only *which already-computed candidates are surfaced and how they are ordered/labelled*, never a gate's threshold. New indicators introduced for US1 get golden-fixture tests before any surface depends on them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Entry-timing quality overlay (Priority: P1)

The owner runs a mid-term momentum screen and wants to know, for each surviving candidate, whether the stock is *right now* at a technically sound entry — close above a real base pivot, trending up, breaking out on confirming volume, off a mature and shallow base, and not stretched far from its long-term trend — so that timing, not just selection, informs the watchlist. The owner can optionally narrow the list to only entry-ready names.

**Why this priority**: This is the headline new capability and the owner's primary intent ("determine stocks at a good entry point"). It delivers value on its own, independent of US2 and US3.

**Independent Test**: On a frozen snapshot, run a screen and confirm each candidate carries an entry-timing classification with the six component results, that the numeric thresholds match the specification, that toggling the "entry-ready only" filter narrows the set deterministically, and that no directive language appears.

**Acceptance Scenarios**:

1. **Given** a candidate whose latest price is 3% above its most recent base pivot, above its SMA-200, broke out on volume ≥1.4× its 50-day average, off a 9-week cup with a 22% depth, and 18% above SMA-200, **When** the entry overlay runs, **Then** the candidate is classified **entry-ready** and every component shows pass with its measured value.
2. **Given** a candidate trading 9% above its base pivot, **When** the overlay runs, **Then** the **pivot-proximity** component fails with reason "extended >5% above pivot" and the candidate is classified **not entry-ready** (extended).
3. **Given** a candidate that broke out on volume only 1.1× its 50-day average, **When** the overlay runs, **Then** the **volume-confirmation** component fails ("weak-volume breakout") and the candidate is not entry-ready.
4. **Given** a candidate off a 4-week flat base (or a 6-week cup), **When** the overlay runs, **Then** the **base-maturity** component fails ("immature base") and the candidate is not entry-ready.
5. **Given** a candidate whose base corrected 41% from high to low, **When** the overlay runs, **Then** the **base-depth** component fails ("base too deep") and the candidate is not entry-ready.
6. **Given** a candidate trading 48% above its SMA-200, **When** the overlay runs, **Then** the **not-extended** component fails ("far above SMA-200") and the candidate is not entry-ready.
7. **Given** insufficient price history to detect a base or pivot, **When** the overlay runs, **Then** the candidate is classified **entry-undetermined** (not silently entry-ready and not excluded), with a neutral "insufficient data to assess entry" rationale.
8. **Given** the "entry-ready only" filter is ON, **When** the screen renders, **Then** only entry-ready candidates appear; **Given** it is OFF, **Then** all candidates appear, each annotated with its entry classification.

---

### User Story 2 - Expanded candidate coverage (Priority: P2)

The owner finds the candidate list too short because a candidate that passes the core thesis but lacks data for a secondary/style gate is dropped entirely. The owner wants those candidates retained — clearly marked as having a skipped non-essential gate and ranked below fully-clean candidates — so coverage widens without hiding the trade-off.

**Why this priority**: Directly increases usable output and addresses a recurring owner frustration, but is secondary to the entry-timing capability and depends on a clear essential/non-essential gate split.

**Independent Test**: On a frozen snapshot, run a screen with default gate classifications, confirm that candidates which previously dropped on a *non-essential* gate now appear, are tagged with the skipped gate and reason, are ordered below all fully-clean candidates, and that no candidate failing an *essential* gate is ever surfaced.

**Acceptance Scenarios**:

1. **Given** a candidate that passes the liquidity gate, data-integrity check, and the strategy's primary thesis gate but is missing the input for a non-essential style gate, **When** the screen runs with expanded coverage enabled, **Then** the candidate is retained with that gate marked `skipped` and a reason.
2. **Given** a mix of fully-clean candidates and candidates with one or more skipped non-essential gates, **When** results are ordered, **Then** every fully-clean candidate ranks above every candidate with a skipped gate.
3. **Given** a candidate that fails an **essential** gate (liquidity, data-integrity, or primary thesis), **When** the screen runs, **Then** the candidate is excluded and never appears regardless of the expanded-coverage setting.
4. **Given** expanded coverage is disabled, **When** the screen runs, **Then** behaviour matches today's screen exactly (no extra candidates).
5. **Given** a candidate with a skipped non-essential gate, **When** its advisor prompt / detail is viewed, **Then** the skipped gate and its reason are stated verbatim, so the owner can judge the trade-off.

---

### User Story 3 - Quarterly Shariah universe refresh (Priority: P3)

The owner wants the Halal Terminal–sourced compliant universe to refresh roughly every three months instead of every few days, to conserve the limited API-key quota, while still being told honestly when the compliance data is stale.

**Why this priority**: A cost-control / operations improvement with no new user-facing surface; valuable but the least impactful of the three and fully independent.

**Independent Test**: Simulate consecutive refresh runs at varying elapsed times against a recorded last-refresh timestamp and confirm the external Halal Terminal source is consulted only when ≥90 days have elapsed (or on explicit force), that within the window the cached compliant universe is reused without API calls, and that staleness is surfaced when the window is exceeded without a successful refresh.

**Acceptance Scenarios**:

1. **Given** the compliant universe was last refreshed 30 days ago, **When** a scheduled refresh runs, **Then** the Halal Terminal API is **not** called and the cached universe is reused.
2. **Given** the compliant universe was last refreshed 95 days ago, **When** a scheduled refresh runs and a valid API key is present, **Then** the Halal Terminal source is consulted and the cache + last-refresh timestamp are updated.
3. **Given** ≥90 days have elapsed and no valid API key is present, **When** a refresh runs, **Then** no API call is attempted, the cached universe is reused, and a "compliance data stale" condition is surfaced (loud warning, never silent).
4. **Given** the owner explicitly forces a refresh, **When** it runs, **Then** the 90-day gate is bypassed and the source is consulted immediately (subject to a valid key).
5. **Given** any refresh decision, **When** it executes, **Then** the same elapsed-time input yields the same call/skip decision (deterministic).

### Edge Cases

- **No detectable base.** A candidate with a valid uptrend but no identifiable base/pivot is classified entry-undetermined, not entry-ready (Scenario US1.7).
- **Multiple bases in the window.** Pivot is taken from the *most recent* qualifying base; the rule for which base wins is fixed and deterministic.
- **Gap-up open above the +5% window.** A candidate that opened/closed already >5% above pivot is "extended", consistent with the exclusion rule, even if the breakout day itself was valid.
- **Thin/holiday volume.** Volume confirmation uses the 50-day average; if fewer than 50 trading days are available, the volume component is undetermined rather than a pass.
- **All candidates fail entry rules.** With the "entry-ready only" filter ON, the screen may legitimately return zero candidates; the empty state explains why (e.g. "no candidates currently near a sound entry").
- **Essential vs non-essential reclassification.** If a gate's tier (essential / preferred / disqualifier) is changed, the change is explicit and surfaced; it never silently alters which essential failures or disqualifiers are excluded.
- **Climax-top after a strong breakout.** A candidate that is technically near pivot on confirming volume but has just advanced ≈+25–50% in 1–3 weeks off an extended uptrend is classified **not-entry-ready (climax-top exhaustion)** via the FR-022 disqualifier, even though individual components might otherwise pass.
- **Recent short-lived catalyst.** A candidate with a known short-lived catalyst (e.g. an index-inclusion effective date) close in time carries a non-directive "possible sell-the-news" warning; the warning is informational and does not by itself exclude or force not-entry-ready.
- **Refresh clock skew / missing timestamp.** A missing or unreadable last-refresh timestamp is treated as "due for refresh" (fail-safe toward freshness), not as "infinitely fresh".
- **First run after cadence change.** The first refresh after this feature ships may consult the source once to establish a baseline timestamp, then settle into the 90-day cadence.

## Requirements *(mandatory)*

### Functional Requirements — US1 (Entry-timing overlay)

- **FR-001**: The system MUST compute, for each surfaced candidate, an entry-timing classification with one of these states: **entry-ready**, **not-entry-ready**, or **entry-undetermined**.
- **FR-002**: The classification MUST be composed of six independently-reported components, each with a pass / fail / undetermined status, the measured value, and a short reason:
  - **Pivot proximity**: entry-ready requires `0% ≤ (price − pivot) / pivot ≤ +5%`, where pivot = the high of the most recent qualifying base (or the handle high for a cup-with-handle). Anything `> +5%` above pivot is **extended** and fails.
  - **Trend**: price above SMA-200.
  - **Volume confirmation**: breakout-day (or breakout-window) volume `≥ 1.4×` the 50-day average volume; `≥ 1.5×` is reported as the stronger/preferred tier. Below 1.4× fails ("weak-volume breakout").
  - **Base maturity**: flat base `≥ 5 weeks`; cup / cup-with-handle / double-bottom `≥ 7 weeks`. Shorter bases fail ("immature base"). The base **type** is assigned by an explicit geometric pattern classifier (see FR-002a), and the per-type threshold is applied accordingly.
  - **Base depth**: correction from base high to base low `≤ 30–35%` (default threshold 33%, configurable within the 30–35% band). Deeper bases fail ("base too deep").
  - **Not-extended from trend**: `(price − SMA-200) / SMA-200 ≤ 40%`. Above fails ("far above SMA-200").
- **FR-002a**: The base and pivot MUST be derived from an **explicit geometric pattern classifier** that recognizes and labels distinct base types — flat base, cup, cup-with-handle, and double-bottom — rather than a generic rolling-window high. The classifier assigns the base type (driving the per-type maturity threshold in FR-002), locates the pivot (base high, or the handle high for a cup-with-handle), and measures base length and depth. When no base of any supported type can be reliably classified, the base-dependent components (pivot proximity, base maturity, base depth) are **undetermined** and the candidate is entry-undetermined — never a false entry-ready. New classifier indicators get golden-fixture tests before any surface depends on them.
- **FR-003**: A candidate MUST be classified **entry-ready** only when all six components pass; **not-entry-ready** when at least one component fails on available data; **entry-undetermined** when a required input (e.g. detectable base/pivot, ≥50 days of volume, ≥200 days for SMA-200) is missing such that a component cannot be evaluated and none has failed.
- **FR-004**: The system MUST expose the pivot value, the base type detected, the base length, the base depth, the breakout volume ratio, the distance above pivot, and the distance above SMA-200 as per-candidate diagnostics so the classification is auditable.
- **FR-005**: The system MUST provide a user-toggleable "entry-ready only" filter. When ON, only entry-ready candidates are returned; when OFF, all candidates are returned, each annotated with its classification. The default state is OFF (annotate, don't hide).
- **FR-006**: The entry-timing overlay MUST NOT change the selection, ranking inputs, gates, thresholds, citations, or backtest baseline of any existing strategy; it is an additive post-screen annotation.
- **FR-007**: All entry-timing copy MUST be free of directive trading language and MUST attribute each rule to its source (base/pivot/breakout → Minervini (2013)); it MUST NOT be labelled or marketed as a CAN SLIM strategy.
- **FR-008**: The classification MUST be deterministic for a given snapshot.
- **FR-022**: In addition to the six pass/fail components, the overlay MUST evaluate explicit **disqualifiers** that force a **not-entry-ready** classification (and exclusion when the "entry-ready only" filter is ON) regardless of the six components, each reported with its measured trigger and reason:
  - **Climax-top exhaustion**: an approximately `+25%–50%` vertical advance within `1–3 weeks` following an extended prior uptrend → reason "climax-top exhaustion (not entry)".
  - **Huge-gap breakout**: a breakout gap leaving the price already `> +5%` above pivot → reason "gap-extended above pivot" (consistent with the pivot-proximity exclusion).
  - **Recent short-lived catalyst**: a known short-lived catalyst with a recent effective date (e.g. an index-inclusion effective date) → the candidate retains its classification but MUST carry an informational, non-directive warning describing the elevated post-catalyst pullback risk (the owner's intent is a "sell-the-news" caution; the surfaced copy MUST be phrased to pass the directive-language lint per SC-008, i.e. describe the risk, never instruct an action). This warning does not by itself force not-entry-ready.
  Disqualifier thresholds are configurable; default values are those stated above. Climax-top detection is deterministic for a given snapshot.
- **FR-023**: The entry-timing overlay attaches **only to the mid-term momentum strategy** (`midterm_52w_high_momentum`). The Minervini VCP, value-composite, and ATR-breakout strategies are unchanged and carry no entry-timing annotation.

### Functional Requirements — US2 (Expanded coverage)

- **FR-009**: The system MUST maintain an explicit, per-strategy classification of each gate into one of **three tiers**, discoverable per strategy:
  - **Essential** — failure excludes the candidate.
  - **Preferred / non-essential** — fail-open: a non-pass (fail *or* unevaluable) retains the candidate, marked `skipped` (not `passed`) with a reason, and demotes it in rank.
  - **Disqualifier** — positive detection hard-excludes the candidate (or, in the entry overlay, forces not-entry-ready per FR-022).
- **FR-009a**: The **default** tier assignment is: **Essential** = universe liquidity gate, feature-008 data-integrity check, and the strategy's primary thesis gate. **Preferred/non-essential** = market regime (overall-market trend; if choppy/down, deduct ranking points and warn, never exclude), sector strength (sector near its highs; treated as `skipped` when the universe is narrow), and relative strength (RS line near new highs, an additional momentum confirmation). **Disqualifiers** = climax-top exhaustion and huge-gap breakout >+5% above pivot (the short-lived-catalyst "sell-the-news" condition is a warning, not an exclusion). The assignment is configurable.
- **FR-010**: A candidate that fails or cannot evaluate a **preferred/non-essential** gate MUST be retained (not dropped) when expanded coverage is enabled, with that gate recorded as `skipped` and a human-readable reason.
- **FR-011**: A candidate that fails an **essential** gate, or that triggers a **disqualifier**, MUST be excluded regardless of the expanded-coverage setting.
- **FR-012**: Candidates with one or more skipped non-essential gates MUST be ranked strictly below all fully-clean candidates (consistent with the existing data-integrity demotion pattern), never interleaved.
- **FR-013**: Expanded coverage MUST be toggleable; when disabled, screen output MUST be identical to current behaviour.
- **FR-014**: The skipped gate(s) and reason(s) MUST be surfaced on the candidate and carried verbatim into the advisor prompt / candidate detail.
- **FR-015**: The expanded-coverage behaviour MUST NOT alter any gate's pass/fail threshold — only whether a non-pass on a non-essential gate excludes the candidate.

### Functional Requirements — US3 (Quarterly Shariah refresh)

- **FR-016**: The system MUST refresh the Halal Terminal–sourced compliant universe only when at least 90 days have elapsed since the last successful refresh, or when an explicit force-refresh is requested.
- **FR-017**: Within the 90-day window, the system MUST reuse the cached compliant universe and MUST NOT make Halal Terminal API calls.
- **FR-018**: The system MUST persist and read a last-successful-refresh timestamp for the compliant universe; a missing/unreadable timestamp MUST be treated as "due for refresh".
- **FR-019**: When the cadence elapses but no valid API key is available, the system MUST skip the API call, reuse the cache, and surface a "compliance data stale" warning (loud, never silent), consistent with existing staleness reporting.
- **FR-020**: The reported refresh-interval metadata MUST reflect the ~90-day cadence (replacing the previous shorter interval) so downstream staleness messaging is accurate.
- **FR-021**: The refresh decision MUST be deterministic given the same elapsed-time and key-availability inputs.

### Key Entities

- **Entry-timing classification**: Per-candidate result with overall state (entry-ready / not-entry-ready / entry-undetermined), the six component results (status + measured value + reason), and the supporting diagnostics (pivot, base type, base length, base depth, breakout volume ratio, distance above pivot, distance above SMA-200).
- **Base / pivot**: A detected consolidation in a candidate's price history characterized by type (flat / cup / cup-with-handle / double-bottom), start/end, length (weeks), high (pivot), and low (for depth). The most recent qualifying base supplies the active pivot.
- **Gate classification**: Per-strategy mapping of each gate to one of three tiers — **essential** (non-pass excludes), **preferred/non-essential** (non-pass demotes-and-labels `skipped`), or **disqualifier** (positive detection hard-excludes / forces not-entry-ready). Includes the entry-overlay disqualifiers (climax-top exhaustion, huge-gap breakout) and the informational short-lived-catalyst "sell-the-news" warning.
- **Compliant-universe refresh state**: The cached Halal Terminal–sourced compliant universe plus its last-successful-refresh timestamp, refresh-interval (≈90 days), and staleness flag.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a frozen snapshot, every surfaced candidate carries an entry-timing classification whose six component values match the specified thresholds exactly, verifiable by reproducing the arithmetic from the exposed diagnostics.
- **SC-002**: Toggling the "entry-ready only" filter changes only *which* candidates are shown (a strict subset), never their underlying selection/ranking, and yields the same subset on repeat runs of the same snapshot.
- **SC-003**: With expanded coverage enabled on a representative snapshot, the candidate count increases relative to today's screen, and 100% of the added candidates are ones that fail/skip only non-essential gates (zero added candidates fail an essential gate).
- **SC-004**: Across any ordered result set, no candidate with a skipped non-essential gate appears above any fully-clean candidate.
- **SC-005**: Over a simulated year of scheduled refreshes, Halal Terminal API calls for the compliant universe occur at most ~4 times (once per ~90-day window) plus any explicit forced refreshes — a verifiable reduction from the prior cadence.
- **SC-006**: Within a refresh window, zero Halal Terminal API calls are made for the compliant universe, confirmed by call accounting.
- **SC-007**: When compliance data exceeds the 90-day window without a successful refresh, a stale-data warning is surfaced on the relevant response 100% of the time.
- **SC-008**: No new or changed user-facing copy contains directive trading language (verified by the existing copy lint).
- **SC-009**: With all three features disabled/at defaults, screen output is byte-identical to the pre-feature baseline for the same snapshot (additive-by-default guarantee).

## Assumptions

- **Entry overlay is a diagnostic, not a strategy.** It is computed as a post-screen annotation over candidates produced by the **mid-term momentum strategy only** (`midterm_52w_high_momentum`; confirmed 2026-06-27, FR-023). It is not a new registered, gated, backtested strategy and does not ship under a CAN SLIM citation.
- **Base/pivot detection uses an explicit geometric pattern classifier** (confirmed 2026-06-27, FR-002a) that labels flat / cup / cup-with-handle / double-bottom and locates the pivot (handle high for cup-with-handle). Detection quality is bounded by the free daily-bar tier; unclassifiable patterns yield entry-undetermined rather than false positives.
- **Default gate tiers** (three-tier model, confirmed 2026-06-27, FR-009a). **Essential** (exclude on fail) = universe liquidity gate (ADV ≥ $1M 20-day, price ≥ $5), the feature-008 data-integrity check, and the strategy's primary thesis gate (52-week-high proximity for momentum). **Preferred/non-essential** (fail-open → `skipped` + demote) = market regime, sector strength, relative strength. **Disqualifiers** (hard exclude / force not-entry-ready) = climax-top exhaustion and huge-gap breakout >+5% above pivot; a recent short-lived catalyst attaches a "sell-the-news" warning only. The split is configurable.
- **Base depth default threshold = 33%** within the stated 30–35% band; configurable.
- **"3 months" = 90 days.** Calendar-day based, not trading-day based.
- **Base/pivot detection runs on the existing free daily-bar history (Stooq + current EOD)**, split/dividend-adjusted consistent with feature 008; detection quality is bounded by that data tier, and undetectable bases yield entry-undetermined rather than false positives.
- **Volume and SMA-200 windows** use 50 and 200 trading days respectively; insufficient history yields undetermined components, never a pass.
- **US1/US2/US3 are independent** and can ship in any order; defaults keep each OFF/additive so the baseline screen is unchanged until the owner opts in.
- **Hosted single-owner context** (feature 010) is unchanged: directive-OFF force, `data_as_of` + `disclaimer`, and the owner-secret gate all continue to apply.

## Clarifications

### Session 2026-06-27

- Q: US1 base/pivot detection approach (rolling-window reuse vs swing-point + light shape vs full classifier)? → A: **Full geometric classifier** — explicitly recognize and label flat / cup / cup-with-handle / double-bottom patterns (not a generic consolidation window), so the differentiated maturity rule (flat ≥5wk; cup/cup-with-handle/double-bottom ≥7wk) and handle-high pivot are applied per detected type; undetectable patterns yield entry-undetermined.
- Q: Which strategies/surfaces carry the entry-timing overlay? → A: **Momentum only** — the overlay attaches solely to the mid-term momentum strategy (`midterm_52w_high_momentum`). Minervini VCP, value composite, and ATR breakout are unchanged.
- Q: Entry overlay default behaviour — hide non-entry-ready or annotate all? → A: **Annotate all; "entry-ready only" filter OFF by default** (spec default, FR-005 unchanged).
- Q: US2 essential/non-essential gate split? → A: **Custom three-tier model** (owner-supplied). Tier A = essential (exclude on fail): liquidity, data-integrity, and primary thesis. Tier B = preferred/non-essential (fail-open → retained, marked `skipped` not `passed`, demoted in rank): **market regime** (overall-market trend; if choppy/down, deduct ranking points + warn, don't exclude), **sector strength** (sector near its highs; ignore when the universe is narrow), **relative strength** (RS line near new highs — additional momentum confirmation). Tier C = explicit disqualifiers (hard exclude / not-entry-ready on positive detection): **climax-top exhaustion** (≈ +25–50% vertical rise in 1–3 weeks after a long uptrend → exhaustion, not entry), **huge-gap breakout** leaving price extended >+5% above pivot, and **recent short-lived catalyst** (e.g. an index-inclusion effective date) → attach a "sell-the-news" warning.

These two decisions affect scope; sensible defaults are already baked into the spec above so it is complete, but the owner may redirect:

### Question 1: Entry overlay — filter vs annotation default

**Context**: FR-005 / US1.8 — "determine stocks at a good entry point" can mean *hide* non-entry names or *label* them.

**What we need to know**: Should the entry overlay default to filtering the list down to entry-ready names, or annotate all candidates with the filter OFF by default?

| Option | Answer | Implications |
|--------|--------|--------------|
| A | Annotate all; "entry-ready only" filter OFF by default *(spec default)* | Coverage preserved; owner opts into narrowing. Composes cleanly with US2. |
| B | Filter to entry-ready by default | Tighter, timing-first list out of the box; may return zero candidates in poor tape; tension with US2's "more candidates" goal. |
| C | Annotate, and also sort entry-ready candidates to the top by default | No data hidden, but timing surfaces first without an explicit toggle. |
| Custom | Provide your own | — |

**Your choice**: **A** — annotate all, "entry-ready only" filter OFF by default (confirmed 2026-06-27).

### Question 2: Which gates are "non-essential" (safely skippable)

**Context**: FR-009–FR-011 — the essential/non-essential split decides which candidates US2 adds.

**What we need to know**: Confirm the default non-essential set.

| Option | Answer | Implications |
|--------|--------|--------------|
| A | Non-essential = sector-relative gate, QMJ quality screen, value momentum floor, profitability gate; essential = liquidity, data-integrity, primary thesis *(spec default)* | Widest sensible coverage gain while protecting the core thesis and data trust. |
| B | Only the sector-relative gate is non-essential | Minimal change; smallest coverage increase. |
| C | All gates except liquidity + data-integrity are non-essential | Maximum coverage; the strategy's own thesis gate becomes demote-not-exclude (looser, higher noise). |
| Custom | Provide your own per-gate split | — |

**Your choice**: **Custom three-tier model** (confirmed 2026-06-27 — see Session 2026-06-27 above and FR-009/FR-009a/FR-022). Tier A essential = liquidity, data-integrity, primary thesis. Tier B preferred/non-essential (fail-open → skipped + demote) = market regime, sector strength, relative strength. Tier C explicit disqualifiers (hard exclude / not-entry-ready) = climax-top exhaustion, huge-gap breakout >+5% above pivot, recent short-lived catalyst ("sell-the-news" warning).
