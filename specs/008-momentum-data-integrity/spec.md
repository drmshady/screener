# Feature Specification: Strategy Defect Detection & Output Integrity (Momentum Pilot)

**Feature Branch**: `008-momentum-data-integrity`
**Created**: 2026-06-15
**Status**: Draft
**Input**: User description: "focus on midterm momentum strategy — I think there is a bug in the implementation. A snapshot as-of 2026-06-12 ranked BELFB #2 in the risk-adjusted list at price 293.87, 3.0% below its 52-week high, with +221% trailing 12-1 momentum. Live, BELFB trades around $184 — roughly 35% below the snapshot entry. … Separately, IOSP surfaced with −9.8% 12-1 momentum — is a missing momentum floor a bug or by-design?" Follow-up: "the main thing I want is for the app to be able to DETECT defects in the strategy so I can rely on it — it should be robust against other bugs that have not been reported."

## Context & Problem Statement

The operator needs to **trust** the screener's strategy output. Today they cannot: a single pasted candidate (BELFB) was caught only because an external advisor happened to notice a ~35% price discrepancy — the screener itself surfaced a corrupt #2-ranked candidate with no warning. The real problem is not one bad price; it is that **the screener has no way to detect when its own strategy output is wrong**, so any number of unreported defects could be sitting in the results undetected.

This feature's primary goal is therefore a **strategy defect-detection capability**: the screener must continuously check that its strategy output satisfies the properties any correct output must have, and loudly surface anything that does not — including classes of bug that have never been reported. The BELFB case is the motivating example and the first defect the capability must catch, not the whole of the work.

The detection approach is **invariant/contract-based**, because that is what makes it robust to *unknown* bugs: rather than hunting for the specific BELFB symptom, the screener checks rules that must hold for every candidate of a strategy regardless of root cause — e.g. that the displayed distance-to-high actually reconciles with the displayed price and 52-week high, that every listed candidate truly satisfies the strategy's hard gate, that the published score reproduces from its own formula, that prices are positive and finite, that the entry/stop/target ordering and R-multiple hold, and that the figures agree with an independent source. A defect of *any* origin breaks at least one such rule.

Scope is **detection, verification, data-correctness, and presentation** — **no change** to any strategy's declared rules, defaults, citations, or committed backtest baselines. The detection mechanism is **strategy-agnostic** (each strategy declares a checkable output contract); this feature implements and fully validates it for the **mid-term momentum strategy** as the pilot and keeps it expressible for the value strategy's existing safeguards, with other strategies a thin follow-on.

### Why the momentum strategy is the pilot (code-grounded defect candidates)

The known momentum failure modes give the pilot contract its first concrete invariants to enforce:

1. **Unadjusted prices feed momentum math.** `52w_high` is the peak daily *closing* price over 252 bars and `return_12_1` is a ratio of two raw closes — both from the unadjusted `close` column, never `adj_close`. A corporate action not reflected consistently across the window corrupts both. → *coherence + plausibility invariants.*
2. **Cross-source seam discontinuity.** The live screen stitches a static Stooq base with a fresh yfinance overlay (overlay wins at the seam, `adj_close` dropped). Different adjustment bases across the seam manufacture a spurious 12-1 return and an inflated high. → *series-integrity invariant.*
3. **Share-class mismatch.** BELFA vs BELFB trade at different prices; a wrong-class price/fundamentals join yields incoherence. → *identity/coherence invariant.*
4. **No data-sanity guard on momentum inputs.** The value path drops a name on implausible yields; the momentum path has no equivalent backstop. → *value-domain/plausibility invariant.*
5. **Staleness gate checks recency, not correctness.** A name whose last bar is *recent but wrong* passes. → *independent cross-check + plausibility invariant.*

### Operator decisions (resolved)

- **Detection breadth** — a strategy-agnostic detection framework, fully implemented and validated for the **momentum** strategy now; the value strategy's existing implausibility backstop is expressible in the same contract form; other strategies follow on thinly.
- **Enforcement** — **both** a lightweight, deterministic, internal-only check on **every live screen** (anomalies surface immediately as data notes / per-candidate warnings) **and** a heavier **offline harness** (independent-source cross-check + seeded-defect regression tests) run in CI / on demand over frozen snapshots. One contract definition, enforced in two places.
- **Momentum floor — rank-only, no gate.** A near-high name with negative/weak 12-1 momentum (IOSP at −9.8%) is working as designed: proximity is the thesis; momentum only ranks. No momentum-floor gate is added; the negative momentum is simply made visible.
- **Suspect-data disposition — keep + loud per-candidate warning, demoted.** A candidate whose figures fail a check is not silently excluded; it stays listed, carries a specific data-integrity warning (which travels into the advisor-prompt export), and is ranked below all clean candidates.

## Clarifications

### Session 2026-06-15

- Q: By how much may a momentum candidate's displayed price diverge from an independent reference before it must be flagged as data-suspect? → A: 10% (price divergence ≥ 10% from an independent reference, or a single-session move ≥ 10% not explained by a corporate action, marks the figure suspect).
- Q: Where does a data-suspect (flagged) candidate sit in the ranked list — keep its score position, or demote it? → A: Demote below all clean candidates (sort flagged names last, mirroring the existing `warning_count`-then-score tiered ordering); the name stays listed but never outranks a clean candidate.
- Q: Where does corporate-action knowledge come from, so the guard separates a real large move from an adjustment artifact? → A: Use the price providers' adjustment/actions data (split + dividend events, and the `adj_close` the pipeline currently ignores) as the source of truth; purely-statistical discontinuity/outlier detection is only a backstop for gaps the feed misses.
- Q: How is "independent reference" defined, and how are strategy results verified against it? → A: An independent reference is a price source NOT part of the screen's own snapshot-building pipeline (not the Stooq base or the yfinance historical-bar overlay) — e.g. a direct live/EOD quote endpoint queried separately. Verification is a reproducible harness that cross-checks the top-N candidates' price and 52-week-high against it (agree within 10% or be flagged) and emits a classified report; the live screen stays deterministic.
- Q: How broad should defect detection be (which strategies)? → A: A strategy-agnostic framework (each strategy declares an output contract), fully implemented + validated for the **momentum** strategy now; value's existing backstop expressible in the same form; other strategies a thin follow-on.
- Q: Where do the defect checks run? → A: **Both** — deterministic internal checks on every live screen (immediate surfacing) AND an offline harness (independent cross-check + seeded-defect regression) in CI / on demand. One contract, two enforcement points.
- Q: Which adjustment basis is canonical for the momentum figures? → A: Adjusted lookback, raw last close — `return_12_1` and `52w_high` are computed from a split+dividend-adjusted series; the displayed entry/price is the latest actual close (which equals the latest `adj_close`, so the `entry == close` coherence invariant still holds). Fixes BELFB's seam/split artifact without distorting the tradable entry price.
- Q: What concrete source is the harness's independent reference? → A: A free-tier third-party quote API from a vendor outside the snapshot pipeline (e.g. Finnhub / Alpha Vantage) providing price + 52-week-high; truly independent of Stooq and yfinance. Any API key is kept process-local only and never written to a file. No paid feed is introduced.
- Q: How is CI enforcement split between the deterministic and network-dependent checks? → A: The deterministic seeded-defect test is a blocking CI gate; the network independent-source cross-check runs on demand / scheduled and reports, but does NOT block CI (so network unavailability / UNVERIFIED results never break unrelated builds).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every screen self-checks its output and surfaces any defect (Priority: P1)

As the solo operator, every time I run a strategy screen, the screener validates the candidates it is about to show me against a declared set of invariants the output must satisfy, and loudly surfaces anything that violates them — so a corrupt figure of *any* origin never reaches me unflagged. This is what lets me rely on the app instead of needing an external advisor to spot-check it.

**Why this priority**: This is the feature's core purpose — detection that is robust to unreported bugs because it checks what must be true, not a known symptom. It directly converts "I can't trust the output" into "the output tells me when it can't be trusted."

**Independent Test**: On a frozen snapshot, deliberately corrupt a single candidate's underlying figure (e.g. set its displayed price inconsistent with its series, or break its score, or inject a NaN). Re-run the screen: the affected candidate appears with a specific data-integrity warning naming the violated invariant and is demoted below clean candidates; clean candidates carry no warning; the run does not crash.

**Acceptance Scenarios**:

1. **Given** a screen's returned candidates, **When** the screen completes, **Then** each candidate is validated against the active strategy's output contract before the result is returned, using only deterministic internal checks (no network call).
2. **Given** a candidate whose `dist_to_high` does not reconcile with its `close` and `52w_high`, **When** the screen returns, **Then** that candidate carries a coherence data-integrity warning and is demoted.
3. **Given** a candidate listed as a match that does not actually satisfy the strategy's hard gate at the stated parameter, **When** the screen returns, **Then** it is flagged as a contract violation rather than presented as a clean match.
4. **Given** a candidate whose published score does not reproduce from its declared formula and published inputs, **When** the screen returns, **Then** it is flagged.
5. **Given** any surfaced or NaN/zero/negative/non-finite figure, **When** the screen returns, **Then** it is flagged, not silently shown.
6. **Given** a fully coherent set of candidates, **When** the screen returns, **Then** no data-integrity warnings are raised (no false positives).
7. **Given** the same frozen snapshot screened twice, **When** the checks run, **Then** the figures and the set of warnings are identical (determinism preserved).

---

### User Story 2 - Robustness is proven by an offline harness with seeded-defect tests and an independent cross-check (Priority: P1)

As the solo operator, I can run an offline harness that (a) injects a representative set of synthetic defects into a frozen snapshot and confirms the detection layer catches every one, and (b) cross-checks the top momentum candidates' prices against a source outside the screen's own pipeline — so I have evidence the detector works against unknown bugs and against the exact BELFB failure mode, not just a claim.

**Why this priority**: Seeded-defect testing is the only thing that *proves* robustness to unreported bugs; the independent cross-check is the only thing that catches a defect (like BELFB) whose value is internally self-consistent but wrong versus reality. Together they are the evidence base for trusting the app.

**Independent Test**: Run the harness on the 2026-06-12 frozen snapshot. It reports, per seeded defect class, whether the detection layer flagged it (100% required); and per top-N candidate, the screener price, the independent-source price, the divergence, and a verdict (AGREES / DIVERGES-AND-FLAGGED / DIVERGES-UNFLAGGED / UNVERIFIED). BELFB resolves to DIVERGES-AND-FLAGGED; coherent names (JBHT, CW) to AGREES; no seeded defect is missed.

**Acceptance Scenarios**:

1. **Given** a frozen snapshot, **When** the harness injects each synthetic defect class (corrupted price, broken score, stale-but-fresh bar, NaN field, inconsistent `dist_to_high`, cross-source seam discontinuity, share-class swap), **Then** the detection layer flags each injected defect and the harness reports any miss as a FAILURE.
2. **Given** the top-N momentum candidates, **When** the harness cross-checks each against an independent reference (not the Stooq base or yfinance overlay), **Then** it records the divergence and assigns a verdict; a ≥10% divergence with no screener warning (DIVERGES-UNFLAGGED) is a FAILURE.
3. **Given** the independent source is unavailable for a name, **When** the harness runs, **Then** it records UNVERIFIED (not a silent pass) and does not crash.
4. **Given** the harness completes, **When** it reports, **Then** it emits a classified, human-readable report (feature-002 pattern) with the independent-fetch timestamp recorded.
5. **Given** the same frozen snapshot, **When** the harness is re-run, **Then** the screener side of every verdict is identical (only the independent-fetch timestamp varies).

---

### User Story 3 - Momentum figures are computed correctly so clean names are not falsely flagged (Priority: P2)

As the solo operator, the known momentum data defects (unadjusted/seam-inconsistent prices, share-class joins, unhandled corporate actions) are remediated so that correct names compute coherent figures and are not flagged, and BELFB either reconciles to its true price or is honestly flagged. Detection without remediation would just flag everything; this makes the detector's signal meaningful.

**Why this priority**: Detection (US1/US2) is the headline, but a detector firing on avoidable internal incoherence is noise. Fixing the root-cause data handling keeps the false-positive rate near zero and makes a raised warning trustworthy.

**Independent Test**: Re-run the momentum screen on the frozen 2026-06-12 snapshot. BELFB's displayed price reconciles to its independently-verified market price within 10% **or** carries a data-integrity warning; its `return_12_1` is no longer the spurious +221%; and its `close`, `52w_high`, and `return_12_1` derive from one adjustment-consistent series across the full lookback window.

**Acceptance Scenarios**:

1. **Given** a name whose history is stitched from two sources, **When** the snapshot is built, **Then** `close`, `52w_high`, and `return_12_1` come from one adjustment-consistent series (no seam discontinuity in either window).
2. **Given** a name with two share classes (BELFA / BELFB), **When** its row is built, **Then** price and fundamentals map to a single share class with no cross-class join.
3. **Given** a split/reverse-split inside the lookback window, **When** `return_12_1` and `52w_high` are computed, **Then** the corporate action does not create an artificial jump or inflated high; corporate-action knowledge is sourced from the providers' adjustment/actions data, and a move it explains does not raise a flag.

---

### User Story 4 - Detected defects surface loudly, are demoted, and propagate to exports (Priority: P2)

As the solo operator, when a defect is detected on a candidate, the candidate stays in the list but carries a prominent, specific, actionable data-integrity warning, is ranked below every clean candidate, and the warning travels verbatim into the advisor-prompt export — so I cannot accidentally act on it and anyone I share the prompt with sees the caveat too.

**Why this priority**: This is the disposition the operator chose (flag-not-exclude, demote). It is how detection becomes safe to rely on, but it depends on US1/US2 existing to produce the flags.

**Independent Test**: Replay a BELFB-like bad bar through the screen. The candidate appears with a visible "price may be stale or erroneous — verify before acting" warning naming the suspect figure, sits below all clean candidates regardless of its raw score, and its advisor-prompt export contains the same warning verbatim. A clean candidate on the same snapshot has none of this.

**Acceptance Scenarios**:

1. **Given** a detected defect on a candidate, **When** the screen returns, **Then** the candidate is present (not excluded for this reason) with a specific, actionable per-candidate data-integrity warning naming the suspect figure.
2. **Given** a flagged candidate whose raw score would place it among the top ranks (BELFB at #2), **When** the list is ordered, **Then** it is demoted below every clean candidate and never outranks an unflagged name.
3. **Given** a flagged candidate, **When** the advisor-prompt export is generated, **Then** the warning is included verbatim.
4. **Given** any flagged or corrected name, **When** the screen returns, **Then** the result's data notes honestly record that a correction or flag was applied and to how many names.

---

### User Story 5 - Negative or weak 12-1 momentum is visible on the candidate (Priority: P3)

As the solo operator, when a near-52-week-high name has negative or weak trailing momentum (IOSP at −9.8%), the candidate clearly shows that momentum and its sign, so I can see it is "near the high but not rising" — even though, by design, it is not excluded.

**Why this priority**: A transparency fix for a by-design behavior, not a defect. It answers the operator's "is this a bug?" question by making the rank-only nature self-evident; it changes no rule and gates nothing.

**Acceptance Scenarios**:

1. **Given** a near-high candidate with negative 12-1 momentum, **When** it is listed, **Then** its 12-1 momentum value and sign are surfaced prominently, and it is not excluded.
2. **Given** two near-high candidates (one rising, one falling), **When** ranked, **Then** the falling name ranks below the rising name by score (existing behavior, verified unchanged).

---

### Edge Cases

- A split or reverse-split inside the 252-bar lookback window (must not inflate the high or create a phantom 12-1 jump).
- A dilutive secondary offering (price-mechanically distinct from a split; must not be mistaken for a price drop without flagging).
- A special/large cash distribution that shifts the unadjusted series.
- Two listed share classes for one issuer (BELFA vs BELFB) — no cross-class join.
- The cross-source seam carrying different adjustment bases between recent overlay bars and year-ago base bars.
- A latest close that is *recent* (passes the recency gate) but *erroneous* (a bad print).
- A name with fewer than 253 bars (12-1 undefined — already skipped; verify it is skipped, not flagged-as-defect).
- A genuinely halted/suspended/delisted name frozen near its old high (already excluded by the recency gate — retained).
- The independent source disagreeing because the screen is simply stale (last bar genuinely old) rather than wrong — must be distinguishable from a true defect.
- A seeded defect that the detector must NOT also raise on the un-corrupted control copy (no false positive).
- Determinism: the same frozen snapshot yields identical figures and identical warnings on every run.

## Requirements *(mandatory)*

### Functional Requirements — Defect-detection framework

- **FR-001**: The system MUST provide a strategy-agnostic defect-detection mechanism driven by a per-strategy **output contract** — a machine-checkable declaration of the invariants every candidate row of that strategy must satisfy. Adding or changing a strategy's contract MUST NOT require changing the detection engine.
- **FR-002**: Every live screen MUST validate its returned candidates against the active strategy's output contract before returning, using only **deterministic, internal (no-network) checks**, so detection preserves the determinism contract (FR-024).
- **FR-003**: The momentum pilot contract MUST enforce at least these invariant families: (a) **derived-field coherence** — `dist_to_high` equals `(52w_high − close)/close` and `entry` equals `close`, within rounding; (b) **gate satisfaction** — every listed candidate actually satisfies the hard 52-week-high proximity gate at the stated parameter; (c) **score reproduction** — the published score equals its declared formula evaluated on the published inputs, within tolerance; (d) **level sanity** — `0 < stop_loss < entry < take_profit` and the take-profit R-multiple matches the declared parameter within rounding; (e) **value-domain** — no NaN/infinite values in surfaced figures, no zero/negative price or ATR, and `return_12_1` / `52w_high` within plausibility bounds; (f) **series integrity** — the backing price series has strictly increasing unique dates and no implausible single-session jump unexplained by a corporate action.
- **FR-004**: A contract violation tied to a specific candidate MUST surface as a per-candidate data-integrity warning (US4); a universe-level or aggregate violation MUST surface as a data note. No violation may be silently dropped.
- **FR-005**: The detection layer MUST NOT raise a warning on coherent, correctly-computed candidates (false positives erode trust in the signal); the false-positive rate on a known-good frozen snapshot MUST be zero.
- **FR-006**: The value strategy's existing implausibility backstop (dropping names on implausible yields) MUST remain expressible within, and consistent with, the same output-contract form, demonstrating the mechanism is genuinely strategy-agnostic — without changing the value strategy's behavior or backtest baseline.

### Functional Requirements — Offline robustness harness

- **FR-007**: The feature MUST provide an offline harness, runnable in CI and on demand over a frozen snapshot, that performs both a **seeded-defect test** and an **independent-source cross-check**, and emits a classified, human-readable report (feature-002 pattern) with the independent-fetch timestamp recorded. The **seeded-defect test is a blocking CI gate** (deterministic, no network); the **independent-source cross-check runs on demand / scheduled and MUST NOT block CI** — a network outage or UNVERIFIED result reports but never fails an unrelated build.
- **FR-008**: The seeded-defect test MUST inject a representative set of synthetic defect classes — at minimum: corrupted price, broken score, stale-but-fresh last bar, NaN/missing field, inconsistent `dist_to_high`, cross-source seam discontinuity, and share-class swap — and assert the detection layer flags each. A missed injection MUST be reported as a failing result.
- **FR-009**: An "independent reference" MUST be a price source NOT part of the screen's own snapshot-building pipeline (not the Stooq deep-history base and not the yfinance historical-bar overlay). It MUST be a free-tier third-party quote API from a vendor outside the pipeline (e.g. Finnhub / Alpha Vantage) supplying price and 52-week-high; no paid price feed is introduced. Any API key it requires MUST be supplied process-local only and MUST NOT be written to any file. Any runtime use of an independent reference MUST be pinned to the snapshot's as-of date so the screen stays deterministic (FR-024); the harness's independent fetch MAY be live and is timestamped.
- **FR-010**: The harness MUST, for the top-N momentum candidates of a frozen snapshot (where "top-N" is the screen's returned candidate list, capped at the top 10 when longer), fetch each name's price and 52-week-high from the independent reference, compute the percentage divergence, and assign a verdict: AGREES (< 10% divergence), DIVERGES-AND-FLAGGED (≥ 10% and the screener carries a data-integrity warning), DIVERGES-UNFLAGGED (≥ 10% and no warning — a FAILURE), or UNVERIFIED (source unavailable).
- **FR-011**: The harness MUST distinguish a genuine defect from mere staleness: when the screen's last bar is honestly old (already noted as stale), a divergence attributable to that staleness MUST be classified separately from a DIVERGES-UNFLAGGED defect.

### Functional Requirements — Momentum data correctness

- **FR-012**: The momentum figures `close` (entry), distance-to-52-week-high, and `return_12_1` MUST be derived from a single price series with one consistent adjustment basis across the entire lookback window used for each figure. The canonical basis is **split+dividend-adjusted for the lookback windows**: `return_12_1` and `52w_high` MUST be computed from the adjusted series, while the displayed entry/price is the **latest actual (raw) close** — which equals the latest `adj_close`, so the `entry == close` coherence invariant (FR-003a) is preserved and the displayed entry remains the true tradable price.
- **FR-013**: When a name's history is assembled from more than one source, the system MUST ensure the stitched series does not introduce an adjustment-basis discontinuity at the seam affecting the 12-1 window or the 52-week-high window; if it cannot guarantee this, the affected figures MUST be flagged (FR-004 / US4).
- **FR-014**: A momentum candidate's price series and name/identity MUST map to exactly one share class; the system MUST NOT join price and fundamentals across share classes of the same issuer.
- **FR-015**: Corporate actions inside the lookback window (at minimum splits and reverse-splits) MUST NOT produce an artificial discontinuity in `return_12_1` or an inflated `52w_high`. Corporate-action knowledge MUST be sourced from the providers' adjustment/actions data (split + dividend events and the providers' adjusted-close basis); purely-statistical detection is a backstop only for gaps the feed misses, and a move explained by a known corporate action MUST NOT raise a defect flag.
- **FR-016**: The data-suspect threshold MUST be: a `return_12_1` beyond a plausibility bound, OR a latest close diverging by **≥ 10%** from an independent reference or from the prior session without a corporate action that explains it.

### Functional Requirements — Disposition, transparency, and invariants

- **FR-017**: Data-suspect / contract-violating candidates MUST remain in the result list (NOT excluded for this reason) and MUST carry a prominent, specific, actionable per-candidate data-integrity warning naming the suspect figure and the reason ("verify before acting"), machine-readable enough to surface in the UI and exports.
- **FR-018**: Flagged candidates MUST be ranked **below all clean candidates** — a flagged name never outranks an unflagged one regardless of raw score (extending the existing `warning_count`-then-score ordering); within the flagged group the existing score order is preserved.
- **FR-019**: The advisor-prompt export for a flagged candidate MUST include the candidate's data-integrity warning verbatim.
- **FR-020**: Each momentum candidate MUST surface its 12-1 trailing momentum value and sign prominently so a near-high-but-falling name is distinguishable from a near-high-and-rising one.
- **FR-021**: The system MUST NOT add a momentum-floor gate; near-high names with negative/weak 12-1 momentum remain listed and ranked (rank-only is the resolved design).
- **FR-022**: The existing per-ticker staleness/recency exclusion MUST be retained unchanged; this feature adds detection, correctness, and flagging on top of it.
- **FR-023**: The feature MUST NOT change any strategy's declared rules, parameter defaults, citations, regime favorability, or committed backtest baseline metrics; all changes are confined to detection, data correctness, and presentation.
- **FR-024**: Screen output MUST remain deterministic: the same frozen snapshot MUST yield identical figures and identical data-integrity warnings on every run.

### Key Entities *(include if feature involves data)*

- **Strategy output contract**: a per-strategy, machine-checkable declaration of the invariants its candidate rows must satisfy (coherence, gate satisfaction, score reproduction, level sanity, value-domain, series integrity); read by the strategy-agnostic detection engine.
- **Defect / contract violation**: a detected breach of an invariant, with the violated rule, the affected figure, a reason code, and a severity (candidate-level → per-candidate warning + demotion; aggregate → data note).
- **Seeded defect**: a synthetic, deliberately injected fault used by the offline harness to prove the detector catches a given bug class.
- **Momentum candidate figure set**: the operator-facing numbers for one candidate (price/entry, distance to 52-week high, 12-1 momentum, volatility scalar, score), which must be mutually coherent and each tied to the same underlying series.
- **Price series (per ticker, per source)**: the ordered daily bars backing a name, characterized by source, adjustment basis, share-class identity, and as-of date — the unit across which adjustment consistency and seam continuity are evaluated.
- **Corporate action event**: a split, reverse-split, secondary offering, or large distribution inside the lookback window, with a type, effective date, and (where applicable) adjustment factor.
- **Independent reference**: a price source outside the snapshot-building pipeline used to cross-check figures against reality.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The seeded-defect test detects **100%** of injected synthetic defect classes (zero silent misses); a miss fails the feature. *(This is the primary robustness-against-unknown-bugs proof.)*
- **SC-002**: On a known-good frozen snapshot, the detection layer raises **0** false-positive data-integrity warnings on coherent candidates.
- **SC-003**: On the 2026-06-12 frozen snapshot, BELFB's displayed price reconciles to its independently-verified market price within **10%** OR the candidate carries a data-integrity warning — in no case is BELFB a clean, unflagged top-ranked match on a ~35%-wrong price.
- **SC-004**: The offline harness produces **zero** DIVERGES-UNFLAGGED verdicts on the 2026-06-12 snapshot (every ≥10% divergence is accompanied by a screener warning); BELFB → DIVERGES-AND-FLAGGED; coherent control names (JBHT, CW) → AGREES.
- **SC-005**: Every live screen runs the contract checks and remains deterministic (same snapshot → identical figures and identical warning set), adding under **5%** to total screen runtime.
- **SC-006**: 100% of momentum candidates whose 12-1 return exceeds the plausibility bound, or whose latest close diverges ≥10% unexplained, carry a per-candidate data-integrity warning.
- **SC-007**: 0 momentum candidates present a price, a 52-week-high distance, and a 12-1 momentum drawn from price segments with inconsistent adjustment bases; 0 are built on a cross-share-class join.
- **SC-008**: For every flagged candidate, the advisor-prompt export contains the data-integrity warning verbatim (100% propagation), and the flagged name is ranked below all clean candidates.
- **SC-009**: The same output-contract engine runs both the momentum contract and the value strategy's (re-expressed) implausibility backstop with no per-strategy engine code, demonstrating strategy-agnostic extensibility.
- **SC-010**: The committed backtest summary metrics for `midterm_52w_high_momentum` (and `midterm_value_composite`) are unchanged versus the pre-feature baseline (no rule/default drift).
- **SC-011**: Every momentum candidate exposes its 12-1 momentum value and sign such that a reviewer can identify a negative-momentum near-high name from the candidate alone in under 5 seconds.

## Assumptions

- The free data tier remains the source of record: Stooq deep history as the base, a yfinance overlay for recency, EDGAR-cache fundamentals. No paid price feed is introduced.
- The framework is implemented and fully validated for the **momentum** strategy now; the value strategy's existing backstop is re-expressed in contract form without behavior change; the short-term strategies are out of scope for this feature but the mechanism is designed to accept their contracts later with no engine change.
- "Adjustment-consistent" means split/reverse-split-consistent at minimum across the lookback window; full dividend/distribution adjustment is best-effort within free-tier limits and, where it cannot be guaranteed, is handled by flagging rather than silent correction.
- The feature MAY depend on the providers' existing adjustment/actions data (yfinance split/dividend actions and the `adj_close` column already fetched but unused, plus Stooq's split-adjusted bars) as the corporate-action source of truth; statistical detection backstops only the gaps it does not cover.
- Plausibility bounds for the value-domain invariants mirror the spirit of the existing value-composite backstop; the one operator-facing threshold (the **10%** divergence flag) is fixed in this spec; other exact bounds are implementation details to be tuned and **A/B-validated on real data before any default is changed** (per "test, don't trust reports").
- The independent reference for the harness is a price source distinct from the snapshot pipeline (e.g. a direct live/EOD quote query); the harness is a validation activity, so its independent fetch may be live and is timestamped, which does not violate the deterministic-screen contract because the screen's own figures and flags are unchanged by it.
- The 001/002 snapshot-determinism contract (same snapshot → same screen output, now including warnings) holds and is a hard constraint.
- Verification follows the operator's practice of driving the live app on real data (re-run the screen / run the harness and confirm), not trusting a generated report.
- Detection is **flag-not-exclude + demote** and the momentum-floor gate is **not added** (both resolved).
