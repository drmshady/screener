# Contract — API / Schema Field Additions

All additions are **additive and optional** so existing strategies and the
deterministic snapshot tests are unaffected. Mirror each on the backend Pydantic
model and the frontend Zod schema, or the frontend strips it.

## Candidate (backend `models/strategy.py` ↔ frontend `lib/api.ts` CandidateSchema)

| Field | Type | Default | FR |
|-------|------|---------|----|
| `f_score_low_confidence` | bool | false | FR-009 |
| `sector_rank` | int \| null | null | FR-010 |
| `stop_basis` | str | "sma_trend" | FR-006 |
| `data_quality_flags` | string[] | [] | FR-012 |

`gate_results` (existing array) gains `"Cheapness cut"` and `"Profitability"`
entries — no schema change, the array already flows.

## ScreenResult / AnalyzeResponse

| Field | Type | Default | FR |
|-------|------|---------|----|
| `regime_available` | bool | true | FR-011 |
| `sector_groups` | record<string,{kept:string[],dropped:string[]}> \| null | null | FR-010 |
| `out_of_scope_count` | int | 0 | FR-003 |

`data_notes` (existing) carries the refined staleness wording (D7) and the
"N non-common-equity instruments out of value scope" line.

## UI rendering obligations (FR-008..FR-012)

- `regime_available === false` → prominent banner: the run is regime-blind and the
  value strategy's regime master-switch could not be applied (no directive copy).
- `f_score_low_confidence` → a "low-confidence (n/9)" badge on the candidate.
- `sector_groups` → candidates rendered grouped by sector with the per-sector cap
  and dropped names visible.
- `data_quality_flags` → non-gating badges (`negative FCF`, `outlier yield`).
- Cheapness-cut and Profitability gates render in the existing gate panel.

## Determinism

Same snapshot ⇒ identical values for every field above (SC-002). New fields are
pure functions of existing row data; none introduces wall-clock or random inputs.

## Lint

Every new string MUST pass the Playwright no-directive lint (FR-013); badges use
neutral framing ("low-confidence", "outlier yield"), never "buy/sell/avoid".
