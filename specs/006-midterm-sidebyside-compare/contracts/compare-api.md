# Contract: Mid-Term Side-by-Side Comparison API

Two new endpoints on the existing `/strategies` router
([backend/src/api/strategies.py](../../../backend/src/api/strategies.py)). Both
run the fixed four-variant matrix over one shared snapshot.

## POST `/strategies/midterm-compare`

Run the four mid-term variants side by side and return their screens.

### Request body (`ScreenRunRequest`, reused)

```jsonc
{
  "parameters": { "as_of_date": "...", "liquidity_min_price": 5.0, "...": "..." },
  "filters":    { "shariah_only": false },
  "shariah_overrides": {},
  "as_of_date": "2026-06-12"        // optional; defaults to latest snapshot
}
```

Notes:
- Liquidity/universe/market/shariah parameters apply identically to all four
  variants (they shape the shared snapshot).
- The four variants' A/B parameters (`sector_strength_top_fraction`,
  `min_momentum_12_1`) are **set by the matrix**, not the caller; any caller value
  for those two is ignored so the matrix stays well-defined (FR-001/FR-004).

### Response (`MidtermComparisonResponse`)

```jsonc
{
  "variants": [
    {
      "key": "momentum_sector_on",
      "label": "Momentum — sector gate ON",
      "strategy": { "...": "full Strategy declaration" },
      "toggle_param": "sector_strength_top_fraction",
      "toggle_value": 0.5,
      "toggle_on": true,
      "screen": { "...": "ScreenResult (candidates, gate_results, levels, parameters_snapshot)" },
      "bias_check": { "confirmed": true, "passed": false, "note": "..." }
    },
    { "key": "momentum_sector_off", "toggle_value": 1.0, "toggle_on": false, "...": "..." },
    { "key": "value_floor_on",      "strategy": "...value...", "toggle_param": "min_momentum_12_1", "toggle_value": -0.20, "toggle_on": true,  "...": "..." },
    { "key": "value_floor_off",     "toggle_value": -1.0, "toggle_on": false, "...": "..." }
  ],
  "regime": "bull",
  "data_as_of": "2026-06-12",
  "disclaimer": "…not investment advice…"
}
```

### Guarantees

- `variants` has exactly 4 entries in fixed order (FR-001, SC-001).
- All four `variants[*].screen.data_as_of == data_as_of` and were evaluated over
  the **same** universe snapshot and the **same** `regime` (FR-002).
- Within each strategy pair, every declared parameter except the toggled one is
  identical (FR-004, SC-003).
- Each variant carries `data_as_of` + `disclaimer` transitively via its
  `ScreenResult` (FR-009, SC-004).
- Deterministic: identical request + snapshot → identical response (FR-007, SC-002).
- An empty variant returns `screen.candidates == []` with gate-accounting notes
  and does not error or drop the other three (FR-016).

## POST `/strategies/midterm-compare/advisor-prompt`

Run the matrix and return ONE combined four-variant advisor prompt.

### Request body

Same `ScreenRunRequest` as above.

### Response (`MidtermComparePromptResponse`)

```jsonc
{
  "prompt": "TASK …\n\n## Market regime …\n\n## Variant 1 — Momentum — sector gate ON …",
  "variant_count": 4,
  "personal_use_directive": false,
  "data_as_of": "2026-06-12",
  "disclaimer": "…not investment advice…"
}
```

### Guarantees

- `prompt` contains four delimited variant sections, each with its declaration,
  gate results, levels, the shared regime, and that strategy's bias-check verdict
  (FR-011/FR-012, SC-006).
- `prompt` is byte-identical on repeat export for the same snapshot (FR-013, SC-007).
- `personal_use_directive` mirrors `SCREENER_PERSONAL_USE_DIRECTIVE`; directive
  framing appears only when it is true (FR-014). Default OFF.
- No required content is truncated regardless of prompt size (FR-013).

## Error behaviour

- Unknown/invalid snapshot date → same handling as `/strategies/{slug}/run`.
- If one underlying strategy is disabled-by-default, the matrix still runs its
  variants for inspection and carries its failing bias-check honestly; it does not
  present the strategy as validated (spec edge case).
