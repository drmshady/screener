# Contract: Fair-Value Estimate (US3, FR-018)

**Surface:** a pure function producing a per-candidate fair-value estimate from the
existing point-in-time inputs. If the adopted basis is a new computed intrinsic
model, it lives in `indicators/fair_value.py` (pure, no I/O) with a
**golden-fixture test written first** (Principle IV) and a citation.

## Inputs (existing, point-in-time)

From `FundamentalsLoader.value_metrics_as_of`: book equity, net income TTM,
operating CF TTM, revenue TTM, shares outstanding (and the
[`indicators/valuation.py`](../../../backend/src/indicators/valuation.py) yields);
plus the latest close. No new data source.

## Output

`{ fair_value, basis, source_as_of, provenance, trust_flag, margin_of_safety }`
(see data-model). `fair_value` is `None` when inputs are missing.

## Trust rules (FR-016/018, Edge Cases)

- `trusted` only when inputs are present, fresh, and the estimate is in a sane
  range relative to price (not negative, not wildly off).
- `unavailable` (missing inputs) / `stale` (input as-of too old) / `out_of_range`
  (implausible) ⇒ **not used** downstream (sizing + target cap fail open).
- Always carries `source_as_of` + `provenance` (source tag + model + citation) so
  it is reproducible and inspectable; point-in-time (no hindsight).

## Basis selection (FR-018/019)

At least **(a)** the valuation-yields composite and **(b)** a simple cited
intrinsic model are compared on real data for reliability + coverage in the US4
artifact; the most reliable is adopted and documented.

## Tests

Golden-fixture numeric test for the adopted model (test-first); trust-flag
transitions (available/missing/stale/out-of-range); determinism.
