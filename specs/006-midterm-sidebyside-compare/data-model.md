# Phase 1 Data Model: Mid-Term Side-by-Side Variant Comparison

All entities are additive response/orchestration shapes. No persisted schema, no
change to `Candidate`, `ScreenResult`, or `Strategy` themselves — variants reuse
the existing `ScreenResult` per variant.

## VariantSpec (internal, fixed matrix)

The four-variant definition the runner iterates. Not a wire model.

| Field | Type | Notes |
|-------|------|-------|
| `key` | str | stable id, e.g. `momentum_sector_on`, `momentum_sector_off`, `value_floor_on`, `value_floor_off` |
| `label` | str | human label, e.g. "Momentum — sector gate ON" |
| `slug` | str | `midterm_52w_high_momentum` or `midterm_value_composite` |
| `toggle_param` | str | `sector_strength_top_fraction` or `min_momentum_12_1` |
| `toggle_value` | float | `0.5` / `1.0` / `-0.20` / `-1.0` |
| `toggle_on` | bool | whether the A/B'd gate is ON for this variant |

Fixed set (Decision 1). Validation: exactly four specs; the two specs sharing a
slug differ **only** in `toggle_value` (FR-004 / SC-003).

## VariantResult (wire)

One entry per variant in the comparison response.

| Field | Type | Notes |
|-------|------|-------|
| `key` | str | matches `VariantSpec.key` |
| `label` | str | display label including toggle state (FR-003) |
| `strategy` | `Strategy` | the live declaration (citation, parameters, modifications) |
| `toggle_param` | str | the single parameter that differs within the strategy pair |
| `toggle_value` | float | this variant's value of that parameter |
| `toggle_on` | bool | gate ON/OFF for this variant |
| `screen` | `ScreenResult` | ranked candidates, per-candidate gate accounting, levels, `parameters_snapshot` |
| `bias_check` | object | `{confirmed, passed, note}` from `load_survivorship_status(slug)` — same for both variants of a strategy (Decision 6) |

Validation rules:
- `screen.candidates` may be empty; an empty variant is shown with its
  gate-accounting notes and must not suppress siblings (FR-016).
- For variants where `toggle_on` is false, the disabled gate must be reported as
  intentionally disabled, not skipped-on-missing-data (FR-006).

## MidtermComparisonResponse (wire)

The full four-variant payload.

| Field | Type | Notes |
|-------|------|-------|
| `variants` | `list[VariantResult]` | exactly 4, fixed order (momentum on, momentum off, value on, value off) |
| `regime` | str \| null | shared market regime for the snapshot (computed once) |
| `data_as_of` | str | shared snapshot date (identical across all four, FR-002) |
| `disclaimer` | str | standing non-advice disclaimer (FR-009) |

Validation: `len(variants) == 4`; all variants share `data_as_of` and saw the
same universe (FR-002 / SC-001).

## MidtermComparePromptResponse (wire)

| Field | Type | Notes |
|-------|------|-------|
| `prompt` | str | the single combined four-variant advisor prompt |
| `variant_count` | int | 4 |
| `personal_use_directive` | bool | reflects `SCREENER_PERSONAL_USE_DIRECTIVE` (FR-014) |
| `data_as_of` | str | shared snapshot date |
| `disclaimer` | str | standing disclaimer |

Validation: `prompt` is byte-identical on repeat export for the same snapshot
(FR-013 / SC-007); contains four delimited variant sections, each with
declaration + gates + levels + shared regime + that strategy's bias-check (FR-012
/ SC-006); no required content truncated.

## Four-variant advisor prompt (document structure)

Plain-text/markdown document (not JSON). Section order:

1. **Task header** — shared, four-variant framing (neutral by default; directive
   only when the personal-use flag is on).
2. **Market regime** — shared, computed once for the snapshot.
3. **Variant 1 … Variant 4** — each delimited section:
   - strategy declaration (name, citation, timeframe, parameters incl. the toggled
     value, regime favorability, modifications + citations),
   - run-configuration line (the toggle state for this variant),
   - per-candidate compact blocks (rank, levels, ranking inputs, gates),
   - the strategy's honest `bias_check` verdict.
4. **Combined honesty footer** — survivorship/look-ahead caveat applied to all,
   data freshness, disclaimer, and (if directive) the personal-use scope note.

See `contracts/advisor-prompt.schema.md`.
