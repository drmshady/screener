# Feature Specification: Mid-Term Strategy Bake-Off (Comparison & Ranking)

**Feature Branch**: `003-strategy-comparison`
**Created**: 2026-06-13
**Status**: Draft
**Input**: User description: "we have back data of US market and now we use 52[-week] high momentum strategy[;] i want to test other strategies against this plan to see which is better"

## Overview

The screener ships with a single mid-term default strategy —
`midterm_52w_high_momentum` ("Mid-Term 52-Week High Momentum", George & Hwang
2004). Deep US back data now exists (Stooq history covering 2008–2009), and the
baseline strategy has been validated end-to-end by feature 002. The operator now
wants to answer a comparative question: **is the 52-week-high momentum strategy
actually the best mid-term choice, or would another peer-reviewed mid-term
strategy hold up better — especially through drawdowns?**

This feature is a **head-to-head bake-off harness**. It runs the incumbent
baseline against one or more mid-term *challenger* strategies over the **same
frozen back-data snapshot, same window, same universe, same liquidity gate, and
same cost model**, so the only thing that differs is each strategy's own
declared rules and its native rebalance cadence. It scores every entrant on a
common scorecard, reports both **gross (pre-cost signal)** and **net
(after-cost portfolio)** results, gives first-class weight to the **2008–2009
stress window**, and produces a single reproducible ranking that names the
winner under a **drawdown-resilient criterion** (primary: Calmar = CAGR ÷ max
drawdown; tiebreak: lower max drawdown).

Because the baseline is presently the *only* registered mid-term strategy, a
meaningful bake-off requires at least one new peer-reviewed mid-term challenger
to be registered (subject to the same declaration/citation gating every strategy
must pass). The harness is built so additional challengers can be dropped in and
ranked later without changing the comparison engine.

This feature deliberately scopes to **mid-term-class strategies only**. The two
short-term strategies (`shortterm_minervini_vcp`, `shortterm_atr_breakout`)
trade on a different timeframe and are excluded from this ranking; comparing them
here would be apples-to-oranges. "Better" means **historically more
drawdown-resilient on this back data under the chosen criterion** — it is a
backtest result, never trading advice.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run the bake-off and get a drawdown-resilient ranking (Priority: P1)

As the operator, I run one comparison over the frozen back data that pits the
52-week-high momentum baseline against the registered mid-term challenger(s), on
an identical window/universe/liquidity-gate/cost basis, and I get back a single
ranked verdict — ordered by drawdown resilience (Calmar, then lowest max
drawdown) — plus the full scorecard for every entrant, so I can see which
mid-term strategy held up best on US data.

**Why this priority**: This is the whole point of the feature — the comparative
verdict. Without it there is no answer to "which is better". It is the smallest
slice that delivers value: a defensible, reproducible head-to-head ranking.

**Independent Test**: Enable the baseline plus at least one mid-term challenger,
run the bake-off against the frozen snapshot, and confirm it returns one ranked
table ordered by the drawdown-resilient criterion with each entrant's full
scorecard — without errors and without re-running each strategy by hand.

**Acceptance Scenarios**:

1. **Given** the baseline plus ≥1 enabled mid-term challenger, **When** the
   bake-off is run on the frozen back-data snapshot, **Then** it returns a single
   ranking ordered by Calmar (CAGR ÷ max drawdown), with lower max drawdown as
   the tiebreaker, and the winner under that criterion is explicitly named.
2. **Given** the bake-off result, **When** the scorecard is inspected, **Then**
   every entrant reports at minimum Calmar, max drawdown, CAGR, Sharpe, Sortino,
   hit rate, annualized turnover, average exposure, and a 2008–2009 stress-window
   return — for the same window and universe.
3. **Given** all entrants, **When** their comparison basis is inspected, **Then**
   the window (≥15 years including 2008–2009), starting universe, universe-wide
   liquidity gate, capital base, and cost model are identical across strategies,
   and any unavoidable asymmetry is disclosed rather than hidden.
4. **Given** two entrants with effectively equal Calmar, **When** the ranking is
   produced, **Then** the lower-max-drawdown strategy ranks higher; if still
   tied, the tie is reported explicitly rather than broken arbitrarily.

---

### User Story 2 - Add a mid-term challenger and have it auto-ranked (Priority: P1)

As the operator, I register a new peer-reviewed mid-term strategy as a challenger
and it is automatically included in the next bake-off ranking — provided it
passes the same declaration and citation gating every strategy must satisfy —
without me editing the comparison engine.

**Why this priority**: With only the baseline registered today, the bake-off has
nothing to compare against. Being able to add at least one compliant mid-term
challenger is therefore part of the P1 MVP, not a later nicety — a ranking of one
strategy is not a comparison.

**Independent Test**: Register a compliant mid-term challenger, run the bake-off,
and confirm it appears in the ranking and scorecard; then register a deliberately
incomplete strategy and confirm it is refused entry with a clear reason.

**Acceptance Scenarios**:

1. **Given** a new mid-term strategy declaring all required fields (NAME,
   CITATION, TIMEFRAME = mid-term, PARAMETERS, REGIME_FAVORABILITY, MODIFICATIONS
   each with its own citation, and a pure `rules()` callable), **When** it is
   enabled, **Then** it appears as an entrant in the next bake-off ranking with no
   change to the comparison harness.
2. **Given** a strategy missing any required declaration field or carrying a
   non-mid-term timeframe, **When** entry is attempted, **Then** it is refused
   from the bake-off with an explicit reason, and the ranking proceeds with the
   compliant entrants.
3. **Given** the comparison is scoped to mid-term-class strategies, **When** a
   short-term strategy is present in the registry, **Then** it is excluded from
   the ranking and shown as out-of-scope rather than silently mixed in.

---

### User Story 3 - See gross-vs-net so cost drag is visible (Priority: P2)

As the operator, I view each strategy's **gross** (raw signal, no trading costs)
and **net** (after transaction costs and slippage, at the strategy's native
rebalance cadence) results side by side, so a high-turnover strategy that looks
great on paper but bleeds out in costs cannot win on a flattering gross number
alone.

**Why this priority**: Net-of-cost realism is what makes the verdict decision-
grade, and turnover differs sharply across mid-term strategies. It sits just
behind producing the ranking itself.

**Independent Test**: For each entrant, confirm both gross and net metrics are
present and that the cost drag (gross minus net) is shown; confirm the ranking
uses the **net** figures.

**Acceptance Scenarios**:

1. **Given** any entrant, **When** its result is viewed, **Then** both gross and
   net versions of the return/drawdown metrics are reported, along with the
   explicit cost drag (gross − net) and annualized turnover.
2. **Given** a high-turnover entrant that leads on gross return, **When** costs
   are applied, **Then** its net ranking reflects the cost drag, and the ranking
   verdict is computed from net (after-cost) figures.
3. **Given** the shared cost/slippage model, **When** the bake-off runs, **Then**
   the same cost assumptions are applied to every entrant and those assumptions
   are stated in the output.

---

### User Story 4 - Trust the comparison: reproducible, stress-aware, honest (Priority: P2)

As the operator, I need the comparison to be reproducible (same data + same
entrants → identical ranking), to foreground how each strategy behaved through
the 2008–2009 crash, and to keep the free-data survivorship-bias caveat visible
and applied equally to all entrants — so the verdict is a fair relative
comparison rather than a number I have to take on faith.

**Why this priority**: A non-reproducible or bias-blind ranking is worse than
none. It is P2 only because it rides on top of the P1 ranking existing first.

**Independent Test**: Run the bake-off twice on the same snapshot and confirm
identical ranking and metrics; confirm a 2008–2009 stress block is present per
entrant; confirm the survivorship caveat is shown and noted as applying to all.

**Acceptance Scenarios**:

1. **Given** the same frozen snapshot and the same set of entrants, **When** the
   bake-off is run twice, **Then** the ranking, every metric, and the report are
   identical (no hidden randomness).
2. **Given** the bake-off, **When** results are viewed, **Then** each entrant's
   2008–2009 drawdown, return, and recovery are reported as a first-class
   comparison dimension.
3. **Given** the free-data back-data tier, **When** the verdict is presented,
   **Then** the survivorship-bias caveat (the free Stooq bundle's delisted-ticker
   gap) is shown, noted as applying symmetrically to all entrants, and the verdict
   is framed as a *relative* comparison under that shared limitation.

---

### User Story 5 - Read a head-to-head comparison report (Priority: P3)

As the operator, I get a single written/visual head-to-head report that states
the ranking, names the winner under the drawdown-resilient criterion, shows the
full scorecard, the gross-vs-net breakdown, and the 2008–2009 stress block — with
the standing disclaimer and `data_as_of` — so I can review the comparison in one
artifact and revisit it later.

**Why this priority**: The report packages the verdict for review and future
reference; valuable, but only after the ranking, challenger support, and
gross/net transparency exist.

**Independent Test**: Run the bake-off and confirm a single report artifact is
produced containing the ranking, scorecard, gross/net, stress block, disclaimer,
and `data_as_of`.

**Acceptance Scenarios**:

1. **Given** a completed bake-off, **When** the report is generated, **Then** it
   contains the ranked verdict, the named winner, the full per-entrant scorecard,
   the gross-vs-net breakdown, and the 2008–2009 stress block.
2. **Given** the report, **When** it is viewed, **Then** the `data_as_of` date and
   the standing disclaimer are present, and no directive trading language ("Buy",
   "Sell", "Recommended", "best strategy to buy", or equivalents) appears — the
   winner is framed strictly as backtest performance under the stated criterion.

---

### Edge Cases

- **Only the baseline enabled (no challenger):** the bake-off MUST surface an
  explicit "need at least one challenger" state and MUST NOT declare the baseline
  the winner by default — a field of one is not a comparison.
- **Challenger with shorter usable history than the window:** restrict the
  comparison to the common overlapping window (or mark the entrant incomplete),
  and disclose the restriction; never silently back-fill or compare across
  mismatched windows.
- **Strategy that holds cash / de-risks in 2008 vs one fully invested:** exposure
  differences MUST be visible (via the exposure metric) so a low-return,
  low-exposure strategy isn't unfairly judged against a fully-invested one.
- **Wins gross, loses net:** a high-turnover entrant that leads on gross return
  but trails on net MUST be ranked on net, with the cost drag shown.
- **Different native rebalance cadences:** turnover MUST be normalized/annualized
  so it is comparable across strategies with different rebalance frequencies.
- **Near-tie on the primary criterion:** apply the max-drawdown tiebreak; if still
  tied within tolerance, report the tie explicitly.
- **A gate lacking point-in-time data for some entrant over part of the window:**
  disclose and handle consistently across entrants; do not silently treat missing
  data as a pass for one strategy and a fail for another.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST produce a single bake-off run that compares the
  baseline `midterm_52w_high_momentum` against all enabled mid-term challenger
  strategies over one frozen back-data snapshot and returns one ranking.
- **FR-002**: The ranking MUST be ordered by a **drawdown-resilient criterion**:
  primary metric Calmar (CAGR ÷ max drawdown), tiebreak the lower max drawdown;
  the winner under this criterion MUST be explicitly named, and remaining ties
  reported rather than broken arbitrarily.
- **FR-003**: The comparison MUST be apples-to-apples: identical backtest window
  (≥15 years including 2008–2009), identical starting universe, identical
  universe-wide liquidity gate, identical capital base/sizing rules, and identical
  transaction-cost & slippage model across all entrants — only each strategy's own
  declared rules and native rebalance cadence may differ. Any unavoidable
  asymmetry MUST be disclosed in the output.
- **FR-004**: The bake-off MUST be scoped to **mid-term-class strategies only**;
  short-term strategies MUST be excluded from the ranking and shown as
  out-of-scope rather than silently mixed in.
- **FR-005**: For every entrant the system MUST report **both gross** (pre-cost
  signal) **and net** (after-cost portfolio) results, and MUST show each entrant's
  cost drag (gross − net) and annualized turnover. The ranking verdict MUST be
  computed from the **net** figures.
- **FR-006**: The per-entrant scorecard MUST include at minimum: Calmar, max
  drawdown, CAGR, Sharpe, Sortino, hit rate, annualized turnover, average
  exposure, and a 2008–2009 stress-window return.
- **FR-007**: The 2008–2009 stress window MUST be reported as a first-class
  comparison dimension per entrant (drawdown, return, and recovery across that
  window).
- **FR-008**: A new strategy MUST satisfy the registry's declaration gating —
  NAME, CITATION, TIMEFRAME = mid-term, PARAMETERS, REGIME_FAVORABILITY,
  MODIFICATIONS (each with its own citation), and a pure `rules()` callable —
  before entering the bake-off; non-compliant or non-mid-term strategies MUST be
  refused entry with an explicit reason, and the ranking MUST proceed with the
  compliant entrants.
- **FR-009**: Enabling a compliant mid-term challenger MUST automatically include
  it in subsequent bake-off runs with no change to the comparison harness.
- **FR-010**: The bake-off MUST be deterministic: the same snapshot and the same
  set of entrants MUST yield an identical ranking, identical metrics, and an
  identical report across repeated runs (no hidden randomness).
- **FR-011**: The free-data survivorship-bias caveat MUST be surfaced on the
  comparison output, noted as applying symmetrically to all entrants, and the
  verdict MUST be framed as a *relative* comparison under that shared limitation.
- **FR-012**: When only the baseline is enabled (no challenger), the system MUST
  surface an explicit "need at least one challenger" state and MUST NOT declare the
  baseline the winner by default.
- **FR-013**: Missing/limited point-in-time data for any entrant MUST be disclosed
  and handled consistently across entrants (e.g., restricting to the common
  overlapping window), never silently back-filled or treated as a pass for one
  strategy and a fail for another.
- **FR-014**: The system MUST produce a single head-to-head comparison report
  containing the ranked verdict, the named winner, the full per-entrant scorecard,
  the gross-vs-net breakdown, and the 2008–2009 stress block, with the stated cost
  assumptions, the standing disclaimer, and the `data_as_of` date.
- **FR-015**: No directive trading language ("Buy", "Sell", "Recommended", "Strong
  buy", "best strategy to buy", or equivalents) may appear in the comparison
  output; "winner"/"better" MUST be framed strictly as historical backtest
  performance under the stated criterion, not advice.
- **FR-016**: The bake-off MUST run against the same frozen snapshot / deep
  back-data used by feature 002 for continuity, and MUST note any finding that
  would only differ on live data.

### Key Entities *(include if data involved)*

- **Bake-Off Run**: one execution of the comparison against a named frozen
  snapshot; has a `data_as_of`, the window, the set of entrants, the cost model
  used, and the resulting ranking/verdict.
- **Strategy Entrant**: one strategy in the run — the baseline or a challenger —
  carrying its declaration (name, citation, timeframe, parameters, modifications)
  and its native rebalance cadence.
- **Scorecard**: the per-entrant metric set, in both gross and net form (Calmar,
  max drawdown, CAGR, Sharpe, Sortino, hit rate, turnover, exposure, cost drag).
- **Stress-Window Result**: an entrant's drawdown, return, and recovery across the
  2008–2009 window, surfaced as a first-class comparison dimension.
- **Ranking / Verdict**: the ordered list of entrants under the drawdown-resilient
  criterion, the named winner, and any explicit ties.
- **Cost Model**: the shared transaction-cost and slippage assumptions applied
  identically to all entrants, stated in the output.
- **Back-Data Snapshot**: the frozen deep-history US dataset (prices, fundamentals,
  universe, catalog) the run is evaluated against, identified by its `data_as_of`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single bake-off run ranks the baseline plus ≥1 mid-term challenger
  by the drawdown-resilient criterion and produces a full per-entrant scorecard,
  in one artifact, without manual per-strategy runs.
- **SC-002**: Re-running the bake-off on the same snapshot with the same entrants
  yields an identical ranking, identical metrics, and an identical report — 0
  unexplained differences.
- **SC-003**: 100% of entrants report both gross and net metrics with an explicit
  cost drag, and the ranking is computed from net figures.
- **SC-004**: 100% of entrants report a 2008–2009 stress-window result (drawdown,
  return, recovery).
- **SC-005**: The comparison basis is provably equal across entrants — same window,
  universe, liquidity gate, capital base, and cost model — with any asymmetry
  disclosed; 0 silently differing inputs.
- **SC-006**: A new compliant mid-term challenger can be added and appears in the
  next bake-off ranking with registration only — 0 changes to the comparison
  harness.
- **SC-007**: A non-compliant or non-mid-term strategy is refused entry with a
  stated reason — 0 ungated entrants in the ranking.
- **SC-008**: 0 instances of directive trading language in the comparison output;
  the `data_as_of` and disclaimer are present on the report.
- **SC-009**: The operator can run the bake-off and read the verdict in a single
  sitting once the snapshot and app are running (target: under 15 minutes of
  active driving).

## Assumptions

- **"Better" = drawdown-resilient**, per the operator's choice: the primary
  ranking metric is Calmar (CAGR ÷ max drawdown) with the lower max drawdown as
  tiebreaker, emphasizing survival through 2008–2009 — not raw absolute return.
- **Mid-term-class only.** The baseline is George & Hwang (2004) 52-week-high
  momentum. To make the comparison meaningful, at least one new peer-reviewed
  mid-term challenger is registered. Candidate examples (operator's choice, each
  must be registry-compliant with its own citation): Jegadeesh & Titman (1993)
  cross-sectional 12-1 momentum, time-series momentum (Moskowitz, Ooi & Pedersen
  2012), a value-plus-momentum combination (Asness, Moskowitz & Pedersen 2013), or
  a quality/profitability-tilted momentum (Novy-Marx 2013 / QMJ-style). The short-
  term strategies and the deferred CAN SLIM strategy are out of scope.
- **Both gross and net** are reported, using a single realistic-but-simple shared
  transaction-cost and slippage model whose assumptions are stated in the output;
  the ranking uses net figures.
- The bake-off **reuses the existing per-strategy walk-forward backtest
  infrastructure** (from 001) and the validated baseline (from 002); this feature
  adds the comparison, ranking, gross/net, stress-window, and report layer on top
  rather than rebuilding backtesting.
- The run uses the **same frozen back-data snapshot** established for 002 (deep
  Stooq history covering 2008–2009), so the verdict is reproducible; the
  survivorship-bias caveat applies equally to all entrants.
- The feature operates in the established **personal-use, single-user, single-
  machine** scope; no hosted/multi-user concerns.
- Same data snapshot + same entrants → identical comparison output, per the
  project's determinism rule.

## Dependencies

- **Feature 001 (screener MVP):** the strategy registry, the universe-wide
  liquidity gate, capital-aware sizing, and the per-strategy walk-forward backtest
  engine (≥15 years including 2008–2009).
- **Feature 002 (app & strategy validation):** the validated baseline
  `midterm_52w_high_momentum` and the frozen back-data snapshot this comparison
  runs against.
- **Deep back data:** the Stooq daily-bar bundle providing pre-2010 history; the
  free-data survivorship-bias limitation is inherited and disclosed.
