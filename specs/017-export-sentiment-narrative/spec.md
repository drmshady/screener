# Feature Specification: Sentiment & Narrative in Exported Advisor Prompts (+ Watchlist Export)

**Feature Branch**: `017-export-sentiment-narrative`
**Created**: 2026-07-04
**Status**: Draft
**Input**: User description: "add feature to export sentimental and narrative within exported prompt of screener results and also for portfolio report and add same for watchlist with similar format"

## Overview

Feature 014 gave the owner an on-request **sentiment & narrative report** (a coarse sentiment
label, a short storyline narrative, a narrative-risk reading, and the dated sources behind it)
for stocks they select. Features 004/006/013 gave the owner a **copy-ready advisor prompt** — a
self-contained block of the screener's own numbers (strategy declaration, gate-by-gate results,
price levels, regime, honesty caveats) that the owner pastes into an external AI advisor.

Today those two things are **separate**: the sentiment story lives only in the on-screen report,
and the exported advisor prompt contains none of it. This feature **weaves the already-captured
sentiment & narrative material into the exported advisor prompt** so a single paste carries both
the screener's hard numbers *and* the market's story for the same names. It applies to:

1. the **screener-results** export (the whole-screen advisor prompt),
2. the **portfolio-report** export (the whole-portfolio hold/trim/exit advisor prompt), and
3. a **new watchlist export** built in the **same format**, since the watchlist has no
   copy-ready prompt today.

The sentiment material embedded in the prompt is the **same captured report** the owner already
sees on screen — it is **informational context inside the prompt**, clearly separated from the
screener's computed numbers. It never changes a gate result, rank, price level, sizing, regime,
or backtest baseline; it carries **zero directive language**; and it must not break the export's
existing guarantee that the same snapshot reproduces the **same prompt text**. Because sentiment
generation is on-request and lives under a hard ~$5/month budget cap, the export **reuses
sentiment that has already been captured** rather than triggering fresh paid generation for every
name mid-export — so a bulk export can never silently run up cost, and stays byte-identical when
no captured sentiment is present.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Sentiment & narrative inside the screener-results export (Priority: P1)

The owner runs a screen, reviews the candidates, and (optionally) runs the sentiment report on
some of them. When the owner exports the whole-screen advisor prompt, each candidate that has a
captured sentiment report carries — inside its block in the prompt — its sentiment label, a short
narrative summary, its narrative-risk reading, and the dated sources, all clearly marked as
external context that must not overwrite the screener's computed gates/levels.

**Why this priority**: This is the primary request and the highest-value surface — the screen
export is the owner's main "hand this to an advisor" action, and pairing the hard numbers with
the story in one paste is the whole point.

**Independent Test**: With a screen and at least one candidate that has a captured sentiment
report, export the advisor prompt and confirm the sentiment label, narrative, narrative-risk, and
dated sources appear within that candidate's block, visually separated from the gate/level lines;
candidates without a captured report are unaffected; re-exporting on the same snapshot reproduces
identical text; no directive words appear.

**Acceptance Scenarios**:

1. **Given** a screen where the owner has captured sentiment for one or more candidates, **When**
   the owner exports the screen advisor prompt, **Then** each such candidate's block includes a
   labeled sentiment section (label, narrative, narrative-risk, dated sources) kept separate from
   its computed gate/level lines.
2. **Given** a candidate with no captured sentiment, **When** the prompt is exported, **Then**
   that candidate's block is byte-identical to today's output (no empty or placeholder sentiment
   section).
3. **Given** the same data snapshot and same captured sentiment, **When** the prompt is exported
   twice, **Then** the two prompts are byte-identical.
4. **Given** any export, **When** the sentiment section renders, **Then** it contains zero
   directive trading terms and the prompt's task instructions state the sentiment is external
   context that must not overwrite a computed gate, rank, level, or size.
5. **Given** a candidate whose captured report is a "no signal" state, **When** the prompt is
   exported, **Then** the block states "no sentiment signal" rather than fabricating a story.

---

### User Story 2 — Sentiment & narrative inside the portfolio-report export (Priority: P1)

From the portfolio view, the owner exports the whole-portfolio hold/trim/exit advisor prompt.
Each held position that has a captured sentiment report carries the same embedded sentiment
section within its holding block, so the owner can hand an advisor both the position's
cost-basis/levels/risk facts and the current story behind the name in one paste.

**Why this priority**: The portfolio export is the second surface the owner named and is equally
central — spotting when the story behind a *held* position has shifted is exactly when the
sentiment context matters most.

**Independent Test**: With holdings and at least one captured sentiment report, export the
portfolio advisor prompt and confirm the sentiment section appears within the matching holding's
block, separated from its levels/risk lines, under the same determinism and no-directive rules as
US1; holdings without a captured report are unaffected.

**Acceptance Scenarios**:

1. **Given** a portfolio where the owner has captured sentiment for one or more holdings, **When**
   the owner exports the portfolio advisor prompt, **Then** each such holding's block includes the
   labeled sentiment section kept separate from its cost-basis/level/risk lines.
2. **Given** a holding with no captured sentiment, **When** the prompt is exported, **Then** that
   holding's block is byte-identical to today's output.
3. **Given** the same snapshot + portfolio + captured sentiment, **When** the prompt is exported
   twice, **Then** the two prompts are byte-identical.

---

### User Story 3 — New watchlist export in the same format (Priority: P2)

The watchlist has no copy-ready advisor prompt today. This story adds one built in the **same
format** as the screener-results export: for each watched name it assembles the strategy
declaration, the name's current screener numbers (gate results, levels, regime context) and — in
the same embedded style as US1/US2 — its captured sentiment & narrative section, plus the shared
honesty caveats. The owner exports one prompt covering the watchlist and pastes it into an
external advisor.

**Why this priority**: It is the third surface the owner named ("add same for watchlist"), but it
is a net-new export path rather than an enrichment of an existing one, so it is sequenced after
the two existing exports are enriched. It still delivers standalone value.

**Independent Test**: With one or more watched names, export the watchlist advisor prompt and
confirm it lists each watched name with its strategy context, current computed numbers, and (when
captured) its embedded sentiment section, in the same layout as the screener export; the honesty
caveats appear once; re-exporting on the same snapshot reproduces identical text; no directive
language appears.

**Acceptance Scenarios**:

1. **Given** one or more watched names, **When** the owner exports the watchlist advisor prompt,
   **Then** a single prompt lists each watched name with its strategy declaration, current
   computed numbers, and (when present) embedded captured sentiment, ending with the shared
   honesty caveats.
2. **Given** a watched name with captured sentiment, **When** the prompt is exported, **Then** its
   sentiment section appears in the same embedded format as the screener export.
3. **Given** an empty watchlist, **When** the owner attempts the export, **Then** a clear "no
   watched names" state is produced rather than an empty or erroneous prompt.
4. **Given** the same snapshot + watchlist + captured sentiment, **When** the prompt is exported
   twice, **Then** the two prompts are byte-identical, and no directive language appears.

---

### Edge Cases

- **No captured sentiment for any selected name**: every export degrades to today's sentiment-free
  prompt (byte-identical), never an empty "Sentiment:" header or a fabricated story.
- **Captured report is "no signal" or "unavailable"**: the block states the explicit no-signal /
  unavailable status from the captured report rather than inventing a narrative.
- **Stale captured sentiment**: the embedded section carries the sources' dates (and any stale
  flag from the captured report) so the reader can judge recency; the export never silently
  presents old sentiment as current.
- **Budget exhausted at capture time**: the captured report's budget state (e.g. template-only
  narrative) is reflected as-is; the export itself triggers **no** new paid generation, so a bulk
  export cannot exceed the cap.
- **Watched / held / candidate ticker not resolvable on the current snapshot**: the name still
  appears with its available facts and an explicit "not priceable / no coverage" note, matching
  today's behavior; its sentiment section is included only if a captured report exists.
- **Directive mode (personal-use flag) on**: the embedded sentiment stays non-directive regardless;
  directive framing applies only to the task instruction, exactly as today, and is forced OFF in
  hosted mode.
- **Hosted mode**: exports obey hosted-mode rules — owner-only access, `data_as_of` + disclaimer on
  every response, forced directive-OFF, and no heavy in-host sentiment generation during export.

## Requirements *(mandatory)*

### Functional Requirements — Embedding sentiment into existing exports (US1/US2)

- **FR-001**: The screener-results advisor-prompt export MUST embed, within each candidate's block,
  the candidate's **captured** sentiment & narrative material when such a report exists for that
  ticker on the current snapshot.
- **FR-002**: The portfolio-report advisor-prompt export MUST embed, within each holding's block,
  the holding's **captured** sentiment & narrative material when such a report exists.
- **FR-003**: The embedded sentiment section MUST include, at minimum: the coarse sentiment label,
  the short narrative summary, the narrative-risk reading (when present), and the contributing
  sources each with a date; it MUST reflect an explicit "no signal" / "unavailable" status when the
  captured report is in that state, and MUST NOT fabricate a narrative.
- **FR-004**: The embedded sentiment section MUST be **visually and semantically separated** from
  the screener's computed numbers, and the prompt's task instruction MUST state that this material
  is **external context** that MUST NOT overwrite any computed gate result, rank, price level, or
  size (consistent with the existing "news informs the risk narrative only" framing).
- **FR-005**: The exports MUST remain **informational-only**: embedding sentiment MUST NOT change
  any candidate's gate result, ranking, price levels, position sizing, regime, or backtest baseline.
- **FR-006**: The embedded sentiment MUST carry **zero directive trading language** (no "buy",
  "sell", "recommended", "strong buy", etc.), consistent with the existing prompt-preview copy lint.

### Functional Requirements — Determinism, cost, and fail-soft

- **FR-007**: Each enriched export MUST remain **deterministic**: for a fixed data snapshot, a fixed
  portfolio/watchlist, and fixed captured sentiment, re-exporting MUST produce **byte-identical**
  prompt text (no wall-clock content in the body).
- **FR-008**: When no captured sentiment exists for a name, that name's block MUST be
  **byte-identical** to today's sentiment-free output (additive/optional embedding; absent ⇒ no
  change).
- **FR-009**: The export MUST reuse **already-captured** sentiment reports and MUST NOT trigger fresh
  paid sentiment/narrative generation as a side effect of exporting; a bulk export MUST NOT be able
  to exceed the ~$5/month sentiment budget cap.
- **FR-010**: The export MUST **fail soft** on sentiment: a missing, unreadable, or errored captured
  report for one name MUST omit only that name's sentiment section and MUST NOT block the export of
  the other names or the rest of the prompt.

### Functional Requirements — Watchlist export (US3)

- **FR-011**: The owner MUST be able to export a single **watchlist advisor prompt** covering all
  watched names, built in the **same format** as the screener-results export (strategy declaration,
  per-name computed numbers, shared honesty caveats appearing once).
- **FR-012**: Each watched name's block in the watchlist export MUST embed its **captured** sentiment
  & narrative material under the same rules as FR-003/FR-004/FR-006 when such a report exists.
- **FR-013**: Exporting an **empty** watchlist MUST produce a clear "no watched names" state, never
  an empty or malformed prompt.
- **FR-014**: The watchlist export MUST be **deterministic** (FR-007) and MUST carry `data_as_of` +
  `disclaimer` and honor hosted-mode owner-only access and forced directive-OFF (FR-016).

### Functional Requirements — Cross-cutting

- **FR-015**: Every response exposing an enriched or new export MUST continue to carry `data_as_of`
  and `disclaimer`.
- **FR-016**: All three exports MUST respect hosted-mode rules: owner-only access, forced
  directive-OFF, and no heavy in-host sentiment generation during export.
- **FR-017**: No strategy rule, default, citation, indicator, gate threshold, or backtest baseline
  MAY change as a result of this feature.

### Key Entities

- **Advisor Prompt Export** (existing, extended): the copy-ready prompt assembled for a screen or a
  portfolio; extended to carry an embedded sentiment section per name and to gain a new watchlist
  variant in the same format.
- **Embedded Sentiment Section** (new, within a prompt block): the captured sentiment label,
  narrative, narrative-risk reading, and dated sources for one ticker, rendered as external context.
- **Captured Sentiment Report** (existing, feature 014): the reproducible, fingerprint-keyed report
  the export reuses; never regenerated by the export.
- **Watchlist Entry** (existing): ticker + originating strategy + captured level snapshot; the basis
  for each block in the new watchlist export.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a screen where the owner has captured sentiment on N candidates, 100% of those N
  candidate blocks in the exported prompt include the embedded sentiment section (label, narrative,
  narrative-risk when present, and dated sources).
- **SC-002**: For a portfolio where the owner has captured sentiment on M holdings, 100% of those M
  holding blocks in the exported prompt include the embedded sentiment section.
- **SC-003**: Re-exporting any of the three prompts on an unchanged snapshot + unchanged captured
  sentiment reproduces byte-identical text 100% of the time.
- **SC-004**: For names with no captured sentiment, 100% of their blocks are byte-identical to the
  pre-feature output (verified against the frozen baseline).
- **SC-005**: 0% of exported prompts contain directive trading language (enforced by the existing
  copy lint), and 100% of embedded sentiment claims are traceable to a listed, dated source.
- **SC-006**: Exporting any prompt triggers 0 new paid sentiment/model calls; recurring sentiment
  cost stays within the ~$5/month cap in 100% of billing periods regardless of export volume.
- **SC-007**: The owner can export a single watchlist prompt covering all watched names in the same
  format as the screener export; an empty watchlist yields a clear "no watched names" state in 100%
  of such cases.
- **SC-008**: No strategy rule, default, citation, indicator, or backtest baseline changes as a
  result of this feature (verified against the frozen baselines).

## Assumptions

- The exports embed the **already-captured** sentiment report from feature 014 (the same content the
  owner sees on screen). The export path performs **no** fresh source collection, scoring, or
  narrative generation — this is what preserves both determinism (FR-007) and the budget cap (FR-009).
  When a name has no captured report, its block is unchanged (FR-008).
- "Same format" for the watchlist export means the existing screener-results prompt layout (strategy
  declaration → per-name computed blocks → one shared honesty footer), with each watched name
  re-expressed through the current snapshot's computed numbers plus its embedded sentiment section.
- The embedded sentiment section reuses feature 014's captured `SentimentReport` fields (label,
  narrative, narrative-risk, source classes, dated sources) and its no-directive/no-signal
  guarantees; this feature adds only the rendering of that material into the prompt builders.
- Embedding is additive and does not alter the prompt builders' existing purity: no wall-clock time
  enters the prompt body, so determinism is preserved end-to-end.
- The watchlist remains the existing owner-scoped watchlist (ticker + strategy + captured levels);
  this feature adds an export over it, not a new watchlist store.
- Hosted mode remains single-owner, owner-secret gated, with `data_as_of` + `disclaimer` and forced
  directive-OFF; no heavy in-host generation runs during export.
- The single-candidate and held-position (single-holding) exports MAY inherit the same embedded
  sentiment section for free since they share the underlying block builders, but the three named
  surfaces (screen, portfolio, watchlist) are the committed scope.

## Dependencies

- Feature 014 captured sentiment report engine and its `SentimentReport` model (label, narrative,
  narrative-risk, dated sources, budget/no-signal states) and its budget cap.
- The existing advisor-prompt builders (screener-results and portfolio-report) and their determinism
  + directive-gating + honesty-block conventions.
- The existing owner-scoped watchlist (ticker + strategy + captured level snapshot).
- Hosted-mode config, owner-secret access gate, and the `data_as_of` / `disclaimer` envelope.
