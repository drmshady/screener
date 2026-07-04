# Phase 1 Data Model: Sentiment & Narrative in Exported Advisor Prompts

This feature is **additive** and introduces no new domain entity. It reuses feature 014's
`SentimentReport` and extends the captured-report store's index and the prompt builders' inputs.

## Reused entity — `SentimentReport` (feature 014, `backend/src/models/sentiment.py`)

The export renders **only** these content-addressed fields (no `captured_at`, no wall-clock):

| Field | Type | Use in the embedded section |
|-------|------|-----------------------------|
| `ticker` | str | match key; block heading |
| `label` | `SentimentLabel` | coarse sentiment label line (FR-003) |
| `label_basis` | str | short basis text |
| `narrative` | str | short narrative summary (FR-003); empty/`ABSENT` → no fabricated story |
| `narrative_source` | `NarrativeSource` | provenance of the narrative (template/model/absent) |
| `narrative_risk` | `NarrativeRisk \| None` | narrative-risk reading (score/label/signals) when present |
| `budget_state` | `BudgetState` | reflect template-only/exhausted/unavailable as-is (edge case) |
| `source_classes_present` / `_omitted` | list[str] | which source classes contributed / were omitted |
| `sources` | list[`SourceItem`] | dated sources: `title`, `publisher`, `published_at`, `is_stale` |
| `resolution` | str \| None | explicit `no_signal` / `unavailable` status (FR-003) |
| `fingerprint` | str | identity of the captured artifact (not rendered) |

**No-signal / unavailable states**: `label == NO_SIGNAL` (with `resolution`) → the section prints
the explicit no-signal / unavailable status rather than a narrative.

## Extended store — `CapturedReportStore` (`backend/src/sentiment/store.py`)

Table `sentiment_reports` gains a nullable `ticker` column and a supporting index.

| Column | Type | Notes |
|--------|------|-------|
| `fingerprint` | TEXT PRIMARY KEY | unchanged |
| `artifact_json` | TEXT NOT NULL | unchanged (full `SentimentReport`) |
| `captured_at` | TEXT NOT NULL | unchanged (wall-clock; **not** rendered) |
| `ticker` | TEXT | **NEW** — populated from `report.ticker` on `put()` |

Index: `CREATE INDEX IF NOT EXISTS idx_reports_ticker ON sentiment_reports(ticker, captured_at)`.

New method:

```
latest_for_ticker(ticker: str) -> SentimentReport | None
    # most recent captured_at for that ticker; None if none captured
```

Migration in `_init()`: add the column if absent, create the index, and backfill `ticker` for
pre-existing rows by parsing `artifact_json` once. Backward-compatible (additive).

## New builder input — `sentiment_by_ticker` mapping

A resolved, in-memory `dict[str, SentimentReport]` (ticker → captured report) passed as an
**optional** keyword arg into the prompt builders. Absent/empty ⇒ builders emit today's output
byte-for-byte (FR-008). It carries no wall-clock and is content-addressed, so it does not affect
determinism (FR-007).

Threaded through:
- `build_screen_advisor_prompt(..., sentiment_by_ticker=None)` → `_candidate_summary_block(...)`
- `build_portfolio_advisor_prompt(..., sentiment_by_ticker=None)` → `_holding_block(...)`
- `build_watchlist_advisor_prompt(..., sentiment_by_ticker=None)` (new)
- (inherited) `build_advisor_prompt` / `build_holding_advisor_prompt` via shared block builders

## New request/response — watchlist export

**Request** `WatchlistAdvisorPromptRequest`:

| Field | Type | Notes |
|-------|------|-------|
| `strategy_slug` | str | active strategy (momentum primary in-app) |
| `tickers` | list[str] | watched names; **empty ⇒ "no watched names" state** (FR-013) |
| `as_of` | str \| None | optional snapshot date; omitted ⇒ current |

**Response** `WatchlistAdvisorPromptResponse`:

| Field | Type | Notes |
|-------|------|-------|
| `strategy` | str | echo of slug |
| `watched_count` | int | number of names in the prompt |
| `personal_use_directive` | bool | forced OFF hosted (FR-016) |
| `prompt` | str | the copy-ready prompt (screen format) |
| `data_as_of` | str | disclosure envelope (FR-015) |
| `disclaimer` | str | disclosure envelope (FR-015) |

## Validation & invariants

- **Determinism (FR-007)**: rendered body excludes `captured_at`; builders remain pure.
- **Absent-fallback (FR-008)**: no mapping entry ⇒ zero added bytes for that name.
- **No fresh generation (FR-009)**: export reads the store only; never calls
  `collect_sources` / scorer / narrative generation.
- **Fail-soft (FR-010)**: per-ticker resolve is best-effort; one bad report omits only its
  section.
- **No-directive (FR-006)**: every rendered string passes `validate_no_directive_language`; the
  Playwright copy lint covers the output.
- **No strategy/indicator/backtest change (FR-017)**: no touch to strategy files, indicators, or
  backtest artifacts.
