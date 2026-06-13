# Research: App & Strategy Validation

**Feature**: 002-app-strategy-validation | **Date**: 2026-06-12

All decisions below resolve the "how to validate" questions. There were no
open NEEDS CLARIFICATION items in the spec; this document records the method
choices and the rejected alternatives so the validation is reproducible and
auditable.

---

## Decision 1 — Validate against a frozen snapshot, not live data

**Decision**: Pin the current computed snapshot (`backend/data/` — Parquet
price store, `catalog.db`, EDGAR cache, warmed strategy snapshots) by its
`data_as_of` and run the entire validation read-only against it. Live-only
findings (e.g. stale-price tickers from yfinance) are noted separately.

**Rationale**: Determinism (Constitution III, FR-007, SC-005) is impossible to
assert against a moving feed. A frozen snapshot makes the verdict re-runnable
by anyone with the same data and isolates strategy-logic defects from upstream
data drift.

**Alternatives considered**:
- *Live data each run* — rejected: non-reproducible; a failing assertion could
  be yesterday's feed, not a code defect.
- *Synthetic fixtures only* — rejected: would not exercise the real ~591-name
  universe interactions (cross-sectional percentile gates need real peers); kept
  only for the indicator golden-fixture floor that already exists.

---

## Decision 2 — Reuse the existing test stack as the regression floor; add a thin validation layer on top

**Decision**: Run the full existing `backend/tests` (pytest + hypothesis +
schemathesis contract) and `frontend` (Vitest + Playwright) suites as a
pass/fail floor (FR-015). Add only what they don't already cover: a focused
mid-term gate-order/funnel/oracle/modification module and a consolidated
surface sweep.

**Rationale**: 139 tasks already shipped substantial coverage (determinism,
window floor, liquidity gate, disclaimer + no-directive lints, indicator golden
fixtures). Re-building that would violate "reuse over rebuild" and waste effort.
The gaps are: (a) an explicit *declared-gate-order* assertion for mid-term, (b)
a *named-ticker oracle* mapping each reference ticker to the gate it should die
at, (c) a *modification-effect* check, (d) a single *all-surfaces-in-one-pass*
sweep producing report evidence.

**Alternatives considered**:
- *New standalone QA framework* — rejected: spec Assumptions explicitly scope
  this as "structured validation pass, not a new framework."
- *Manual-only clickthrough* — rejected: not reproducible, can't gate on
  determinism, and the operator wants a repeatable verdict.

---

## Decision 3 — Reference-ticker oracle for the mid-term strategy

**Decision**: Use a small hand-classified set as the pass/fail oracle, each
ticker tagged with the gate it is expected to clear or die at, derived from
prior task notes and confirmed on the snapshot:

| Ticker | Expectation | Documented reason (gate) |
|--------|-------------|--------------------------|
| EA, BELFB, ASYS, AMAT, ROST | expected **candidates** | clear all gates on the current snapshot (T192 restored set) |
| WYY | expected **fail** | asset-growth gate (~11.5% YoY growth > bottom-half ceiling) |
| a name >5% below 52-wk high | expected **fail** | proximity gate |
| a name with D/E > 1.5 or FCF ≤ 0 | expected **fail** | quality gate |

The exact tickers are confirmed against the frozen snapshot at run time; if the
snapshot has shifted the candidate set, the report records the then-current set
and the operator re-confirms the oracle (the *method* is fixed, the specific
symbols are snapshot-relative).

**Rationale**: FR-006 / SC-004 require ≥4 hand-classified tickers spanning at
least the proximity, quality, and asset-growth gates. Anchoring to the T192
documented funnel keeps the oracle grounded in observed behavior rather than
invented expectations.

**Alternatives considered**:
- *Reproduce George & Hwang published returns* — rejected (spec Assumption):
  free-data coverage and universe differ from the paper; "as intended" is
  judged against the strategy's own declared rules, not paper returns.
- *Randomly sampled tickers* — rejected: no a-priori expected outcome, so no
  oracle.

---

## Decision 4 — Modification-effect verification by toggle-and-diff

**Decision**: For each declared mid-term modification (Barroso–Santa-Clara
volatility scaling, sector-relative ranking, QMJ-style quality screen), run the
strategy with the modification at its active setting and again neutralized
(e.g. quality ceiling relaxed, sector ranking disabled, vol target widened via
the documented `PARAMETERS` / env knobs such as `SCREENER_MIDTERM_STOP_MODE`)
and assert the output set or ordering changes. A modification that produces
*zero* difference on the snapshot is flagged for inspection (inert/ineffective).

**Rationale**: FR-006a — a modification that is declared but has no observable
effect is a transparency defect (Constitution II): the citation implies an
effect that isn't real.

**Alternatives considered**:
- *Code-read only* — rejected: confirms the code path exists but not that it
  bites on real data.
- *Unit-test each helper in isolation* — already exists
  (`test_quality_helpers.py`); this decision adds the end-to-end "does it move
  the screen" check the unit tests don't give.

---

## Decision 5 — Findings report is the primary deliverable, with a fixed schema

**Decision**: Produce `findings-report.md` in this spec directory, structured
per `contracts/findings-report.schema.md`: a run header (snapshot `data_as_of`,
date, overall verdict), a surface-sweep table, a mid-term strategy section
(declaration, gate funnel, oracle results, modification deltas, determinism), a
backtest section, and a classified findings list (defect / data-tier limitation
/ pass) with counts. Every non-pass carries a one-line justification (FR-013,
SC-007).

**Rationale**: The operator's request is fundamentally "tell me if it works and
why" — the artifact that answers that is a written, classified report, not just
a green test run.

**Alternatives considered**:
- *Just rely on the test runner's exit code* — rejected: doesn't distinguish a
  data-tier limitation from a defect, and gives no narrative verdict.

---

## Decision 6 — Defect vs. data-tier-limitation classification rubric

**Decision**: Classify each non-pass with this rubric:
- **Data-tier limitation (accept)**: caused by the free data tier behaving as
  documented — stale-price tickers (yfinance no-data + lagging static Stooq),
  banks with no FCF, sub-2-year names with no YoY asset growth, the Saudi `.SR`
  asset-growth skip, and the known survivorship gap (no delisted in free
  Stooq). The *gate* behaved correctly.
- **Defect (must-fix)**: the gate, ordering, provenance label, disclaimer,
  directive-language lint, determinism, or backtest window behaved incorrectly
  given the data it had.

**Rationale**: FR-004(US4) and the project's prior task notes (T190, T192)
already separate these; codifying the rubric prevents chasing correct gate
behavior as if it were a bug.

**Alternatives considered**:
- *Treat every dropped ticker as a bug* — rejected: T192 showed several
  "missing" cases are correct gate outcomes (WYY at asset-growth) or inherent
  data gaps (banks/FCF).

---

## Decision 7 — Tiered gates: hard *eligibility* vs soft *scored warnings* (recommended remediation)

**Problem observed during validation.** Every mid-term gate is currently a HARD
filter — a candidate must pass the intersection of all of them. On the live
~591-name compliant snapshot this produced pathologies:
- The full stack collapsed to **0 candidates** (proximity 119 → trend 119 →
  volume 111 → quality 81 → sector 1 → GP 0), and small data changes flip the
  survivor set (T192).
- Valid momentum names are excluded by *enhancement* gates: **WYY** (asset
  growth 11.5%) and **LNTH** (12.5%) die at the asset-growth gate despite
  passing proximity/trend/quality/GP — i.e. they ARE strong 52-week-high
  momentum names, just with a weaker q-theory tilt.
- Behavior is already inconsistent: the quality gate *fails closed* (missing
  data → drop), asset-growth *fails open* (missing → pass), sector *fails open*
  on a small universe — three different policies, no stated principle.

**Decision.** Classify gates into two tiers and treat them differently:

| Tier | Gates | Behavior |
|------|-------|----------|
| **Hard — eligibility / core thesis** (must pass) | liquidity (price ≥ $5, ADV ≥ $1M), **52-week-high proximity (≤5%)**, **trend (close > 200-day SMA)** | exclude on fail — these *define* a tradeable 52-week-high momentum candidate |
| **Soft — quality/return tilts** (pass-with-warning) | quality (D/E, FCF), gross-profitability, **asset-growth**, volume confirmation, sector breadth | failing → a **warning** + a lower composite score/rank, NOT exclusion |

A candidate is *selected* iff it clears the **hard** gates; soft-gate results
become `status: "warn"` (alongside pass/skip) and feed a composite score that
ranks the candidate list. `would_be_selected` keys off hard gates only; every
warning is surfaced (candidate `reason`/`data_notes`, analyze gate panel).

**Rationale.**
- *Factor-investing practice*: multi-factor models use **hard filters only for
  eligibility/tradeability** and combine the rest as a **soft composite rank**
  (normalized percentiles), explicitly to *avoid over-screening* (Stockopedia
  StockRanks; S&P "Merits & Methods of Multi-Factor Investing"; common composite
  designs weight fundamentals/technical/quality and rank, not intersect).
- *52-week-high literature*: the anomaly's **core is proximity + trend/
  momentum**; the quality (QMJ), gross-profitability (Novy-Marx), asset-growth
  (George-Hwang-Li q-theory), and industry-momentum overlays *concentrate /
  risk-adjust* the premium — they raise expected return, they don't make a
  near-high name "not a momentum stock." Encoding return tilts as binary
  disqualifiers is a category error that both over-filters and destabilizes the
  screen.
- *Fixes the observed defects*: WYY/LNTH return as **ranked, warned** candidates
  instead of vanishing; the screen stays populated; data refreshes change
  *warnings/ranks*, not membership (more stable); the rebuilt sector-breadth
  metric becomes a soft tilt instead of a screen-killer.

**Implementation sketch** (one strategy, additive):
- Tag each gate `hard|soft` in the strategy; `evaluate()` returns `pass|fail|
  warn|skipped` (warn = soft gate failed).
- `rules()` filters on hard gates only; computes a composite score from the soft
  gates (e.g. mean of per-soft-gate pass=1/warn=0, or normalized percentile of
  GP/AG/volume) blended with the existing momentum/proximity score; ranks by it.
- Candidate carries `warnings: list[str]`; UI shows a warning chip; the analyze
  panel already renders pass/fail — add the `warn` styling.

**Must re-validate before shipping.** The earlier backtest finding that the
added gates *hurt* (12.33×→5.89× under the buggy metric; and they zeroed the
live screen) was with them as HARD filters. As **soft score tilts** they should
help ranking without over-excluding — but this is a strategy-logic change and
must go through a fresh walk-forward backtest (Constitution IV, test-first) and
the determinism floor before it becomes the default. Keep it systematic and
reproducible — "warn" must be a declared rule, not discretion, and must never
become directive language (Constitution V).

**Alternatives considered.**
- *Keep all gates hard* — rejected: the over-restriction, instability, and
  valid-name exclusions documented above.
- *Make all gates soft (no hard floor)* — rejected: would surface far-from-high
  or illiquid names, breaking the strategy's identity and the liquidity gate
  (FR-034). Eligibility must stay hard.
- *Per-gate fixed weights now* — deferred: start with equal soft weights;
  weight-tuning needs its own backtest and risks overfitting.

### 7a — Reconciliation with the PTH-filter literature (operator-supplied report)

The operator supplied a sourced classification of 52-week-high (PTH) filters into
*hard* (structural) vs *pass-with-warning* (risk/optimization). It tightens the
tiering above and is adopted:

| Report filter | Class | Our mapping |
|---|---|---|
| **Min price ($5)** | HARD | already in the liquidity gate (price ≥ $5) — keep HARD |
| **52-week-high proximity (PTH anchor)** | HARD (it *is* the strategy) | proximity ≤5% — keep HARD |
| **Liquidity / large-cap focus** ("small-cap alpha eaten by costs") | HARD-ish | ADV ≥ $1M gate — keep HARD |
| **One-month lagged window** | HARD (methodology) | our momentum is 12-1 (close[-22]/close[-253]) → already skips the most recent month ✓; backtest uses next-bar entry |
| **Delisting / survivorship** | HARD (methodology) | KNOWN unmet gap — free Stooq has no delisted; documented (Decision 6, Constitution III) |
| **FX exclusion** | HARD | N/A — equities only (US + Saudi) |
| **Confirmed momentum** (operating/earnings momentum, not price alone) | WARN | quality (D/E, FCF) + gross-profitability gates → **soft/warn** |
| **Trend / momentum-crash** (post-bear rebound vulnerability) | WARN | trend (close > 200-SMA) → **soft/warn**; the SPY-below-200 regime gate is the long-only analogue of WML\* neutralization (kept as a separate switch) |
| **"Downward-updating" vs price-spike** (near-high via a recent spike is reversal-prone) | WARN | **NEW** soft warning: flag names within 5% of the high whose proximity is driven by a large recent short-term gain (spike) rather than a stable/declining peak |
| **January seasonality** (tax-loss reversal) | WARN | **NEW** soft warning when the screen as-of month is January |

**Net hard set:** liquidity (price ≥ $5, ADV ≥ $1M) + 52-week-high proximity.
**Net soft/warn set:** trend, confirmed-momentum (quality + gross-profitability),
asset-growth, volume, sector-breadth, **price-spike (downward-update) check**,
**January seasonality**. The asset-growth and sector tilts are project additions
beyond the report but fit the same "return-enhancing, not structural" logic.

Initial implementation ships the existing soft gates as warnings (trend, quality,
GP, asset-growth, volume, sector) + the **price-spike** and **January** warnings;
all subject to the Decision-7 re-backtest before becoming default.

**The report is a hypothesis, not a rule (operator directive).** Its
classification is *consistent* with Decision 7 but is adopted only where it
tests positive on our own snapshot/backtest:
- Implement the tiering behind a **toggle** (hard-all vs tiered-soft) so both are
  backtestable side-by-side; make tiered the default **only if** it is ≥ the
  hard-all baseline (return/hit/drawdown/avg-loss/t-stat) AND keeps the screen
  populated.
- Testable in our data: tiered-vs-hard; "quality limits downside" (already seen:
  GP+asset-growth moved avg loss −15.4%→−11.2%, T148a); price-spike variant.
- **NOT testable on our current free data** (state honestly, don't assume):
  the **January** claim (our backtest rebalances annually at Jan 31, so it can't
  isolate the January-holding effect) and the **momentum-crash** claim (the
  midterm backtest has no 2008–2010 trades due to the point-in-time fundamentals
  gap, so the 2009 rebound isn't exercised). These warnings may still be shown as
  informational, but their *efficacy* is unproven here.

---

## Open items / follow-ups

- None blocking. If the operator later wants paper-return parity (not in
  scope), that becomes a separate research spike requiring a delisted-inclusive
  paid source (Constitution III survivorship).
