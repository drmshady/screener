# Data Model: Release Readiness (009)

This feature adds **no persisted store and no schema migration**. The entities
below are either (a) computed-on-read response shapes derived from the existing
`backend/data/manifest.json` and the trading calendar, or (b) documentation
artifacts (bug-scan log, deployment runbook). They formalize the spec's Key
Entities.

---

## 1. Data Freshness Record (computed, per source)

Derived at request time from the manifest + `latest_completed_trading_day()`.
Not persisted as a new store.

| Field | Type | Notes |
|-------|------|-------|
| `source_name` | string | e.g. `yfinance`, `stooq`, `edgar`, `econ_calendar`. Manifest key. |
| `kind` | string | `prices` \| `fundamentals` \| `calendar` \| `holdings` … (from manifest). |
| `data_as_of` | date | Latest completed trading session the source's cached data covers (for `prices`, the max `last_bar_date`; otherwise `source_as_of`'s date). |
| `latest_session` | date | `latest_completed_trading_day()` for the source's market (weekend/holiday aware). |
| `sessions_behind` | int ≥ 0 | Trading sessions between `data_as_of` and `latest_session` (0 = current). |
| `is_stale` | bool | `sessions_behind > refresh_interval_days` (or manifest's explicit `is_stale`). |
| `last_refresh_outcome` | enum | `success` \| `failed` \| `skipped-current` — outcome of the most recent refresh attempt for this source (from the refresh response / manifest). |

**Validation / rules**:
- `sessions_behind` MUST use the trading calendar, not raw calendar days, so a
  weekend/holiday start does not report false staleness (FR-005).
- A source missing from the manifest is reported as `data_as_of: null`,
  `is_stale: true` (unknown freshness is treated as stale, never as current).

**Aggregate** (envelope for `GET /data/freshness`):

| Field | Type | Notes |
|-------|------|-------|
| `sources` | Data Freshness Record[] | One per material source. |
| `any_stale` | bool | True iff any record `is_stale`; drives the startup prompt. |
| `latest_session` | date | The reference session used for the computation. |
| `data_as_of` | datetime | Response envelope timestamp (middleware default). |
| `disclaimer` | string | Standard non-advice disclaimer (middleware default). |

---

## 2. Advisor Prompt Document (additive fields)

The exported prompt is a string assembled by `agent/advisor_prompt.py`. This
feature adds **per-material-input freshness** to make it self-contained; no field
is removed. The honesty block stays driven by the real backtest bias check.

Required content (FR-006–FR-010), with **new** items marked:

| Section | Content | Status |
|---------|---------|--------|
| Task instruction | Neutral framing (or directive iff flag ON); zero directive words otherwise | existing |
| Strategy | Name, slug, citation, timeframe, holding period, liquidity gate, gates, ranking, modifications + citations | existing |
| Candidate | Ticker/name/sector, would-be-selected, price levels, R:R, ranking + fundamental diagnostics | existing |
| **Per-input freshness** | Prices `data_as_of`, fundamentals `data_as_of`, regime as-of — each material input named with its own freshness | **NEW** |
| Data-integrity warning | Verbatim, prominent, when the candidate is flagged | existing (verify) |
| Gate-by-gate | Pass/Fail/Skipped with detail; skipped ≠ real pass | existing |
| Market regime | Current regime + favorability | existing |
| Honesty & limitations | Real survivorship/bias verdict, data gaps, data notes, freshness, disclaimer | existing (extend with per-input freshness) |

**Rules**:
- The prompt MUST NOT reference app-only context (no "see the screen", no
  in-app-only identifiers) — fully standalone (FR-006).
- Builder remains a **pure function** of its inputs (no wall-clock in body);
  freshness values come from the result/snapshot, preserving byte-identical
  re-export for a fixed snapshot.
- Zero directive trading language when the directive flag is OFF (default).

---

## 3. Bug Scan Finding (documentation: `bug-scan-log.md`)

One row per discovered defect or robustness gap.

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Sequential, e.g. `BUG-001`. |
| `location` | string | File / endpoint / flow where found. |
| `description` | string | What is wrong and how to reproduce. |
| `severity` | enum | `correctness` \| `integrity` \| `crash-hang` \| `minor`/`cosmetic`. |
| `resolution` | enum | `fixed` (+ commit/test ref) \| `deferred-with-rationale` (+ one-line reason). |

**Release gate (SC-007)**: 0 findings with severity in
{`correctness`, `integrity`, `crash-hang`} may remain `deferred`. Every `minor`
deferral carries an explicit rationale. 0 unaddressed (untriaged) findings.

---

## 4. Deployment Runbook (documentation: `quickstart.md` + README)

Ordered, reproducible steps from a clean environment to a running production
build.

| Element | Requirement |
|---------|-------------|
| Prerequisites | Python 3.12 (`py -3.12`), Node + `npm.cmd`, data directories present. |
| Backend bring-up | Install editable backend; seed/refresh data (incremental); start uvicorn. |
| Frontend prod build | `npm run build` then `npm run start` (Next production), `NEXT_PUBLIC_API_URL` set at runtime — **not** baked into the build. |
| Data directories | Documented locations for prices store, EDGAR slim cache, manifest, calendars. |
| Provider keys | Optional keys supplied **process-local/inline only**, never written to a file (FR-022). |
| Smoke verification | Exercise screen → candidate detail → advisor prompt → portfolio; confirm matches test-validated behavior (FR-021, SC-009). |
| Finalization | Working tree committed on `009-release-readiness`, suite green (FR-023). |

**Rule**: A first-time follow on a clean environment MUST need **0** missing or
incorrect steps (SC-009).
