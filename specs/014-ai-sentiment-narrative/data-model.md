# Phase 1 Data Model: AI Sentiment & Narrative Intelligence (+ 3 bug fixes)

Entities for the sentiment overlay plus the reused/repaired entities for the three bug fixes.
Determinism, sourcing, and no-directive rules are enforced at the model boundary.

---

## New entities (sentiment overlay)

### SourceItem
An individual news/event/filing/opinion record used as narrative evidence (FR-S2/S10).

| Field | Type | Notes |
|---|---|---|
| `id` | str | Stable id (e.g. `url` hash or `8K:<accession>`), used in the report fingerprint. |
| `source_class` | enum | `news` \| `filing_8k` \| `earnings` \| `analyst_opinion` \| `social` (social omitted by default). |
| `title` | str | Headline / event label. |
| `publisher` | str \| null | Feed / source name (source tag, Principle I). |
| `published_at` | ISO date-time | Required; drives freshness + "stale" labeling. |
| `reference_url` | str \| null | Link/reference for auditability. |
| `is_stale` | bool | True when older than the class freshness threshold (labeled, not hidden). |
| `score` | float \| null | Per-item FinBERT `P(pos) − P(neg)` (captured); null for the lexicon path. |

**Rules.** No SourceItem ⇒ the report shows an explicit **no-signal** state (never fabricated).
A class that is unavailable / out-of-budget / licensing-restricted is **omitted**, never faked.

### SentimentReport
Produced on request for one ticker + snapshot; captured once and served verbatim (FR-S1/S5).

| Field | Type | Notes |
|---|---|---|
| `ticker` | str | Uppercased symbol. |
| `origin` | enum | `screener` \| `holding` \| `manual` (from the Selection). |
| `label` | enum | `positive` \| `mixed` \| `negative` \| `no_signal`. From **FinBERT (captured)** or the **lexicon fallback** — reproducible per fingerprint. |
| `label_basis` | str | Short, inspectable explanation (FinBERT score / pos-neg counts). |
| `sentiment_composite` | float \| null | 24h/7d/30d/90d recency-weighted composite (Decision 2), missing components renormalized. **Presentation-only.** |
| `narrative_risk` | obj \| null | `{ score: 0–100, label: str, signals: str[] }` (Decision 10) — neutral non-directive label; feasible signals only. **Presentation-only.** |
| `narrative` | str | ≤ N-sentence plain-language storyline; **zero directive terms**; every claim maps to a `sources` item. |
| `narrative_source` | enum | `model` (LLM, captured) \| `template` (budget/degrade path) \| `absent` (no-signal). |
| `sources` | SourceItem[] | The dated evidence set; per-class labeled. |
| `source_classes_present` | str[] | Which classes contributed (others omitted, listed as omitted). |
| `fingerprint` | str | `sha256(ticker + sorted(source ids+dates) + snapshot_as_of + scorer_id + model_id + prompt_version)`. |
| `budget_state` | enum | `ok` \| `budget_exhausted` \| `unavailable` (source/model outage). |
| `data_as_of` | ISO | Snapshot as-of (envelope). |
| `disclaimer` | str | Envelope disclaimer. |

**Rules.** Informational-only: a SentimentReport (label, score, composite, narrative_risk, prose)
MUST NOT alter any gate result, rank, level, sizing, regime, or backtest (FR-S3). Same `fingerprint`
⇒ byte-identical output (SC-004) — served from the store, never regenerated. `narrative_risk` uses
neutral, non-directive labels (FR-S4/S12) and omits signals whose sources aren't available (e.g. the
deferred social layer), never estimating them.

### ReportRequest / Selection
The owner-assembled set of tickers to analyze (FR-S0/S0a/S0b/S0c).

| Field | Type | Notes |
|---|---|---|
| `selections` | Selection[] | 1..N; empty ⇒ rejected with "select at least one stock" (FR-S0c). |
| Selection.`ticker` | str | Symbol; manual entries validated/resolved independently (FR-S0b). |
| Selection.`origin` | enum | `screener` \| `holding` \| `manual`. |
| Selection.`as_of` | str \| null | Snapshot pin (defaults to current snapshot). |

**Rules.** Only tickers in `selections` are analyzed — **0 calls for non-selected stocks**, **0
auto-generation** (SC-009). An unresolvable manual symbol returns a per-name
"symbol not found / no coverage" state without failing the other selected names.

### SpendLedger (internal, not API-exposed)
Monthly spend accounting for the hard cap (FR-S9, SC-007).

| Field | Type | Notes |
|---|---|---|
| `period` | str | `YYYY-MM`. |
| `estimated_spend_usd` | Decimal | Sum of projected costs of paid generations this period. |
| `cap_usd` | Decimal | `SCREENER_SENTIMENT_MONTHLY_CAP_USD` (default 5.00). |

**Rules.** A paid call proceeds only if `estimated_spend + projected_call_cost ≤ cap_usd`; otherwise
degrade to the `template` narrative. Cache hits are free and unmetered.

---

## Reused / repaired entities

### WatchlistEntry (existing — Bug A)
Unchanged shape (`frontend/src/lib/store.ts`): `id`, `ticker`, `name`, `sector`, `strategy_slug`,
`saved_at`, `state`, `levels_snapshot{entry,stop_loss,take_profit}`, optional entry-timing fields.
Bug A adds **no field** — it adds a detail-page control + confirmation feedback over the existing
idempotent `saveCandidate` action (dedup on `ticker+strategy_slug`).

### MarketRegime / RegimeInputs (existing — Bug B)
`backend/src/models/regime.py`. Bug B ensures the inputs are populated from the SPY source with
sufficient history and adds/propagates a concrete **unavailable reason** when the 200-day SMA truly
can't be computed:

| Field | Type | Notes |
|---|---|---|
| `spy_close` | Decimal \| null | Latest SPY close from the chosen source. |
| `spy_sma200` | Decimal \| null | Computed 200-day SMA (null only on true insufficient history). |
| `spy_above_sma200` | bool \| null | Verdict; null ⇒ reason must be present. |
| `price_source_name` | str | `yfinance` \| `baked(daily)` \| `stooq(local)` (never silently empty). |
| `unavailable_reason` | str \| null | **New** — concrete reason + "gate fails open" when SMA is null (FR-B2). |
| `as_of_date` | date | SPY series as-of. |

**Rules.** Deterministic per snapshot (FR-B3); no strategy rule/default/citation/indicator/baseline
change. Never emit a bare "Unknown" when the data to compute a verdict exists (FR-B1).

### MarketEvent / EventSource (existing — Bug C)
`backend/src/models/events.py` + `events_store` source row. Bug C changes **freshness accounting +
curated content coverage**, not the event schema:
- `EventSource.last_refreshed_at` is stamped to the **actual reseed time**, so a re-seeded valid
  curated calendar isn't derived-stale; `source_as_of` (content date) is surfaced separately.
- The curated event window is rolled forward with **real published dates only**; when official
  schedules end, the calendar ends (labeled), never fabricates dates.

**Rules.** No strategy impact; the macro calendar is a display overlay. Stale badge shows only when
truly past the refresh interval.
