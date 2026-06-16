# Contract: Data-Integrity Warning (wire shape)

**Feature**: 008-momentum-data-integrity

The machine-readable per-candidate warning surfaced in the API, UI, and advisor export (FR-017/FR-019). Additive to `Candidate`; distinct from the existing soft-gate `warnings: string[]`.

## Candidate additions (JSON)

```jsonc
{
  // ...existing Candidate fields unchanged...
  "warnings": ["Volume confirmation"],          // existing soft-gate warnings (unchanged)
  "data_suspect": true,                          // NEW — drives demotion + UI badge
  "data_integrity_warnings": [                    // NEW — candidate-severity contract violations
    {
      "figure": "close",
      "rule": "series.seam_consistent",
      "reason": "price may be stale or erroneous — the 1-year history stitches two sources with inconsistent split/dividend adjustment; verify before acting"
    }
  ]
}
```

## Field rules

- `data_suspect` = `true` iff `data_integrity_warnings` is non-empty.
- `reason` is operator-facing, specific (names the figure), actionable, and ends with the verify-before-acting intent. It is included **verbatim** in the advisor prompt's candidate block and honesty footer (FR-019).
- Both fields are optional with defaults (`false` / `[]`) so existing API clients and the OpenAPI contract remain backward-compatible.

## Frontend rendering (FR-017/FR-020)

- `CandidateRow` renders a **distinct, prominent** data-integrity badge (visually stronger than the amber soft-gate badge) when `data_suspect` is true, with the reasons in its title/expansion.
- The same row surfaces `return_12_1` **with its sign** so a near-high-but-falling name (IOSP, −9.8%) is identifiable at a glance (US5/FR-020/SC-011). This is rank-only transparency; no gate is added (FR-021).
- No directive language is introduced (Playwright lint stays green).

## Ordering (FR-018)

A `data_suspect` candidate is ranked **below all clean candidates** regardless of raw score, via the screen sort key `["data_suspect", "warning_count", "score", "ticker"]`. Within the flagged group, existing score order is preserved.
