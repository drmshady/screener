# Feature Specification: AI Sentiment & Narrative Intelligence (+ three bug fixes)

**Feature Branch**: `014-ai-sentiment-narrative`
**Created**: 2026-07-02
**Status**: Draft
**Input**: User description: "i want to add AI Sentiment Analysis + Narrative Intelligence feature for screener output and portfolio, search for free or low-budget options. Plus 2 bugs: (1) there is no add-to-watchlist option for screener candidates, and (2) the SPY 200-day SMA input is unavailable."

## Overview

This feature adds an **on-request AI-assisted sentiment and narrative report** so the owner
can see, on demand, *what story the market is telling* about specific stocks — a plain-language
summary of recent news/events and a coarse sentiment reading — sourced from **free or
low-budget** data feeds. It runs **only when the owner asks**, on a **set of stocks the owner
selects**, which they can pick from three places: **screener results**, their **portfolio
holdings**, or by **typing a ticker symbol manually**. Running on request (rather than
auto-generating for every name) keeps usage — and therefore cost — within the small budget.
The report is **informational only**: it never changes which candidates pass gates, their
ranking, price levels, sizing, or any backtest baseline, and it carries no directive
("buy/sell") language.

Bundled with it are three **bug fixes** that stand on their own and can ship first:

- **Bug A** — screener candidates cannot be reliably added to the watchlist from every
  surface where a candidate is shown (notably the candidate detail page has no
  add-to-watchlist control, and the screen-table control gives no confirmation feedback).
- **Bug B** — the SPY 200-day SMA market-regime input can display as *unavailable / Unknown*
  in the app, so the regime panel and any regime-dependent narrative lose their basis.
- **Bug C** — the Market Events panel (FOMC/CPI/NFP/PCE/PPI schedule) shows a persistent
  *Stale events data* badge and eventually an empty window, because the curated macro
  calendar is re-seeded daily from a static file whose as-of date never advances and whose
  finite hand-entered events expire as their dates pass.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Add any screener candidate to the watchlist (Priority: P1) — Bug A

The owner runs a screen, opens a candidate's detail page (or stays on the results table),
and wants to track that name without committing capital. Today the detail page offers only
"Add to portfolio," and the table's "Add to watchlist" click produces no visible confirmation,
so the owner is unsure whether the name was saved.

**Why this priority**: Smallest, highest-certainty fix; a core existing workflow (watch a
name until it becomes entry-ready) is broken/ambiguous. Ships independently of everything else.

**Independent Test**: From both the results table and the candidate detail page, add a
candidate to the watchlist and confirm it appears on the watchlist page with its captured
levels; a clear confirmation is shown at the point of action.

**Acceptance Scenarios**:

1. **Given** a screen with ≥1 candidate, **When** the owner clicks "Add to watchlist" on a
   candidate row, **Then** a visible confirmation appears and the name is present on the
   watchlist page with its entry/stop/target snapshot and originating strategy.
2. **Given** a candidate detail page, **When** the owner adds the candidate to the watchlist,
   **Then** the same result occurs as from the table (parity across surfaces).
3. **Given** a candidate already on the watchlist for the same strategy, **When** the owner
   adds it again, **Then** no duplicate entry is created and the owner is informed it is
   already watched.

---

### User Story 2 — Trustworthy market-regime (SPY 200-day SMA) reading (Priority: P1) — Bug B

The owner relies on the market-regime line ("SPY above/below its 200-day SMA") to interpret
whether new-entry conditions are favorable. When the SPY 200-day SMA input is unavailable,
the regime shows *Unknown* and the gate silently fails open, undermining trust in the reading.

**Why this priority**: The regime gate is a declared strategy input; a persistently blank
input is a correctness/trust defect and also a prerequisite for regime-aware narrative (US4).

**Independent Test**: On a fresh run (including the hosted deployment and when the live price
feed is unreachable), the regime panel shows a concrete SPY close, a computed 200-day SMA
value, an above/below verdict, and the source + as-of date of the SPY series — not "Unknown."

**Acceptance Scenarios**:

1. **Given** the app is running with its baked/offline data only (live feed unreachable),
   **When** the owner views the regime panel, **Then** a numeric SPY 200-day SMA and verdict
   are shown with the SPY series' source and as-of date.
2. **Given** the SPY 200-day SMA genuinely cannot be computed (insufficient history),
   **When** the regime is displayed, **Then** the app states plainly why it is unavailable and
   that the gate fails open — rather than a bare "Unknown."
3. **Given** a normal snapshot, **When** the regime is computed twice for the same snapshot,
   **Then** the SPY close, SMA, and verdict are identical (determinism preserved).

---

### Bug C — Trustworthy market-events calendar (Priority: P1)

The owner reads the Market Events panel (FOMC, CPI, NFP, PCE, PPI) to anticipate macro
catalysts. Today it shows a persistent "Stale events data" warning and eventually an empty
window, because the curated calendar is re-seeded daily from a static file whose as-of date
never advances, and its hand-entered events expire as their dates pass.

**Why this priority**: A trust/correctness defect on a surface the owner relies on;
small, self-contained, and ships with the other two fixes ahead of the sentiment work.

**Independent Test**: After the daily refresh runs, the panel lists upcoming macro events
with real dates and shows no stale badge; the badge appears only when the source is genuinely
past its refresh interval.

**Acceptance Scenarios**:

1. **Given** the daily refresh re-seeded the calendar today, **When** the owner views Market
   Events, **Then** no "Stale events data" badge is shown and upcoming FOMC/CPI/NFP/PCE/PPI
   events with real dates are listed.
2. **Given** the curated schedule reaches the end of officially-published dates, **When** the
   panel renders, **Then** it clearly states the schedule extends through the last published
   date rather than showing a bare empty window or fabricating dates.
3. **Given** the same snapshot, **When** market events are computed twice, **Then** the output
   is identical (determinism preserved).

---

### User Story 3 — Run sentiment & narrative on-request for selected stocks (Priority: P2)

The owner explicitly **chooses which stocks to analyze** and triggers the report on demand.
They can pick names from **screener results** (e.g., select one or more candidates), from
their **portfolio holdings**, or by **typing a ticker symbol manually**. On running, each
selected stock gets a compact **narrative summary** (the recent storyline: earnings, guidance,
product/regulatory news, notable filings) and a **coarse sentiment label** (positive / mixed /
negative / no-signal) with the sources and recency behind it. Nothing is generated until the
owner asks, and only for the stocks they selected — this bounds usage and cost. It helps the
owner decide what to research further; it does not tell them what to trade.

**Why this priority**: The core new value, but larger and dependent on a data feed and on the
determinism/no-advice guardrails; sequenced after the two fixes. On-request (vs. auto-for-all)
keeps calls within the ~$5/month cap.

**Independent Test**: Select one or more stocks (from screener results and/or by manual ticker
entry), trigger the report, and confirm each selected stock shows a sentiment label and a short
narrative built only from cited, dated sources; the same data snapshot reproduces the same
label and summary; no directive language appears; a selected stock with no source data shows an
explicit "no signal" state (never a fabricated one); unselected stocks are never analyzed.

**Acceptance Scenarios**:

1. **Given** a screen with candidates, **When** the owner selects one or more and triggers the
   report, **Then** a sentiment label and a ≤N-sentence narrative are shown for each selected
   name, each claim attributable to a listed, dated source — and only the selected names run.
2. **Given** the report input, **When** the owner types a ticker symbol manually and triggers
   the report, **Then** the same sentiment label + narrative are produced for that symbol
   (independent of whether it appeared in any screen), or a clear "symbol not found / no
   coverage" state if it cannot be resolved.
3. **Given** a selected stock with no qualifying source data, **When** the report runs, **Then**
   an explicit "no sentiment signal" state is shown (not a neutral fabrication).
4. **Given** the same data snapshot and the same selected stock, **When** the report is run
   twice, **Then** the displayed label and narrative are identical.
5. **Given** any report, **When** the narrative is rendered, **Then** it contains zero directive
   trading terms and does not alter any candidate's gate result, rank, levels, or sizing.

---

### User Story 4 — Run the report on selected portfolio holdings (Priority: P3)

From the portfolio view, the owner **selects one or more held positions** and runs the same
on-request sentiment + narrative report, so they can spot when the story behind a position has
shifted — without analyzing the whole portfolio unless they choose to.

**Why this priority**: Reuses US3's engine and selection model on a second source surface;
valuable but lowest-risk to defer.

**Independent Test**: With holdings present, select one or more and run the report; each shows
the sentiment label + narrative from cited/dated sources under the same on-request, determinism,
and no-advice rules as US3; unselected holdings are not analyzed.

**Acceptance Scenarios**:

1. **Given** ≥1 holding, **When** the owner selects holdings and runs the report, **Then** each
   selected holding shows its sentiment label and narrative, or an explicit "no signal" state.
2. **Given** a selected holding whose recent news is materially negative, **When** the report
   runs, **Then** the negative sentiment and its sources are surfaced without any directive
   suggestion.

---

### Edge Cases

- **Manual symbol invalid / unknown**: the report shows a clear "symbol not found / no coverage"
  state for that entry and still runs for any other valid selected stocks.
- **Nothing selected**: triggering the report with no stocks selected is prevented or produces a
  clear "select at least one stock" prompt — no empty/erroneous run.
- **Source feed down / rate-limited**: the report shows "sentiment unavailable" for affected
  names and the rest of the app remains fully usable (fail-soft, never blocks a screen).
- **Stale sources**: a source older than the freshness threshold is labeled stale, not shown
  as current.
- **Conflicting sources** (bullish + bearish same day): reflected as a "mixed" label, not
  silently resolved to one side.
- **Non-English or thin coverage** (e.g., Saudi test market): explicit "no/low signal" state.
- **Budget/quota exhausted for the period**: overlay degrades to "unavailable" and the app
  keeps working; the owner is told the quota is spent, never silently charged beyond the cap.
- **Hosted mode**: overlay obeys the hosted-mode rules (owner-only access, `data_as_of` +
  disclaimer on every response, no directive framing, no heavy in-host generation if it would
  break the atomic-snapshot serving guarantee).

## Requirements *(mandatory)*

### Functional Requirements — Bug A (Watchlist)

- **FR-A1**: The owner MUST be able to add a screener candidate to the watchlist from every
  surface that displays a candidate — at minimum the results table and the candidate detail page.
- **FR-A2**: Adding to the watchlist MUST produce an immediate, visible confirmation at the
  point of action.
- **FR-A3**: A watchlisted candidate MUST persist with its captured entry/stop/target snapshot
  and originating strategy, and MUST appear on the watchlist page.
- **FR-A4**: Re-adding the same candidate for the same strategy MUST NOT create a duplicate and
  MUST inform the owner it is already watched.

### Functional Requirements — Bug B (SPY 200-day SMA / regime)

- **FR-B1**: The market-regime reading MUST display a concrete SPY close, a computed 200-day
  SMA, an above/below verdict, and the SPY series' source and as-of date whenever the data to
  compute them exists — including in the hosted deployment and when the live price feed is
  unreachable.
- **FR-B2**: When the 200-day SMA genuinely cannot be computed, the app MUST state the specific
  reason and that the gate fails open, instead of a bare "Unknown."
- **FR-B3**: The regime computation MUST remain deterministic for a given data snapshot and MUST
  NOT change any strategy rule, default, citation, indicator, or backtest baseline.

### Functional Requirements — Bug C (Market events calendar)

- **FR-C1**: The market-events freshness state MUST reflect the calendar's **actual** last refresh
  (the daily reseed time), not a static content date, so a re-seeded, still-valid calendar is NOT
  flagged stale.
- **FR-C2**: The curated macro calendar MUST be extended with **officially-published dates only**
  (Fed / BLS / BEA); when official schedules end, the panel MUST say so rather than emptying
  silently or fabricating dates.
- **FR-C3**: Market-events computation MUST remain deterministic for a given snapshot and MUST NOT
  change any strategy rule, default, indicator, or backtest baseline.

### Functional Requirements — Sentiment & Narrative Report (US3/US4)

- **FR-S0**: The report MUST run **only on explicit owner request** (never auto-generated for
  every candidate/holding), and MUST run only for the **stocks the owner selected**.
- **FR-S0a**: The owner MUST be able to assemble the selection from three sources: **screener
  results** (select one or more candidates), **portfolio holdings** (select one or more), and
  **manual ticker entry** (type a symbol). Multiple stocks MAY be run in one request.
- **FR-S0b**: A manually entered symbol MUST be resolved and analyzed independently of whether it
  appears in any screen or the portfolio; an unresolvable symbol MUST return a clear "symbol not
  found / no coverage" state without failing the other selected stocks.
- **FR-S0c**: Triggering the report with no stocks selected MUST be prevented or produce a clear
  "select at least one stock" prompt — never an empty or erroneous run.
- **FR-S1**: For each selected stock, the system MUST present a coarse sentiment label (at least:
  positive / mixed / negative / no-signal) and a short narrative summary of the recent storyline.
- **FR-S2**: Every sentiment/narrative claim MUST be attributable to one or more listed sources,
  each with a date; unsourced assertions MUST NOT appear.
- **FR-S3**: The report MUST be **informational only**: it MUST NOT change any candidate's gate
  result, ranking, price levels, position sizing, regime, or backtest baseline.
- **FR-S4**: The report MUST contain **zero directive trading language** (no "buy", "sell",
  "recommended", "strong buy", etc.), consistent with the existing UI-copy lint.
- **FR-S5**: For a given data snapshot and selected stock, the displayed sentiment label and
  narrative MUST be reproducible (same snapshot + same stock → same result); any non-deterministic
  generation MUST be captured/snapshotted so the served result is stable and re-inspectable.
- **FR-S6**: When no qualifying source data exists for a selected stock, the report MUST show an
  explicit "no signal" state and MUST NOT fabricate a neutral or invented narrative.
- **FR-S7**: The report MUST fail soft: a source/model outage affects only the affected selected
  names and never blocks a screen, a portfolio view, or any other feature.
- **FR-S8**: Every response exposing the report MUST continue to carry `data_as_of` and
  `disclaimer`, and MUST respect hosted-mode owner-only access and the forced directive-OFF rule.
- **FR-S9**: The chosen data/model sources MUST be free or within an **owner-approved cap of
  ~$5/month**; the system MUST enforce a hard spend/quota cap and degrade gracefully to free
  sources when it is reached, never silently exceeding the cap.
- **FR-S10**: The sources feeding sentiment/narrative MUST be drawn from an explicitly bounded,
  owner-disclosed set: **free news headlines**, the **existing EDGAR / 8-K events** the app
  already ingests, **analyst/ratings feeds** where a free or in-budget source exists, and
  **social/retail sentiment** where a free or in-budget, licensing-permissible source exists.
  Each source class MUST be individually labeled on the report, and any class that is
  unavailable, out of budget, or licensing-restricted MUST simply be omitted (fail-soft),
  never fabricated. Social/retail sentiment in particular MUST be clearly marked as low-signal
  / noisy and MUST still satisfy the determinism (FR-S5) and sourcing (FR-S2) rules.
- **FR-S11**: Personal-use scope is preserved: single owner, no redistribution of third-party
  source content beyond what the owner is licensed to view.
- **FR-S12**: The report MAY include a **narrative-intelligence** overlay (a bounded "is a story
  forming/escalating?" reading) computed only from the feasible signals its available sources
  support. It MUST be **presentation-only** (never changes a gate result, rank, level, sizing, or
  regime), MUST use **neutral, non-directive** labels (no "avoid/enter/review" phrasing), and MUST
  satisfy the same determinism (FR-S5) and sourcing (FR-S2) rules; signals that require sources not
  yet available (e.g. the deferred social layer) MUST be omitted, not estimated.

### Key Entities

- **Sentiment/Narrative Report**: produced on request for a selected ticker + as-of snapshot —
  a sentiment label, a bounded narrative summary, the list of contributing sources (name, date,
  link/reference) with per-class labels, freshness, and a signal-present/absent flag.
- **Report Request / Selection**: the owner-assembled set of tickers to analyze, each tagged with
  its origin (screener result, portfolio holding, or manual entry).
- **Source Item**: an individual news/event/filing record (title, publisher, date, reference)
  used as narrative evidence.
- **Watchlist Entry** (existing): reused by Bug A; captures ticker, strategy, and level snapshot.
- **Market Regime** (existing): reused/repaired by Bug B; SPY close, 200-day SMA, verdict,
  source, as-of date.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From 100% of surfaces that display a screener candidate, the owner can add it to
  the watchlist and receives a confirmation within 1 second.
- **SC-002**: In the hosted deployment with the live feed unreachable, the regime panel shows a
  numeric SPY 200-day SMA and a verdict (not "Unknown") on 100% of loads where sufficient SPY
  history exists.
- **SC-003**: 100% of displayed sentiment/narrative claims are traceable to a listed, dated
  source; 0% contain directive trading language (enforced by the existing copy lint).
- **SC-004**: Re-running the report for the same selected stock on an unchanged data snapshot
  reproduces byte-identical labels and narratives 100% of the time.
- **SC-005**: Selected stocks with no qualifying source data show an explicit "no signal" state
  in 100% of such cases (0 fabricated narratives).
- **SC-006**: A source/model outage degrades only affected selected names; the screen, portfolio,
  and every other feature remain fully usable (0 screen failures attributable to the report).
- **SC-007**: Recurring data/model cost stays within the ~$5/month cap in 100% of billing
  periods; reaching the cap degrades the report without exceeding spend. (On-request execution
  means calls are incurred only for owner-selected stocks.)
- **SC-009**: The report runs only for owner-selected stocks — 0 model/API calls are made for
  stocks the owner did not select, and 0 reports are generated without an explicit trigger.
- **SC-008**: No strategy rule, default, citation, indicator, or backtest baseline changes as a
  result of this feature (verified against the frozen baselines).
- **SC-010**: After a successful daily refresh, the market-events panel shows upcoming macro events
  with real dates and **no spurious "stale" badge** in 100% of runs where the reseed succeeded;
  the badge appears only when the source is genuinely past its refresh interval.

## Assumptions

- The AI overlay is **presentation only**, mirroring prior features (events/news badges):
  it never affects gates, ranking, levels, sizing, regime, or backtests. (Confirmed by the
  owner: informational-only.)
- Budget ceiling is **~$5/month**, mostly free-tier with a small metered allowance for LLM
  calls or a cheap feed, behind a hard cap. (Confirmed by the owner.)
- Sentiment sources span free news headlines, existing EDGAR/8-K events, analyst/ratings, and
  social/retail sentiment — each used only where a free/in-budget, licensing-permissible option
  exists, each labeled, and each omitted (not faked) when unavailable. (Confirmed by the owner.)
- Determinism and the no-advice boundary are non-negotiable constitution rules, so any
  LLM/model output is **captured into the snapshot** and served deterministically, not
  regenerated live per view.
- The existing watchlist store, candidate model, and regime module are reused/extended rather
  than replaced.
- Bug B builds on the existing daily-baked offline SPY series work; the fix hardens
  availability/labeling rather than introducing a new regime source.
- Bug C hardens the freshness accounting + curated coverage of the **existing** macro calendar
  (no new macro-data provider, no fabricated dates); the daily reseed stamps the real refresh time.
- Sentiment **scoring** uses a deterministic-friendly finance-domain classifier (FinBERT) whose
  output is captured for reproducibility, with a fully-transparent lexicon fallback; it is a
  presentation-layer tagger, never a screen/strategy input. The optional **narrative prose** model
  is provider-swappable (a free-tier Gemini key or Claude Haiku) within the ~$5/month cap, and its
  output is captured. News uses a free key-free baseline with owner-supplied Finnhub / Alpha Vantage
  keys as fail-soft backups. (Confirmed by the owner.)
- Hosted mode remains single-owner, owner-secret gated, with `data_as_of` + `disclaimer` and
  forced directive-OFF.
- "Search for free or low-budget options" is an instruction to evaluate free/low-budget data +
  model providers during planning; it is not a separate user-facing "search" feature.

## Dependencies

- Existing watchlist persistence and candidate/holdings data models (frontend store + backend).
- Existing market-regime module and the daily-baked SPY history / offline fallback chain.
- Free/low-budget news + sentiment sources (news headlines, EDGAR/8-K events, and — where a
  free/in-budget option exists — analyst/ratings and social/retail sentiment) and, if used, a
  low-cost language model within the ~$5/month cap — specific providers selected in planning.
- Hosted-mode config, owner-secret access gate, and the `data_as_of`/`disclaimer` envelope.
