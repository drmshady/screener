# Quickstart: Sentiment & Narrative in Exported Advisor Prompts (+ Watchlist Export)

Verifies the three surfaces embed captured sentiment, stay deterministic, fall back
byte-identically when absent, and carry no directive language. Assumes the local dev runbook
(`py -3.12`, `npm.cmd`, backend + frontend running) from CLAUDE.md.

## 0. Prerequisites

- Backend running with the feature-014 captured-report store at
  `backend/data/cache/reports.sqlite`.
- At least one screen run and one imported holding.

## 1. Capture sentiment for a few names (prime the store)

```
POST /sentiment/report
{ "selections": [ { "ticker": "AAPL", "origin": "screener" },
                  { "ticker": "NVDA", "origin": "portfolio" } ] }
```

This is the **only** step that may spend budget; the exports below spend nothing.

## 2. US1 — screener-results export embeds sentiment

```
POST /strategies/midterm_52w_high_momentum/advisor-prompt
{ ...screen run request... }
```

Expect: AAPL's candidate block contains a `### External context — sentiment & narrative` section
(label, narrative, narrative-risk when present, dated sources), separated from its gate/level
lines. A candidate with no captured report has a block byte-identical to the pre-feature output.

- **Determinism**: POST twice → the two `prompt` strings are byte-identical.
- **No-directive**: `prompt` contains no "buy/sell/recommended/strong buy".

## 3. US2 — portfolio-report export embeds sentiment

```
POST /portfolio/holdings/advisor-prompt
{ "strategy_slug": "midterm_52w_high_momentum" }
```

Expect: NVDA's holding block carries the same embedded sentiment section, separated from its
cost-basis/level/risk lines; holdings without a captured report are unchanged.

## 4. US3 — new watchlist export (same format)

```
POST /portfolio/watchlist/advisor-prompt
{ "strategy_slug": "midterm_52w_high_momentum", "tickers": ["AAPL", "NVDA"] }
```

Expect: one prompt — strategy declaration once, a per-name computed block for each watched name
with its embedded sentiment when captured, and one shared honesty footer. Re-POST → byte-identical.

Empty watchlist:

```
POST /portfolio/watchlist/advisor-prompt
{ "strategy_slug": "midterm_52w_high_momentum", "tickers": [] }
```

Expect: a clear "no watched names" prompt state (`watched_count: 0`), never an empty/malformed
prompt.

Frontend: the Watchlist page shows a **Copy watchlist advisor prompt** button that returns the
same text.

## 5. Cost & determinism guarantees

- Run the three exports repeatedly and confirm `period_spend_usd` (from `POST /sentiment/report`,
  step 1) does **not** advance — exports trigger 0 paid calls (FR-009/SC-006).
- Diff two exports of each prompt on an unchanged snapshot → empty diff (FR-007/SC-003).

## 6. Automated checks

- Backend: `py -3.12 -m pytest backend/tests/agent backend/tests/sentiment backend/tests/api`
  — renderer fixtures, store `latest_for_ticker` + migration, enriched screen/portfolio exports,
  new watchlist export, byte-identical-absent, and determinism.
- Frontend: Playwright no-directive copy lint over all three exported prompts + the watchlist
  export flow.

## Expected outcomes (map to Success Criteria)

| Check | SC |
|-------|----|
| N captured candidates all embed a section | SC-001 |
| M captured holdings all embed a section | SC-002 |
| Re-export byte-identical | SC-003 |
| Absent names byte-identical to baseline | SC-004 |
| 0 directive terms; every claim has a dated source | SC-005 |
| 0 new paid calls; within $5/mo cap | SC-006 |
| Watchlist export works; empty → clear state | SC-007 |
| No strategy/indicator/backtest change | SC-008 |
