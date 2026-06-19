# Contract: Advisor-prompt completeness

Pins the required content of the exported advisor prompt
(`agent/advisor_prompt.py`) so it is self-contained and detailed. Satisfies
FR-006–FR-010, SC-004, SC-005. The builder remains a **pure function** (no
wall-clock in body) → byte-identical re-export for a fixed snapshot.

## Required sections (single-candidate and batch)

A generated prompt MUST contain, for the exported candidate(s):

1. **Strategy declaration** — name, slug, core citation, timeframe, holding
   period, the universe-wide liquidity gate, the gates evaluated, the ranking
   expression, and each modification with its own citation.
2. **Candidate facts** — ticker, name, sector, would-be-selected, current price,
   entry, stop (and tighter alternative if any), take-profit, reward:risk, and
   the ranking + fundamental diagnostics that are present.
3. **Per-material-input freshness** *(new)* — the `data_as_of` of each material
   input the candidate depends on (prices, fundamentals, regime), named
   individually rather than as a single global timestamp (FR-004/FR-007).
4. **Data-integrity warning** — when the candidate is flagged, the warning text
   appears **verbatim and prominently** (FR-008).
5. **Gate-by-gate breakdown** — each gate Pass/Fail/Skipped with its detail; a
   skipped gate is explicitly marked as *not a real pass*.
6. **Market regime** — current regime and the strategy's favorability for it.
7. **Honesty & limitations** — driven by the **real** backtest bias check:
   survivorship verdict (PASS / FAILS-optimistic / UNCONFIRMED), data gaps, data
   notes, data freshness, and the non-advice disclaimer (FR-009).

## Guarantees (tests)

1. **Self-contained** (FR-006, SC-004): the prompt contains no reference to
   app-only context; an external reader needs nothing but the prompt.
2. **Integrity verbatim** (FR-008): for a flagged candidate, the warning string
   appears unchanged in the prompt.
3. **Honesty from real data** (FR-009): a FAILS/UNCONFIRMED survivorship status
   is stated, never omitted; a passing status is stated as such.
4. **Zero directive language** (FR-010, SC-005): with
   `SCREENER_PERSONAL_USE_DIRECTIVE` OFF (default), the prompt contains none of
   "buy", "sell", "recommended", "strong buy" and frames everything as analysis
   inputs. (Directive mode stays flag-gated per constitution Principle V.)
5. **Deterministic** (feature-004 FR-011): byte-identical output for a fixed
   snapshot across repeated exports.
