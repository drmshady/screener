# Contract: Base-Pattern Geometric Classifier (US1, FR-002a)

`indicators/base_pattern.py` — a new **indicator**, so it ships with golden-fixture tests
**before** any consumer (constitution Principle IV). Pure, deterministic, no I/O.

## Signature

```python
def classify_base(high: pd.Series, low: pd.Series, close: pd.Series, *,
                  flat_min_weeks: float = 5.0, cup_min_weeks: float = 7.0,
                  max_depth: float = 0.33, confidence_cutoff: float = ...) -> BasePattern
```

Returns `BasePattern` (data-model §2): `{detected, base_type, pivot, handle_high,
base_start, base_end, base_length_weeks, base_depth, confidence}`. Input series are the
**split/dividend-adjusted** daily bars used everywhere else (feature 008 basis).

## Recognized types & rules

| Type | Geometry | Pivot | Min length |
|------|----------|-------|-----------|
| `flat` | shallow sideways range, no deep correction | base high | 5 weeks |
| `cup` | left rim → rounded trough → return near rim | rim high | 7 weeks |
| `cup_with_handle` | cup followed by a short shallow upper-portion drift (handle) | **handle high** | 7 weeks (cup + handle) |
| `double_bottom` | two troughs split by an interior peak, 2nd ≈ 1st | interior-peak high | 7 weeks |

## Invariants

1. **Most-recent base wins** when several qualify; deterministic tie-break by latest
   `base_end` (spec edge case).
2. **High precision over recall**: when no type meets its constraints with `confidence ≥
   confidence_cutoff`, return `detected=False, base_type="none"` and null pivot/length/depth
   → downstream base components are `undetermined`, never a fabricated pivot (FR-002a/FR-003).
3. **Cup-with-handle pivot is the handle high**, not the cup rim (FR-002).
4. **Depth** = `(base_high − base_low)/base_high`; **length** in weeks from `base_start` to
   `base_end`.
5. **Determinism**: identical series → identical `BasePattern`.
6. Insufficient history (shorter than the minimum base window) → `detected=False`.

## Golden-fixture tests (TEST-FIRST, Principle IV)

- One hand-constructed fixture per type asserting `base_type`, `pivot`/`handle_high`,
  `base_length_weeks`, and `base_depth` to documented tolerance.
- A flat-vs-cup disambiguation fixture (correct label).
- A "no base" fixture (noisy/insufficient history) → `detected=False`.
- A deep-correction fixture → depth measured > `max_depth` (drives the base-depth component
  fail downstream, not a detection failure).
- A multiple-bases fixture → the most-recent base is selected.
