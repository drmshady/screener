# Contract: Watchlist Advisor Prompt Export (new) + enriched-export deltas

Owner-secret gated on all routes (hosted mode). Every response carries `data_as_of` +
`disclaimer`. No route triggers fresh sentiment generation.

## NEW — `POST /portfolio/watchlist/advisor-prompt`

Assemble one copy-ready advisor prompt over the owner's watched names, in the **same format** as
the screener-results export, with each name's **captured** sentiment section embedded when present.

### Request

```json
{
  "strategy_slug": "midterm_52w_high_momentum",
  "tickers": ["AAPL", "NVDA", "MSFT"],
  "as_of": null
}
```

- `strategy_slug` (required): active strategy; unsupported slug → `422`.
- `tickers` (required): watched names. **Empty array is valid** and yields a "no watched names"
  prompt state (FR-013), not an error.
- `as_of` (optional): snapshot date; omitted ⇒ current snapshot.

### Response `200`

```json
{
  "strategy": "midterm_52w_high_momentum",
  "watched_count": 3,
  "personal_use_directive": false,
  "prompt": "You are ... \n\n## Strategy ... \n\n### AAPL — ... \n### External context — sentiment & narrative ... \n\n## Honesty & limitations ...",
  "data_as_of": "2026-07-02",
  "disclaimer": "For informational purposes only; not investment advice."
}
```

- `watched_count`: number of names rendered.
- `prompt`: strategy declaration once → per-name computed block (with embedded sentiment when a
  captured report exists) → shared honesty footer once.
- `personal_use_directive`: forced `false` in hosted mode.

### Behavior

- **Empty watchlist** (`tickers: []`) → `200` with a clear "no watched names" prompt body
  (FR-013); `watched_count: 0`.
- **Unresolvable ticker** on the snapshot → the name still appears with available facts and an
  explicit "not priceable / no coverage" note (matches today's single-candidate behavior); its
  sentiment section is included only if a captured report exists.
- **Determinism** → identical request + unchanged snapshot + unchanged captured sentiment ⇒
  byte-identical `prompt` (FR-007/FR-014).
- **No directive language** anywhere in `prompt` (FR-006), enforced by the copy lint.

### Errors

| Status | Condition |
|--------|-----------|
| `401/403` | Missing/invalid owner secret (hosted). |
| `422` | Unknown/unsupported `strategy_slug`. |

## ENRICHED — `POST /strategies/{slug}/advisor-prompt` (screener-results export)

Additive: each candidate block for which a **captured** `SentimentReport` exists (resolved via
`CapturedReportStore.latest_for_ticker`) gains an embedded `### External context — sentiment &
narrative ...` section (label, narrative, narrative-risk when present, dated sources), clearly
separated from the gate/level lines. Response shape is **unchanged** (`ScreenAdvisorPromptResponse`).

- Candidates with no captured report → block **byte-identical** to today (FR-008).
- Export reads the store only; triggers **no** new paid generation (FR-009).
- Re-export on unchanged snapshot + captured sentiment ⇒ byte-identical (FR-007).

## ENRICHED — `POST /portfolio/holdings/advisor-prompt` (portfolio-report export)

Additive: each holding block for which a captured `SentimentReport` exists gains the same
embedded sentiment section, separated from its cost-basis/level/risk lines. Response shape is
**unchanged** (`PortfolioAdvisorPromptResponse`). Same absent-fallback, no-generation, and
determinism guarantees as above.

## Cross-cutting invariants (all three)

- Sentiment is **external context**; the task instruction states it MUST NOT overwrite any
  computed gate, rank, level, or size (FR-004/FR-005).
- No strategy rule, default, citation, indicator, gate threshold, or backtest baseline changes
  (FR-017).
- `data_as_of` + `disclaimer` on every response (FR-015); hosted-mode owner-only + forced
  directive-OFF (FR-016).
