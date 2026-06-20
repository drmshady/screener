# Phase 0 Research: Automated Daily Refresh, Realistic Levels & Smarter Sizing

All decisions resolve the NEEDS-CLARIFICATION items in the plan's Technical
Context. Each adopted numeric default for levels/sizing/fair-value is **provisional
here and finalized empirically by the US4 comparison artifact** (FR-019) on a
frozen real snapshot — consistent with the owner's "A/B every default change on
real data before applying" rule.

---

## Decision 1 — Bounded, volatility-/horizon-aware level method (US2)

**Problem (root cause).** Today
([`derive_levels`](../../backend/src/strategies/midterm_52w_high_momentum.py#L477)):
`entry = close`; the default stop is the **trend stop** = SMA-200 when it sits
below price, else an ATR stop; `take_profit = entry + R·(entry − stop)` with
`take_profit_r_multiple` default. The unrealistic-target failure is structural:
when SMA-200 is far below a name that has run up, `entry − stop` is huge, so the
R-multiple target implies an implausible move. Symmetrically a stop that far away
makes the risk distance meaningless (and US3 sizing depends on it).

**Decision.** Adopt a **bounded** derivation:

- **Entry** stays the latest close (unchanged, deterministic).
- **Stop** = the existing technical stop (structure / trend / ATR per mode) but
  the **risk distance `entry − stop` is clamped** to a documented band
  `[lo·ATR, hi·ATR]` (and additionally capped as a fraction of price for
  low-priced names). A far-below SMA-200 trend stop is pulled up to `hi·ATR`
  (still below entry); a too-tight stop is pushed to `lo·ATR`. `stop_loss > 0`
  always.
- **Take-profit** = `entry + R·(clamped risk distance)`, then **capped by a
  realistic reward ceiling**: the *min* of a volatility/horizon limit
  (≈ `ATR · √(horizon_days) · z`, the diffusion scale over the mid-term hold) and,
  **when available and trusted, the fair-value estimate** (don't target a price
  above intrinsic fair value). This bounds both distances (FR-008) and the ceiling
  (FR-009).
- **Insufficient data** (no ATR / no SMA-200 / no swing low) → an explicit
  "insufficient data" levels state, never a degenerate level (FR-010).
- A short **rationale** string states which rule set each level (e.g. "stop = 20-day
  swing low, widened to the 3·ATR risk cap; target = 2R, capped at the
  volatility/horizon ceiling"), neutral and zero-directive (FR-011).

**Rationale.** Bounding the **distance**, not the method, keeps the existing,
already-cited technical stop logic (George-Hwang/ATR/structure) intact — selection
and citations are untouched — while guaranteeing realism. Tying the reward ceiling
to volatility×√horizon is the standard diffusion scaling already used elsewhere in
the codebase (Barroso-Santa-Clara vol scaling), and the optional fair-value cap
connects US2 to US3.

**Alternatives rejected.** (a) Pure ATR bracket (drop trend/structure stops) —
discards information the owner trusts and changes the technical character of the
stop. (b) Fixed-percent stop/target — ignores volatility, the original complaint.
(c) Leaving the R-multiple unbounded but clamping only the target — the *stop*
distance would still be meaningless for sizing.

**Exact `lo`/`hi`/`R`/ceiling-z chosen in US4** (Decision 6) on real data.

---

## Decision 2 — Fair-value basis (US3, FR-018/019)

**Decision.** Compare two free, in-repo-derivable bases on real data and adopt the
more reliable/better-covered, recording the result in the comparison artifact:

- **(a) Valuation-yields composite** — reuse the existing
  [`indicators/valuation.py`](../../backend/src/indicators/valuation.py) yields
  (book/market, earnings, cashflow, sales) plus sector context already produced by
  `FundamentalsLoader.value_metrics_as_of`. Fair value ≈ price implied by
  normalizing a yield (or the composite percentile) toward a sector/peer reference.
- **(b) Simple cited intrinsic model** — a transparent, textbook model from the
  *same* point-in-time inputs (book equity, net income TTM, operating CF TTM,
  revenue TTM, shares). Candidates: **Graham number** (`√(22.5 · EPS · BVPS)`),
  **earnings-power value** (normalized earnings / required return), or a one-stage
  residual-income value. Whichever is adopted as a **new computed indicator** lands
  in `indicators/fair_value.py` with a **golden-fixture test written first**
  (Principle IV) and a citation.

Every estimate carries **provenance + freshness** (from the underlying filing
as-of) and an **availability/trust flag**; an estimate that is missing, stale, or
**out of a sane range** (e.g. wildly above/below price, negative) is flagged
**untrusted** and not used (Edge Cases, FR-016/018).

**Rationale.** Both bases are free, transparent, point-in-time, and already
sourced — satisfying Principle I and FR-018 without any paid feed. Picking
empirically (coverage × reliability) avoids guessing.

**Alternatives rejected.** Analyst price targets / paid fair-value feeds (Out of
Scope, cost + TOS). A multi-stage DCF (too many free-parameter assumptions for a
transparent, reproducible, owner-inspectable estimate).

---

## Decision 3 — Risk-per-trade sizing + an empirically-chosen conviction modulation (US3)

**Decision.** Replace pure cap-fill
([`size_position`](../../backend/src/portfolio/sizing.py#L13)) with a fixed
**backbone** plus a **modulation layer selected by investigation** — fair value is
**one candidate, not assumed**:

1. **Risk-per-trade target (backbone, fixed).** `risk_budget = f · total_capital`
   where `f` is a small documented, configurable fraction (env-overridable like
   existing flags); `target_shares ≈ risk_budget / (entry − stop_loss)` using the
   FR-007 realistic stop. Wider stop → fewer shares (SC-004). This is the
   non-negotiable fix for "fixed/cap-only over-allocates to wide-stop names" and is
   not in question.
2. **Conviction/quality modulation (investigate — adopt the best in US4).** Compare
   at least these candidate modulators on real data for sizing realism + robustness
   and adopt the most reliable, recording it in the comparison artifact:
   - **(a) Fair-value margin of safety** — with a *trusted* fair-value estimate, a
     larger margin (deeper discount) **does not reduce** and per the documented rule
     **may increase** size (up to caps); trading **above** fair value may shrink/cap
     it. (The owner's original "including use of fair price.")
   - **(b) Volatility targeting / inverse-volatility** — scale toward an equal-risk
     contribution (lower-vol names sized relatively larger), reusing the existing
     ATR/volatility inputs already in the snapshot.
   - **(c) Strategy-rank / conviction weighting** — scale by the candidate's own
     rank/score within the screen (higher-ranked → relatively larger), reusing the
     existing ranking output (no new selection rule).
   - **(d) None — risk-per-trade only** — the honest baseline the others must beat.
   Each is a documented, monotonic, deterministic rule.
3. **Cap clamp (hard upper bound).** Clamp the modulated target to the existing
   per-position and per-sector caps — never breached (FR-014/SC-004). The existing
   exposure/`aggregate_exposure` accounting is reused unchanged.
4. **Fail-open.** If the **adopted** modulator's input is missing or untrusted
   (e.g. no trusted fair value for (a)), the modulation step is skipped (risk-based
   within caps) and the rationale notes the input was not used (FR-016).
5. **Rationale** names the **binding constraint** (risk target, the adopted
   modulation, or a cap) and stays zero-directive (FR-017). Deterministic on fixed
   input.

**Rationale.** Risk-per-trade is the standard position-sizing primitive and the
guaranteed part of the fix; layering the conviction signal as an **investigated
choice** (rather than fixing it to fair value up front) directly answers the
owner's "investigate a **better** option" ask and his "A/B every default on real
data before applying" rule. Caps remain the safety ceiling regardless of which
modulator wins. Candidates (b)/(c) reuse inputs already in the snapshot, so no new
data source.

**Alternatives rejected.** Fixing the modulator to fair value without comparison
(pre-judges the investigation the owner asked for). A full mean-variance / Kelly
optimizer over the whole book (needs a covariance/edge estimate that isn't
robustly free + point-in-time, and is harder to make deterministic and
owner-inspectable than the per-name monotonic rules above) — may be noted as future
work but is out of this comparison.

**The adopted modulator, `f` default, and the exact modulation curve are all chosen
in US4** (Decision 6).

---

## Decision 4 — Backtest modeled exits & the gated re-baseline (FR-020)

**Finding.** The runner
([`backtests/runner.py`](../../backend/src/backtests/runner.py)) currently exits on
a **fixed holding horizon** (`_forward_return`, `HOLDING_HORIZON_DAYS`), **not** on
stop/target. So making the adopted levels "the single source of truth in the
backtest's modeled exits" means **adding level-driven modeled exits**, which
**moves the committed baseline**.

**Decision.** Implement deterministic intrabar modeled exits: each holding, walk
forward bar-by-bar; **stop checked before target** within a bar (conservative);
gaps handled by filling at the open when a gap jumps past a level; otherwise exit
at the horizon as today. Point-in-time inputs and seeding unchanged. Run the US4
artifact to quantify the **baseline delta**; **only if it is an improvement** do we
perform the **one-time re-baseline** of the committed `backend/data/backtests/*.json`
+ `backend/backtests/<slug>/*`, with a constitution reproducibility re-check, and
the change surfaced explicitly (never silent). Until then the backtest keeps the
old baseline.

**Rationale.** This is the Complexity-Tracking item; it preserves Principle III's
substance (no look-ahead, delisted coverage, costs, determinism) while satisfying
FR-020's single-source-of-truth requirement. Showing new levels but backtesting old
exits would itself be a transparency defect.

**Alternatives rejected.** Leave the backtest on horizon exits (violates FR-020 /
makes the curve describe a strategy the owner isn't running). Silent re-baseline
(violates Principle III + FR-020). Re-baseline before the artifact proves
improvement (violates the gate).

---

## Decision 5 — Automated daily refresh in cloud CI (US1) + **efficient data update**

**Decision.** A **GitHub Actions scheduled cron** runs after the US session close
on weekdays and drives the existing publish chain (refactored from
[`scripts/publish.ps1`](../../scripts/publish.ps1) so CI and local share one
codepath): **incremental refresh → integrity (008) → secret-scan → docker build →
push GHCR → HF Factory-rebuild REST call**. Secrets (provider keys, GHCR push
credential, HF token) live **only** in the Actions encrypted store, injected at
runtime (FR-002a/006). On any failed step it **aborts before publish/deploy**, the
last known-good snapshot stays live, and the owner is **notified** (Actions
failure notification / email). On a non-trading day or when no new completed
session exists, the job is a **documented no-op** (idempotent, FR-005).

**Efficiency (explicit owner request — "make data update efficient").** The daily
path is deliberately **incremental and minimal**:

- **Only `ingest_daily`** runs on the daily schedule (incremental prices + events +
  Shariah + fundamentals on their existing cadence). The **heavy ~90-day Stooq
  deep-history bundle is NOT run daily** — it stays on its existing quarterly
  cadence (`-FullStooq` / a separate, less-frequent scheduled job).
- **Fetch only the latest completed session's delta** — append new bars, don't
  re-download history; reuse the EDGAR slim cache (schema-versioned) and the
  events store memoization (007) so unchanged fundamentals/events are not re-fetched.
- **Skip-on-no-new-session guard** short-circuits the whole pipeline (no build, no
  push, no rebuild) so non-trading days cost ~nothing and `data_as_of` never
  regresses.
- **Cache CI layers/deps** (pip + docker build cache) and only rebuild the image
  when the snapshot actually changed, keeping each run well inside a trading-day
  gap and within free-tier minutes.

**Rationale.** Cloud CI removes the owner-machine dependency (the core US1 value)
while the incremental-only design keeps each run cheap, fast, and within free
tiers, and preserves 010's read-only-host + determinism guarantees (the host still
ingests nothing; FR-001a). Reusing the existing, already-trusted publish steps
avoids a second, drifting pipeline.

**Alternatives rejected.** (a) Re-running the full Stooq bundle daily — slow,
wasteful, unnecessary for end-of-day incremental freshness. (b) Self-hosted runner
on the owner's machine — reintroduces the manual/always-on dependency US1 removes.
(c) In-host ingest on the HF Space — violates 010's read-only-host posture and the
free-tier resource limits. (d) A bespoke scheduler service — more moving parts than
a stock GitHub Actions cron for a single daily job.

**To confirm in Phase 1/implementation:** a GitHub-hosted runner can `docker
build` + push to GHCR and POST the HF `restart?factory=true` endpoint (both are
plain HTTPS + docker, supported on hosted runners).

---

## Decision 6 — Empirical defaults via the US4 comparison artifact (FR-019)

**Decision.** All free choices above — risk-distance band `[lo,hi]·ATR`,
reward-ceiling z, R-multiple, fair-value basis (a vs b), risk-per-trade fraction
`f`, **which sizing-conviction modulator wins (fair value / inverse-vol /
strategy-rank / none)**, and the adopted modulation curve — are selected by a
**deterministic, frozen-snapshot comparison harness** reporting per-method
**realism** (degenerate rate, distribution of risk/reward distances vs
price/ATR/horizon; for sizing: dispersion of suggested sizes, cap-bind rate,
wider-stop→smaller monotonicity), **robustness** (stability across the universe),
and **reliability/coverage** (fair-value availability/trust rate, and the input
coverage of each candidate modulator), plus the **backtest-baseline delta** for the
level/exit change. The adopted default is the one the artifact justifies — **fair
value is not assumed to win the sizing modulation**; the artifact regenerates
byte-identically (SC-007).

**Rationale.** Directly encodes the owner's working rule and FR-019; keeps every
default defensible and reproducible.
