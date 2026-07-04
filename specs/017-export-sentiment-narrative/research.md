# Phase 0 Research: Sentiment & Narrative in Exported Advisor Prompts

All NEEDS CLARIFICATION items resolved. Decisions below are constrained by the constitution
(determinism, no-advice, provenance) and by the existing feature-014 sentiment engine and the
feature-004/006/013 advisor-prompt builders.

## Decision 1 — How the export finds a captured report by ticker (the one real unknown)

**Decision**: Add a **ticker-indexed lookup** to `CapturedReportStore`
(`latest_for_ticker(ticker: str) -> SentimentReport | None`) and resolve reports **in the API
layer** at export time. Add a `ticker` column to the `sentiment_reports` table, populated on
`put()` from `report.ticker`, and return the row with the most recent `captured_at` for that
ticker.

**Rationale**: The store is keyed by `fingerprint`, and the fingerprint is derived from the
**collected sources** (`_fingerprint(selection, sources)` in `api/sentiment.py`). To recompute a
fingerprint the export would have to call `collect_sources(ticker)` — a source-collection /
network step. That would (a) break determinism (sources shift over wall-clock), and (b) risk
budget/cost and latency at export time, violating FR-007 and FR-009. A ticker index lets the
export reuse the exact captured artifact **without** any collection step.

**Alternatives rejected**:
- *Recompute the fingerprint at export by re-collecting sources* — rejected: reintroduces
  network + non-determinism + potential cost; directly contradicts FR-007/FR-009.
- *Scan all rows and parse `artifact_json` to match ticker* — rejected as the primary path
  (full-table JSON parse per export); a `ticker` column with an index is O(log n) and trivially
  correct. (A one-time backfill on migration parses existing rows once.)
- *Have the frontend pass the fingerprint it saw on screen* — rejected: couples the export to
  client state, is fragile across snapshot changes, and still fails when the owner exports names
  they never opened the on-screen report for.

**Migration**: `_init()` adds `ticker TEXT` (nullable) if missing and an index on
`(ticker, captured_at)`; a lightweight backfill parses `artifact_json` for pre-existing rows and
populates `ticker`. Schema change is backward-compatible (additive column).

## Decision 2 — Preserving byte-identical determinism (FR-007) and absent-fallback (FR-008)

**Decision**: The renderer `_sentiment_section(report)` consumes **only** deterministic,
content-addressed `SentimentReport` fields — `label`, `narrative`, `narrative_risk`
(score/label/signals), `sources` (title/publisher/`published_at`/`is_stale`), `budget_state`,
`narrative_source`, and `resolution`. It **never** reads `captured_at` or any wall-clock. When
`sentiment_by_ticker` has no entry for a name, the block builder appends **nothing** — the block
is byte-identical to today's output.

**Rationale**: `captured_at` is the only wall-clock-dependent value in the store; excluding it
from the rendered body is what makes re-export byte-identical for a fixed snapshot + fixed
captured report. Absent ⇒ no-op keeps the additive guarantee (SC-004). Staleness is conveyed by
the report's own `SourceItem.is_stale` flag and each source's `published_at` date (Edge case:
stale captured sentiment), not by comparing to export-time now.

**Alternatives rejected**:
- *Show "captured N days ago"* — rejected: injects wall-clock into the body, breaking FR-007.

## Decision 3 — Where the report is injected (keep builders pure)

**Decision**: Keep the prompt builders **pure functions of their inputs**. The API layer
(`strategies.py`, `portfolio.py`) resolves `sentiment_by_ticker` from the store and passes it as
an **optional keyword arg** into `build_screen_advisor_prompt`,
`build_portfolio_advisor_prompt`, and the new `build_watchlist_advisor_prompt`. Those forward it
to `_candidate_summary_block` / `_holding_block`, which call `_sentiment_section` when a report
is present for that ticker.

**Rationale**: The builders' determinism guarantee ("no wall-clock in the body", byte-identical
on re-run) rests on their being pure. Doing store I/O inside a builder would break that contract
and its tests. Passing a resolved mapping keeps the builders pure and the mapping is itself
content-addressed (each value is a captured report), so determinism is preserved. Single-candidate
(`build_advisor_prompt`) and single-holding (`build_holding_advisor_prompt`) inherit the same
section for free via the shared block builders (Assumption in spec), but the three named surfaces
are the committed scope.

**Alternatives rejected**:
- *Attach the report onto each candidate/holding model* — rejected: pollutes the computed-result
  models with presentation-only external data and risks the report leaking into non-export
  responses; a side mapping keeps the separation FR-004 demands.

## Decision 4 — Fail-soft on a missing/unreadable report (FR-010)

**Decision**: Resolution is best-effort per ticker in the API layer: a `try/except` around
`store.latest_for_ticker(ticker)` yields `None` on any error, so that one name simply omits its
sentiment section; all other names and the rest of the prompt are unaffected. The renderer also
guards the explicit `no_signal` / `unavailable` captured states (FR-003) by printing the
report's stated status instead of fabricating a narrative.

**Rationale**: Matches the spec's fail-soft edge cases and mirrors `_safe_report_for_selection`'s
existing defensive pattern in feature 014.

## Decision 5 — Rendering: layout, separation, and no-directive (FR-003/FR-004/FR-006)

**Decision**: `_sentiment_section(report)` emits a clearly-delimited sub-block under a heading
like `### External context — sentiment & narrative (informational; does NOT change gates/levels)`
containing: sentiment **label**, a short **narrative** summary, the **narrative-risk** reading
(score + label + signals) when present, and each contributing **source** with its
publisher/date and any stale marker. The task instruction already states news "informs the risk
narrative only"; extend that sentence to explicitly name sentiment as external context that MUST
NOT overwrite a computed gate, rank, level, or size. All rendered strings pass
`validate_no_directive_language` (the same guard feature 014 already applies to label/risk copy),
and the existing Playwright prompt-preview copy lint covers the rendered output.

**Rationale**: Satisfies FR-003 (minimum fields + explicit no-signal), FR-004 (visual/semantic
separation + framing), FR-006 (zero directive language) using conventions already in the codebase.

**Alternatives rejected**:
- *Inline the sentiment among the gate/level lines* — rejected: violates FR-004's separation
  requirement and risks the advisor treating a story as a computed fact.

## Decision 6 — Watchlist export shape and format (US3 / FR-011–FR-014)

**Decision**: New `POST /portfolio/watchlist/advisor-prompt` accepting
`{ strategy_slug, tickers: [str], as_of?: str }`. The backend computes each watched ticker via
the existing `compute_candidate_result(ticker, strategy, as_of)` and assembles one prompt with a
new `build_watchlist_advisor_prompt` that reuses `_strategy_context`, `_candidate_summary_block`
(or `_candidate_block`), the shared honesty block, and `_sentiment_section`. An **empty**
`tickers` list returns a clear "no watched names" prompt state (FR-013), never a malformed
prompt. The watchlist stays client-side (Zustand/localStorage blob); the frontend posts the
watched entries' tickers + the active strategy slug.

**Rationale**: "Same format" = the screener-results layout (strategy declaration → per-name
computed blocks → one shared honesty footer), re-expressed through the current snapshot's
computed numbers plus the embedded sentiment section — exactly what reusing the screen block
builders yields. Placing the endpoint on the portfolio router keeps it next to the owner-scoped
persisted state; momentum-primary in-app means a single `strategy_slug` per export is sufficient
(feature 016 removed value/short-term from in-app entry points).

**Alternatives rejected**:
- *A brand-new watchlist store on the backend* — rejected: the spec keeps the existing
  owner-scoped watchlist; this feature adds an export over it, not a new store.
- *Per-entry strategy in one export* — deferred: in-app is momentum-only; a single slug matches
  the screen-export format and avoids interleaving multiple strategy declarations.

## Decision 7 — Hosted-mode and directive gating (FR-016)

**Decision**: No new gating logic. All three exports already sit behind the owner-secret
dependency and read `personal_use_directive()` (forced OFF in hosted mode via feature 010).
`data_as_of` + `disclaimer` remain on every response. The export triggers no heavy in-host
generation because it only reads the captured store.

**Rationale**: Reuses the established hosted-mode envelope; the feature adds no route that could
bypass it.

## Summary of resolved unknowns

| Unknown | Resolution |
|---------|------------|
| Find captured report without fresh collection | Decision 1: ticker-indexed `latest_for_ticker` on the store |
| Keep re-export byte-identical | Decision 2: render only content-addressed fields, never `captured_at` |
| Keep builders pure/deterministic | Decision 3: API resolves a `sentiment_by_ticker` mapping, passes it in |
| Missing/errored report for one name | Decision 4: per-ticker best-effort resolve → omit only that section |
| Layout / separation / no-directive | Decision 5: dedicated `_sentiment_section` + existing lints |
| Watchlist export "same format" | Decision 6: new endpoint reusing screen block builders |
| Hosted + directive gating | Decision 7: reuse existing owner-secret + forced-OFF path |
