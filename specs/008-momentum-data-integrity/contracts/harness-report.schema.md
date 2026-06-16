# Contract: Offline Integrity Harness Report

**Feature**: 008-momentum-data-integrity

Structure of the human-readable report emitted by `scripts/run_integrity_harness.py` (FR-007), following the feature-002 findings-report pattern. The report is the serialization of one harness run over a frozen snapshot. A report missing any REQUIRED section is itself a process defect.

---

## Required sections (in order)

### 1. Run Header (REQUIRED)

- `run_date`, `snapshot_as_of`, `snapshot_id`, `independent_source` (vendor name), `independent_fetch_at` (ISO; the only non-deterministic field).
- **Overall verdict**: `pass` | `fail`.
- Counts: seeded defects injected / detected / missed; cross-check verdicts by class.

### 2. Seeded-Defect Results (REQUIRED) — FR-008, SC-001

One row per injected defect class; **100% detection required** (any miss → overall `fail`).

| Defect class | Target | Expected family | Detected | Result |
|--------------|--------|-----------------|----------|--------|
| corrupted_price | … | value_domain/series | ✓/✗ | PASS/**FAIL** |
| broken_score | … | score | | |
| stale_but_fresh | … | series/value_domain | | |
| nan_field | … | value_domain | | |
| inconsistent_dist_to_high | … | coherence | | |
| seam_discontinuity | … | series | | |
| share_class_swap | … | identity | | |

A control (un-corrupted) copy MUST raise **no** warning on the same names (no false positive — SC-002).

### 3. Independent Cross-Check (REQUIRED) — FR-010/FR-011, SC-003/SC-004

One row per top-N candidate (N = returned list, capped at 10):

| Ticker | Screener price | Independent price | Divergence % | Screener 52w-high | Independent 52w-high | Verdict |
|--------|----------------|-------------------|--------------|-------------------|----------------------|---------|
| BELFB | … | … | … | … | … | DIVERGES_AND_FLAGGED |
| JBHT | … | … | <10% | … | … | AGREES |
| CW | … | … | <10% | … | … | AGREES |

- Verdict set: `AGREES` (<10%), `DIVERGES_AND_FLAGGED` (≥10% **and** screener carries a data-integrity warning), `DIVERGES_UNFLAGGED` (≥10% **and** no warning — a **FAILURE**), `UNVERIFIED` (source unavailable), `STALE` (divergence attributable to an honestly-old last bar, not a defect — FR-011).
- **Zero `DIVERGES_UNFLAGGED`** required for overall `pass` (SC-004).

### 4. Determinism Statement (REQUIRED) — FR-024/SC-005

Confirmation that the screener side of every verdict is byte-identical across two runs of the same frozen snapshot (only `independent_fetch_at` varies).

### 5. Verdict & Actions (REQUIRED)

- The go/no-go sentence consistent with §2/§3 counts, plus an ordered must-fix list pointing at the file/figure for any FAIL.

---

## Acceptance

The report is **accepted** when: §2 shows 100% seeded detection with no control false positive; §3 shows zero `DIVERGES_UNFLAGGED` and resolves BELFB → `DIVERGES_AND_FLAGGED`, JBHT/CW → `AGREES`; §4 confirms determinism; §1 verdict is consistent with the counts.
