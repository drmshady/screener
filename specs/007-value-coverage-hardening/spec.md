# Feature Specification: Value Strategy — Data Coverage & Correctness Hardening

**Feature Branch**: `007-value-coverage-hardening`
**Created**: 2026-06-14
**Status**: Draft
**Input**: User operation of the live `midterm_value_composite` screen (feature
005) surfaced (a) large data-completeness gaps and false "halted/suspended"
exclusions, and (b) several strategy-correctness and disclosure defects in the
candidate output. This feature hardens the value strategy's data pipeline and
selection/level logic so the live screen is trustworthy.

## Background

Feature 005 shipped `midterm_value_composite` enabled-by-default. Driving it on
the live US universe exposed two independent classes of problem, both verified
against the code and cache:

1. **Data coverage.** 530 of 4,242 EDGAR cache files are 82-byte *failed-fetch
   stubs* (`{"facts":{"us-gaap":{}},"sic":null,"fetch_failed":true,
   "schema_version":2}`) — empty facts, null sector, predating the v3 value/`dei`
   capture. On a single live run this produced: 13/592 names with no fundamentals
   at all, 42/592 missing value inputs, and 115 names dropped for "no value
   yield." Separately, the price-staleness gate branded six actively-trading names
   (AMWD, APLS, CTLP, CTRA, EXAS, HOLX) "halted/suspended" when only CTLP is a
   genuine delisting — the rest are stale *local* bars the warm store never
   refreshed.

2. **Strategy correctness & disclosure.** A loss-making name (OIS, negative
   earnings yield) passed at composite 0.68 because the composite *averages* four
   percentile ranks and dilutes one bad metric. OIS also printed a degenerate
   stop ($0.11 below entry → inflated "3.82R") because the 200-day-SMA stop is
   used whenever it sits just below entry, with no minimum-risk floor. The
   per-candidate breakdown omits the cheapness-cut as a distinct gate, never
   flags sub-9 F-Score evaluable counts as low-confidence, hides the
   within-sector grouping/cap, and under-states a regime-unavailable run.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A value screen backed by complete, current data (Priority: P1)

As the single screener user, when I run the value strategy I get a universe whose
fundamentals are actually populated — names are excluded only when they are
*genuinely* ineligible (not US-GAAP filers, truly delisted), not because a prior
fetch failed and cached an empty stub or because my local price feed lagged.

**Why this priority**: The strategy's ranking is only as honest as its inputs.
With ~19% of the screened universe dropped for missing value yields and healthy
names mislabeled "halted," the candidate list is not trustworthy. Fixing
coverage is the foundation everything else rests on.

**Independent Test**: Re-fetch the failed-stub filers and re-run the live screen;
confirm the "no value yield" and "fundamentals missing" counts fall toward the
irreducible floor (genuinely-foreign / no-US-GAAP names), and that AMWD/CTRA/
EXAS/HOLX return as live candidates while only true delistings stay excluded.

**Acceptance Scenarios**:

1. **Given** the EDGAR cache contains failed-fetch stubs for real US filers,
   **When** the coverage-refresh runs, **Then** those names are re-fetched into
   complete schema-v3 payloads (with `dei` shares + value tags) and the screen
   can compute their value yields and F-Score.
2. **Given** instruments that are not US-GAAP common equity (preferred shares,
   ADRs, closed-end funds, ETFs), **When** the value universe is assembled,
   **Then** they are excluded *before* the gates and reported on a separate,
   quiet "out of value scope" line — not counted as a data defect.
3. **Given** a liquid name whose only problem is a stale *local* price bar while
   peers are fresh, **When** the screen runs, **Then** it is reported as "stale
   local data — run ingest" (and ideally refreshed), distinct from a genuine
   halt/delisting, and is not silently dropped as "halted/suspended."

---

### User Story 2 — Correct selection and level math (Priority: P1)

As the user, the value screen must not rank loss-making names as cheap, must not
print degenerate risk/reward, and must apply its declared gates in a way I can
verify.

**Why this priority**: A value strategy that ranks a loss-maker as "cheap" and
shows a stop $0.11 below entry as a 4R trade is actively misleading — it defeats
the strategy's own value-trap thesis. Equal P1 with coverage.

**Independent Test**: On the reference snapshot, confirm (a) no candidate has a
negative earnings yield while failing the new profitability gate, (b) no
candidate has a stop closer than the minimum-risk floor to entry, and (c) the
falling-knife guard (12-1 momentum ≥ −0.20) is applied by default.

**Acceptance Scenarios**:

1. **Given** a name with negative trailing earnings (CFO ≤ 0 or ROA ≤ 0),
   **When** the value strategy runs in hard mode, **Then** it fails a
   **profitability gate** (Piotroski's CFO>0 and ROA>0 signals) and is excluded,
   with the exclusion recorded — regardless of how its composite averages out.
2. **Given** a candidate whose 200-day-SMA stop would sit within ~1×ATR of entry,
   **When** levels are derived, **Then** the stop falls back to the 3-ATR
   disaster stop so the risk distance — and therefore the R-multiple target — is
   not degenerate.
3. **Given** the default configuration, **When** the screen runs, **Then** names
   whose 12-1 month momentum is below −0.20 are excluded as falling knives
   (override via the existing toggle / `SCREENER_VALUE_MIN_MOMENTUM`), and names
   with unknown momentum pass through (fail-open).

---

### User Story 3 — Honest, verifiable disclosure per candidate (Priority: P2)

As the user, every declared gate, every low-confidence input, and every
regime-blind run is surfaced loudly enough that I can judge the call myself.

**Why this priority**: The constitution's transparency/honesty principles require
it, and the gaps (hidden cheapness cut, un-flagged partial F-Scores, invisible
sector cap, quiet regime-unavailable) directly caused the user's loss of trust in
the output. Depends on Stories 1–2 producing correct data/levels first.

**Independent Test**: Inspect a returned candidate and confirm the cheapness cut
shows as its own PASS/FAIL line, a sub-9 F-Score evaluable count renders a
low-confidence flag, the within-sector grouping and per-sector cap are visible
(including dropped names), and a regime-unavailable run shows a prominent banner.

**Acceptance Scenarios**:

1. **Given** the cheapness cut (`composite_top_percentile`), **When** a candidate
   is shown, **Then** it appears as a distinct declared gate with its own
   pass/fail line (not silently folded into "Value composite").
2. **Given** a candidate whose F-Score was computed from fewer than 9 evaluable
   signals, **When** it is shown, **Then** a low-confidence flag states how many
   signals were evaluable.
3. **Given** a completed screen, **When** the user views results, **Then** the
   within-sector grouping and the per-sector cap are shown — including which names
   were dropped by the cap — so the cap can be verified.
4. **Given** a run where market regime could not be determined, **When** results
   are shown, **Then** a prominent banner states the run is regime-blind and the
   strategy's regime master-switch could not be applied.
5. **Given** a candidate with negative trailing FCF or extreme/outlier yields
   (transitory-earnings bulge), **When** it is shown, **Then** a data-quality
   flag marks it (without necessarily gating it).

---

### Edge Cases

- **Foreign filers / non-US-GAAP instruments**: have no companyfacts by nature;
  excluded from the value universe up front and reported as out-of-scope, never
  re-fetched in a loop or counted as a defect.
- **Re-fetch failure**: a name whose CIK resolves but whose SEC fetch still fails
  (rate-limit, 404) keeps its prior state and is recorded; the refresh is
  idempotent and resumable, never writing a worse stub over a good payload.
- **Globally stale price store**: if *every* name's last bar is old (the whole
  store is behind), report one store-level staleness warning rather than
  branding the entire universe "halted."
- **Profitability gate with missing inputs**: a name lacking CFO/ROA inputs has
  the profitability gate recorded as *skipped* (and excluded in hard mode like
  the other health gates), never silently passed.
- **Minimum-risk floor vs. legitimate tight stop**: the ATR fallback triggers
  only on degenerate (sub-floor) SMA stops; a genuinely valid SMA stop beyond the
  floor is preserved.

## Requirements *(mandatory)*

### Functional Requirements

**Data coverage**

- **FR-001**: The system MUST provide an idempotent, resumable refresh that
  re-fetches SEC companyfacts for EDGAR cache entries that are failed-fetch stubs
  or pre-v3 partial payloads **and** resolve to a valid CIK, writing complete
  schema-v3 payloads (including `dei:EntityCommonStockSharesOutstanding` and the
  value `NEEDED_TAGS`). It MUST use only a User-Agent header (no API key) and MUST
  NOT overwrite a good payload with a worse one.
- **FR-002**: The refresh MUST classify every screened-universe name into
  {complete, partial, fixable-stub, non-equity-stub, not-cached} and emit the
  before/after counts, so coverage improvement is measured, not assumed.
- **FR-003**: The value universe MUST exclude instruments that are not US-GAAP
  common equity (preferred classes, ADRs without US filings, closed-end funds,
  ETFs) *before* the value gates run, and report them on a separate "out of value
  scope" line rather than as missing-data defects.
- **FR-004**: The price-staleness gate MUST distinguish a name that is stale only
  in the *local* feed (peers fresh, still in the active universe) — reported as
  "stale local data, refresh" — from a genuinely halted/delisted name. The daily
  ingest MUST cover the full screened universe and retry tickers it failed.

**Strategy correctness**

- **FR-005**: The value strategy MUST apply a **profitability gate** using
  Piotroski's profitability signals (operating cash flow > 0 **and** return on
  assets > 0) as a hard gate, excluding loss-making names regardless of composite
  rank, and record per candidate whether it passed, failed, or was skipped for
  missing inputs.
- **FR-006**: Level derivation MUST enforce a **minimum-risk floor**: when the
  200-day-SMA stop would sit within approximately one ATR of entry, the stop
  falls back to the 3-ATR disaster stop, so the derived risk distance and
  R-multiple target are never degenerate. This applies identically in the batch
  (`rules`) and single-name (`derive_levels`) paths.
- **FR-007**: The falling-knife guard MUST default ON at a 12-1 momentum floor of
  **−0.20**, overridable per-run via the existing UI toggle and
  `SCREENER_VALUE_MIN_MOMENTUM`; names with unknown momentum pass through.

**Disclosure**

- **FR-008**: The cheapness cut (`composite_top_percentile`) MUST appear in the
  per-candidate gate breakdown as a distinct declared gate with its own
  pass/fail status, separate from the value-composite ranking line.
- **FR-009**: A candidate whose F-Score was computed from fewer than 9 evaluable
  signals MUST carry a visible low-confidence flag stating the evaluable count.
- **FR-010**: The screen result MUST expose the within-sector grouping and the
  per-sector cap, including names dropped by the cap, so the cap is verifiable.
- **FR-011**: A run in which market regime could not be determined MUST surface a
  prominent regime-blind banner (not only a data note), because regime is the
  strategy's declared master switch.
- **FR-012**: Candidates with negative trailing FCF or extreme/outlier yields
  (likely transitory-earnings bulge) MUST carry a data-quality flag.
- **FR-013**: All new copy MUST pass the directive-language lint; every new
  user-visible response MUST continue to carry `data_as_of` and `disclaimer`.

**Regression discipline**

- **FR-014**: Every strategy-logic change (FR-005, FR-006, FR-007) MUST be
  covered by a test written before the change (golden-fixture / rules-level),
  consistent with the test-first principle for financial logic.
- **FR-015**: After the coverage refresh, the slim cache MUST be rebuilt (schema
  v3) and the value backtest regenerated so the backtest universe matches live;
  a guard test MUST assert the screened value universe keeps at least a defined
  minimum value-metric coverage on a fixture.

### Key Entities *(include if feature involves data)*

- **EDGAR cache entry classification**: per-ticker state (complete / partial /
  fixable-stub / non-equity-stub / not-cached) plus resolved CIK and instrument
  type, driving the refresh and the out-of-scope filter.
- **Coverage report**: before/after counts of each classification over the
  screened universe — the measurable artifact proving the fix worked.
- **Profitability gate result**: per-candidate CFO>0 / ROA>0 evaluation
  (pass/fail/skip) added to the existing gate breakdown.
- **Level-derivation inputs**: entry, ATR, SMA-200, the minimum-risk floor, and
  the chosen stop with the reason it was chosen (SMA vs. ATR fallback).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After the refresh, the live value screen's "no value yield" count
  on the reference universe drops from 115 to the irreducible floor (only
  genuinely non-US-GAAP / not-cached names), with the residual fully explained by
  classification.
- **SC-002**: The six names previously flagged "halted/suspended" resolve
  correctly — actively-trading names (AMWD, CTRA, EXAS, HOLX, APLS) become
  eligible; only genuine delistings (CTLP) remain excluded, labeled as such.
- **SC-003**: Zero candidates with negative earnings yield (CFO≤0 or ROA≤0) pass
  the hard-mode screen; the OIS profile is excluded by the profitability gate.
- **SC-004**: Zero candidates have a stop closer to entry than the minimum-risk
  floor; the displayed R-multiple equals the level math for 100% of candidates.
- **SC-005**: With defaults, 100% of candidates have 12-1 momentum ≥ −0.20 or
  unknown momentum (no falling knives below the floor).
- **SC-006**: 100% of candidates show the cheapness cut as a distinct gate, and
  100% with sub-9 F-Score evaluability carry the low-confidence flag.
- **SC-007**: A regime-unavailable run shows the regime-blind banner on 100% of
  such runs; the within-sector cap is visible and verifiable on every screen.
- **SC-008**: Directive-language lint passes on 100% of new surfaces; the
  regenerated value backtest still carries its honest (failing) survivorship
  verdict — coverage work does not hide it.

## Assumptions

- The dominant coverage fix is re-fetching real US filers whose cache entry is a
  failed stub; a meaningful share of the 530 stubs are legitimately non-US-GAAP
  instruments that should be filtered, not fetched.
- SEC companyfacts remains the free, personal-use point-in-time source; refresh
  respects SEC rate limits with backoff and writes nothing secret to disk.
- The momentum, ATR-breakout, and Minervini strategies are unaffected; changes
  are scoped to the value strategy, its inputs, and shared disclosure surfaces
  used by the value screen.
- Personal-use, single-user, single-machine scope continues; survivorship bias
  stays honestly surfaced (the backtest verdict still FAILS on free Stooq).

## Dependencies

- Feature 005 (`midterm_value_composite`) — the strategy, indicators, and EDGAR
  `value_metrics_as_of` this feature hardens.
- `FundamentalsLoader` / EDGAR cache builder and the slim-cache schema version.
- The price warm store and `scripts/ingest_daily.py` (price staleness, FR-004).
- The constitution's Data Integrity (I), Strategy Transparency (II), Reproducible
  Backtesting (III), and Test-First (IV) principles.

## Decisions Record

Resolved with the operator on 2026-06-14:

- **Loss-makers** → **Add a profitability gate** (Piotroski CFO>0 and ROA>0 as a
  hard gate). [FR-005]
- **Degenerate stop** → **Minimum-risk ATR fallback** (SMA stop within ~1×ATR of
  entry falls back to 3-ATR). [FR-006]
- **Falling-knife guard default** → **ON at −0.20** (per-run overridable). [FR-007]
- **Sequencing** → **Spec doc first, then build** (this document).
