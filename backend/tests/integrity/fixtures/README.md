# Integrity harness test fixtures

Harness-only fixtures for the strategy defect-detection suite (feature
`008-momentum-data-integrity`).

## Canonical input

The **2026-06-12 frozen universe snapshot** is the canonical input for both the
seeded-defect regression suite and the independent cross-check. All seeded
faults are injected into a copy of this snapshot; the un-corrupted control copy
must raise zero data-integrity warnings.

- Seeded-defect suite (`tests/integrity/test_seeded_defects.py`) — the blocking
  CI gate (quickstart §1): inject each defect class into a snapshot copy, run the
  contract, assert the expected invariant family fires (SC-001 = 100% detection)
  and the control copy stays clean (SC-002).
- Independent cross-check (`scripts/run_integrity_harness.py --as-of 2026-06-12`,
  quickstart §4) — on demand, non-blocking: compares top-N candidate
  prices / 52-week highs against a free-tier independent vendor.

## Determinism

The screener side of every result is deterministic on the frozen snapshot — a
re-run yields an identical figure set and warning set. Only the harness's
`independent_fetch_at` timestamp varies between runs (the live independent fetch
is confined to the offline harness; the live screen is no-network).

Fixtures here are checked in and must not depend on network access.
