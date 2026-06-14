# Phase 1 — Data Model

Entities introduced or extended by feature 007. All additions to existing
response models are **additive** (optional fields) to preserve determinism and
backward compatibility with the other strategies.

## CacheEntryClassification (transient, refresh-time)

Produced by `refresh_edgar_coverage` for each ticker; not persisted beyond the
coverage report.

| Field | Type | Notes |
|-------|------|-------|
| `ticker` | str | uppercase symbol |
| `cik` | str \| None | resolved from SEC `company_tickers.json`; None → cannot re-fetch |
| `instrument` | enum | `common_equity \| preferred \| adr \| fund \| unknown` (D2) |
| `state` | enum | `complete \| partial \| fixable_stub \| non_equity_stub \| not_cached` (D1) |
| `bytes` | int | file size (diagnostic) |
| `schema_version` | int \| None | from payload; `<3` ⇒ partial |
| `action` | enum | `refetch \| skip_non_equity \| skip_no_cik \| leave` |

Validation: `action = refetch` only when `state ∈ {fixable_stub, partial}` AND
`instrument ∈ {common_equity, unknown}` AND `cik` is not None.

## CoverageReport (artifact)

Emitted before/after the refresh (and consumable by a guard test). The measurable
proof for SC-001.

| Field | Type | Notes |
|-------|------|-------|
| `universe_scope` | str | e.g. "screened-592" or "full-cache-4242" |
| `counts_before` / `counts_after` | map<state,int> | per-`state` tallies |
| `refetched` | int | successfully upgraded to complete |
| `refetch_failed` | list<str> | tickers whose re-fetch still failed (kept prior state) |
| `non_equity_excluded` | int | filtered from value universe |
| `value_yield_missing_residual` | int | irreducible floor after refresh (SC-001) |
| `generated_at` | iso-8601 | |

## ProfitabilityGateResult (per candidate)

Added to the existing `gate_results` array; same shape as other gates.

| Field | Type | Notes |
|-------|------|-------|
| `gate` | "Profitability" | |
| `status` | enum | `pass \| fail \| skipped` |
| `detail` | str | e.g. "CFO 1.2e8 > 0 and ROA 0.07 > 0" / "CFO ≤ 0" / "no CFO/ROA inputs" |

Rule: pass ⟺ `operating_cf > 0 AND roa > 0`; missing either input ⇒ skipped
(excluded in hard mode, like the F-Score gate; NOT fail-open).

## LevelDerivation (per candidate, extended)

Existing entry/stop/take_profit, with the floor made explicit.

| Field | Type | Notes |
|-------|------|-------|
| `entry` | float | close |
| `atr` | float | 14-period ATR |
| `sma_200_stop` | float \| None | candidate trend stop |
| `stop_loss` | float | final stop after the min-risk floor (D5) |
| `stop_basis` | enum | `sma_trend \| atr_floor_fallback \| structure` — why this stop |
| `risk_per_share` | float | `entry − stop_loss`, guaranteed `≥ 1·ATR` |
| `take_profit` | float | `entry + R·risk_per_share` |

Invariant (SC-004): `risk_per_share ≥ 1·ATR` for every candidate; displayed
R-multiple equals `(take_profit − entry) / risk_per_share`.

## Candidate (extended, additive fields)

On `Candidate` (`backend/src/models/strategy.py`) and the Zod `CandidateSchema`:

| Field | Type | Notes |
|-------|------|-------|
| `f_score_low_confidence` | bool | true when `f_score_evaluable < 9` (FR-009) |
| `sector_rank` | int \| None | rank within sector (FR-010) |
| `data_quality_flags` | list<str> | e.g. `negative_fcf`, `outlier_yield` (FR-012) |
| `stop_basis` | str | from LevelDerivation |

## ScreenResult / AnalyzeResponse (extended, additive)

| Field | Type | Notes |
|-------|------|-------|
| `regime_available` | bool | false ⇒ UI shows regime-blind banner (FR-011) |
| `sector_groups` | map<sector, {kept: [str], dropped: [str]}> | within-sector cap visibility (FR-010) |
| `out_of_scope_count` | int | non-equity instruments excluded from the value universe (FR-003) |
| `data_notes` | list<str> | existing; staleness note text refined (D7) |

## InstrumentType (reference, data layer)

`backend/src/data/instruments.py` → `classify(ticker, payload) -> InstrumentType`
(`common_equity | preferred | adr | fund | unknown`). Pure function over the
ticker string + cached payload; golden-fixture tested (test_instruments.py).
