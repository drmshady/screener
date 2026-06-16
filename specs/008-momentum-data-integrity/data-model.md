# Data Model: Strategy Defect Detection & Output Integrity

**Feature**: 008-momentum-data-integrity | **Date**: 2026-06-15

All additions are **additive** to existing Pydantic models and DataFrame columns. No store schema migration. Existing API consumers are unaffected because new fields are optional with safe defaults.

---

## 1. OutputContract (new, per-strategy, in-code)

The machine-checkable declaration the strategy-agnostic engine reads (FR-001). Lives next to the strategy (`strategies/<slug>.py`), referenced by `Strategy.output_contract`.

| Field | Type | Notes |
|-------|------|-------|
| `strategy_slug` | str | Owning strategy. |
| `invariants` | list[Invariant] | Ordered; evaluated per candidate row. |

## 2. Invariant (new)

| Field | Type | Notes |
|-------|------|-------|
| `name` | str | Stable identifier, e.g. `coherence.dist_to_high`, `series.seam_consistent`. |
| `family` | str | One of: `coherence`, `gate`, `score`, `level`, `value_domain`, `series`, `identity`. |
| `severity` | str | `candidate` → per-candidate warning + demotion; `aggregate` → data note. |
| `predicate` | Callable[[row, signals], bool] | Pure; `True` = satisfied. No I/O, no wall-clock. |
| `figure` | str \| None | The surfaced field the rule guards (`return_12_1`, `52w_high`, `close`, `score`, `stop_loss`, …). |
| `message` | str | Operator-facing reason template ("…— verify before acting"). |

**Validation rules**: predicates MUST be deterministic and side-effect-free; an invariant that needs the backing series reads only the precomputed `signals` columns (Decision 7), never re-fetches.

## 3. ContractViolation (new)

A detected breach (Key Entity "Defect / contract violation").

| Field | Type | Notes |
|-------|------|-------|
| `invariant_name` | str | Which rule broke. |
| `family` | str | Copied from the invariant. |
| `figure` | str \| None | Affected figure. |
| `reason` | str | Rendered, specific, actionable message. |
| `severity` | str | `candidate` \| `aggregate`. |

## 4. DataIntegrityWarning (new wire model on Candidate)

Per-candidate serialization of a candidate-severity `ContractViolation`, distinct from the existing soft-gate `warnings: list[str]`.

| Field | Type | Notes |
|-------|------|-------|
| `figure` | str \| None | e.g. `close`, `return_12_1`. |
| `rule` | str | Invariant name. |
| `reason` | str | Verbatim message; travels into the advisor prompt (FR-019). |

## 5. Candidate (MODIFY — `models/strategy.py`)

Additive fields:

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `data_integrity_warnings` | list[DataIntegrityWarning] | `[]` | Candidate-severity violations (US4/FR-017). |
| `data_suspect` | bool | `False` | True iff any candidate-severity violation; drives demotion + UI badge (FR-018). |

`warnings` (soft-gate) is **unchanged** and kept separate — a data-integrity warning is not a soft-gate warning.

## 6. Strategy (MODIFY — `models/strategy.py`)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `output_contract` | OutputContract \| None | `None` | Optional so strategies without a contract still load. The registry does not require it (back-compat); momentum + value declare one. |

## 7. ScreenResult (no field change)

`data_notes` (existing) carries aggregate-severity violations and the "flagged/corrected N names" honesty note (FR-004, US4-AC4). No new field.

## 8. Snapshot series-integrity signals (new DataFrame columns)

Computed once in `_compute_snapshot_rows` (Decision 7); consumed by series/value-domain invariants; **not** persisted to a store.

| Column | Type | Meaning |
|--------|------|---------|
| `series_dates_ok` | bool | Backing series has strictly increasing, unique dates. |
| `series_max_session_move` | float | Largest \|single-session return\| in the lookback. |
| `seam_consistent` | bool | Stooq↔overlay adjustment factor was derivable and stable (Decision 2). |
| `seam_factor` | float \| None | The applied back-adjustment factor (1.0 when single-source). |
| `corporate_action_in_window` | bool | A split/dividend (from the adj_close/close ratio) lies inside the lookback. |
| `adj_close_basis_used` | bool | Lookback figures were computed on the adjusted series (vs raw fallback). |
| `share_class_consistent` | bool | Price-series ticker and fundamentals ticker resolve to one share class (FR-014). |

Existing momentum figures (`close`, `52w_high`, `return_12_1`, `dist_to_high`, `entry`, `stop_loss`, `take_profit`, `score`, `vol_scalar`, `atr`) are unchanged in shape; only their **derivation basis** changes per Decisions 1–2.

## 9. SeededDefect (new, harness-only)

A synthetic fault injected by the offline harness (Key Entity "Seeded defect").

| Field | Type | Notes |
|-------|------|-------|
| `defect_class` | str | `corrupted_price`, `broken_score`, `stale_but_fresh`, `nan_field`, `inconsistent_dist_to_high`, `seam_discontinuity`, `share_class_swap`. |
| `target_ticker` | str | Name to corrupt in the frozen snapshot copy. |
| `apply` | Callable | Mutates a snapshot copy to introduce the fault. |
| `expected_family` | str | The invariant family that MUST fire. |

## 10. CrossCheckVerdict (new, harness-only report row)

| Field | Type | Notes |
|-------|------|-------|
| `ticker` | str | Candidate. |
| `screener_price` / `screener_52w_high` | float | From the frozen snapshot. |
| `independent_price` / `independent_52w_high` | float \| None | From the independent reference. |
| `divergence_pct` | float \| None | Percentage difference. |
| `verdict` | str | `AGREES` \| `DIVERGES_AND_FLAGGED` \| `DIVERGES_UNFLAGGED` \| `UNVERIFIED` \| `STALE` (genuine staleness, FR-011). |
| `independent_fetch_at` | str | ISO timestamp of the live fetch (the only non-deterministic field). |
