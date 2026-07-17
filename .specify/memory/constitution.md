<!--
SYNC IMPACT REPORT
==================
Version change: 1.1.0 → 1.2.0
Bump rationale: MINOR. Re-scopes (does not remove) the personal-use directive
exception in Principle V so it keys on whether directive output can reach a
THIRD PARTY, rather than on whether the compute happens to be hosted. A
single-owner, access-gated hosted instance whose output reaches only its owner
now qualifies for the same narrow, flag-gated exception. The default no-advice
boundary is unchanged and remains non-waivable for any multi-user, shared, or
third-party-exposed instance; all disclosure obligations are preserved.

Driver: feature 018-daily-portfolio-brief. The owner's deployment is hosted
(feature 010) but single-user and access-gated to one allowlisted email, so its
output never reaches a third party. The prior "evaporates when hosted" condition
blocked the safe single-owner case for the wrong reason; this amendment ties the
boundary to the actual risk (third-party exposure).

Modified principles (v1.2.0):
- V. User Safety, Risk Disclosure & No-Advice Boundary — evaporation condition
  changed from "shared, hosted, multi-user, or otherwise redistributed" to
  "multi-user, shared, sold, or output otherwise exposed to any third party
  (whether compute is local or hosted)"; added a single-owner access-gate
  requirement for hosted deployments. Flag-gated + OFF by default + full
  disclosure preserved.

Template / doc propagation (v1.2.0):
- ✅ .specify/templates/*.md — no principle-driven section changed; no edits.
- ⚠ CLAUDE.md / feature 010 — the 010 summary states hosted mode forces
  personal_use_directive() OFF and non-waivable (FR-009). That remains the
  DEFAULT but is no longer absolute for a single-owner access-gated host:
  feature 018's plan MUST implement an explicit single-owner-gated directive
  carve-out (still flag-gated, still access-gated) rather than a blanket
  hosted force-off. Flagged for the 018 plan's Constitution Check.

Follow-up TODOs (v1.2.0):
- Amendment procedure requires review by a maintainer who is not the author;
  for this single-operator repo the owner records acceptance in the 018 plan.

--- Prior report (v1.1.0) ---
Version change: 1.0.0 → 1.1.0
Bump rationale: MINOR. Adds materially expanded, bounded guidance to an
existing principle (V). It does NOT remove or weaken the default no-advice
boundary — that remains the non-negotiable default; the amendment only carves
a narrow, flag-gated, auto-reverting exception for single-user personal use.
No principle removed or redefined, so not MAJOR; more than wording, so not
PATCH.

Driver: feature 004-advisor-prompt-export needs to (optionally) emit directive
personalized guidance for the single owner of this personal-use tool. Per
governance, relaxing a NON-NEGOTIABLE principle requires an amendment; this is
that amendment.

Modified principles:
- V. User Safety, Risk Disclosure & No-Advice Boundary — added the
  "Personal-use directive exception" (flag-gated, OFF by default, evaporates
  for any shared/hosted instance; disclosure obligations preserved).

Added sections:
- (none — existing principle expanded; Data/Compliance bullet updated to match)

Removed sections:
- (none)

Templates requiring updates:
- ✅ .specify/templates/plan-template.md — generic "Constitution Check"
  references the constitution by file; still valid, no edits required.
- ✅ .specify/templates/spec-template.md — no mandatory section changed; no
  edits required.
- ✅ .specify/templates/tasks-template.md — no principle-driven task category
  changed; no edits required.
- ✅ CLAUDE.md — delegates to the active plan; feature 004 plan already
  records the conditional gate; no edits required.
- ✅ specs/004-advisor-prompt-export/plan.md — Constitution Check marks
  Principle V CONDITIONAL pending this amendment; now satisfied (the flag may
  legitimately be enabled for personal use; default stays OFF).

Follow-up TODOs:
- (none)

--- Prior report (v1.0.0) ---
Initial ratification. All five principles new. Product scope locked at v1:
short-term + mid-term US-equity screening only; pure long-term buy-and-hold
deferred to a future amendment.
-->

# Stock Screener Constitution

US-equity stock screener for short-term and mid-term investing, built on
reliable, peer-reviewed strategies and high-integrity market data.

**Horizon definitions** (used throughout this document):

- **Short-term**: intraday to a few weeks (day-trading and swing setups).
- **Mid-term**: roughly 1 to 12 months (position trading, trend-following,
  momentum, earnings-revision plays).

Pure long-term buy-and-hold (multi-year) screens are out of scope for v1 and
require a constitutional amendment to add.

## Core Principles

### I. Data Integrity & Provenance (NON-NEGOTIABLE)

Every price, fundamental, corporate-action, and reference datapoint used by a
screen, indicator, or backtest MUST be sourced from a licensed or
publicly-authoritative provider (e.g., SEC EDGAR, exchange feeds, or a vendor
whose terms of service permit the displayed use) and MUST carry an
identifiable source tag plus an as-of timestamp. Historical data MUST be
point-in-time: corrections, restatements, splits, and dividends are applied as
they became known, never with hindsight. Delisted and acquired tickers MUST be
retained in the historical universe so screens and backtests do not silently
survivor-bias their results.

**Rationale**: The entire product trustworthiness rests on whether the
numbers it shows match a verifiable source. Bad data poisons strategies and
silently misleads users about real-world performance.

### II. Strategy Transparency & Peer-Reviewed Foundations

Every shipped screen or strategy MUST reference a published, widely-recognized
methodology (academic paper, book, or established practitioner framework)
appropriate to a short- or mid-term horizon — for example momentum factor
(Jegadeesh & Titman), 52-week-high breakout (George & Hwang), Minervini-style
VCP and stage analysis, CAN SLIM (O'Neil), post-earnings announcement drift
(Bernard & Thomas), relative-strength sector rotation, ATR-based volatility
breakouts, or RSI mean-reversion. The strategy MUST encode its rules
deterministically with all parameters and thresholds documented in code. Black-box models, undisclosed ML weights, or
strategies whose rules cannot be stated in a short rule list are PROHIBITED
in v1. Any user-tunable parameter MUST have its default value and permitted
range documented in the strategy definition.

**Rationale**: Users must be able to understand *why* a stock matched a
screen, and reviewers must be able to audit *what* the screen actually does.
"Reliable trusted strategies" only holds if every rule is inspectable.

### III. Reproducible Backtesting & Bias Avoidance (NON-NEGOTIABLE)

Backtests MUST use point-in-time data with no look-ahead leakage (no future
earnings, no future index membership, no restated fundamentals applied
retroactively), MUST include delisted tickers, MUST model realistic
transaction costs and slippage, and MUST report metrics across at least one
full market cycle (≥ 10 years where data is available) so that mid-term
strategies are evaluated across both trending and choppy regimes, not just
the most recent bull run. A backtest run on a given data snapshot MUST
produce identical results on a re-run by another contributor using the same
snapshot; non-determinism (random seeds, wall-clock-dependent paths) MUST be
either eliminated or seeded and recorded.

**Rationale**: Backtest results drive user decisions. Look-ahead and
survivorship bias are the two failure modes that make pretty equity curves
useless in production; the constitution forbids them by name.

### IV. Test-First for Financial Logic

Every indicator (RSI, MACD, SMA/EMA, ATR, F-Score components, valuation
multiples, etc.) and every screening rule MUST ship with unit tests that
assert numerical correctness against known fixtures — either hand-calculated
golden numbers or values reproduced from the cited source. Tests MUST be
written before or alongside the implementation, MUST fail before the
implementation lands, and MUST run in CI on every change to the implementing
file. A pure refactor of an indicator MUST not change its test outputs by
more than the documented numerical tolerance.

**Rationale**: An RSI that is wrong by 3 points or a P/E that uses the wrong
denominator silently corrupts every downstream screen. The only defensible
safety net is fixture-anchored tests that future contributors cannot
accidentally break.

### V. User Safety, Risk Disclosure & No-Advice Boundary

The app is an information and screening tool, NOT personalized investment
advice. Every screen result, watchlist export, and shareable view MUST
display: the strategy's name and citation, the timeframe it targets
(short-term or mid-term), the assumptions it makes, the as-of date of the
underlying data, and a plain-language non-advice disclaimer. By default,
output language MUST use neutral framing ("screen match", "candidate for
further research") and MUST NOT use directive language ("buy", "sell",
"recommended"). User credentials, brokerage tokens, and any
personally-identifiable information, if stored at all, MUST be encrypted at
rest and never logged in plaintext.

**Personal-use directive exception** (added v1.1.0; re-scoped v1.2.0): When the
app serves a single identified owner about their own decisions AND its directive
output is NOT redistributed, shared, sold, or exposed to any third party,
directive personalized guidance (e.g. take/pass/size calls, position-level
reasoning) MAY be produced for that single owner. Hosting the tool for the
owner's own use does NOT by itself forfeit this exception, provided access is
gated to the single owner and no third party can receive the output. This
exception is NARROW and conditional:

- It MUST be gated behind an explicit operator flag that is OFF by default
  (the implementing flag is `SCREENER_PERSONAL_USE_DIRECTIVE`). When the flag
  is off, the neutral no-directive default above fully applies.
- For any HOSTED deployment, an enforced single-owner access gate (e.g. a
  single-email allowlist fronting all data routes) MUST be in place so that
  only the owner can receive the directive output; without such a gate the
  neutral default applies unconditionally.
- Even when enabled, every directive output MUST still carry the strategy
  citation, the data as-of date, and the non-advice / limitations disclosure
  (including any failing bias check, e.g. survivorship).
- The exception EVAPORATES automatically the moment the instance becomes
  multi-user, shared, sold, or its output is otherwise exposed to any third
  party — regardless of whether the compute is local or hosted. In any such
  context the neutral no-directive boundary is mandatory and non-waivable, and
  the "licensed/permissive provider" data-source obligations re-attach.
- This exception applies ONLY to first-person guidance for the tool's single
  operator about their own decisions; it is never a license to present
  directive output to any third party.

**Rationale**: For a shared or multi-user tool, talking like a financial advisor
invites both legal risk and user harm, so the neutral boundary is the
non-negotiable default. But a private tool advising its own single owner about
their own money is not regulated advice; forbidding the owner from asking their
own tool for a direct answer serves no one. The dangerous case is directive
output reaching a THIRD PARTY — not the mere fact that the compute runs on a
server. A single-owner, access-gated hosted instance is functionally the same
private case as a laptop, so v1.2.0 ties the boundary to third-party exposure
rather than to hosting. The flag + single-owner access gate + automatic
reversion keep the dangerous case closed while permitting the safe, private
case whether the owner runs the tool locally or hosts it for their own use.

## Data, Compliance & Performance Standards

**Universe (v1)**: US-listed common equities on NYSE, NASDAQ, and NYSE
American. ETFs, ADRs handled as common equities only when their fundamentals
are well-defined. OTC pink-sheet names, cryptocurrencies, options, and
futures are out of scope for v1 and require a constitutional amendment to
add.

**Data sources**: Allowed sources are SEC EDGAR (filings/fundamentals),
exchange or vendor feeds the project holds rights to redistribute, and
end-of-day data from providers whose TOS permit the displayed use. Scraping
of sites that prohibit it in their TOS is PROHIBITED. Caching MUST respect
each provider's redistribution and retention terms.

**Freshness SLAs**:
- End-of-day screens (mid-term mode): data MUST be no more than 1 trading
  day stale.
- Intraday screens (short-term mode): quote lag MUST be ≤ 60 seconds during
  US market hours where the data tier supports it; if only delayed data is
  available, the delay MUST be displayed prominently on every screen view.
- Fundamentals: refresh within 2 business days of the underlying 10-Q / 10-K
  becoming available on EDGAR.

**Performance targets**:
- Full-universe screen execution (≈ 6,000 tickers after primary filters):
  p95 ≤ 10 s for end-of-day strategies, p95 ≤ 2 s when results are served
  from cache.
- Single-ticker fundamentals/charts page: p95 ≤ 1.5 s.

**Compliance**:
- No personalized recommendations and no "buy/sell" labels by default. The
  sole exception is the single-user, personal-use directive mode defined in
  Principle V, which is OFF by default and remains non-waivable for any
  multi-user, shared, sold, or third-party-exposed instance. A single-owner,
  access-gated hosted instance (output reaching only the owner) may enable it.
- Every page that displays screen output MUST carry a disclaimer that the
  content is for informational purposes only and is not investment advice.
- No claim of past or future performance may be displayed without the
  backtest methodology link adjacent to it.

## Development Workflow & Strategy Review

**Adding or changing a strategy** requires a PR that includes:
1. Citation of the source methodology (paper, book chapter, or recognized
   practitioner writeup) with a permanent link or full reference.
2. A deterministic rule definition: inputs, thresholds, ranking expression,
   timeframe, and rebalance cadence — all in code, all in one file per
   strategy.
3. A backtest run on the project's reference data snapshot, with results
   committed to the strategy's directory: equity curve, drawdown,
   turnover, hit-rate, and the bias-check checklist (look-ahead /
   survivorship / data-revision / cost model — each item ticked with a
   one-line justification).
4. Reviewer sign-off from a maintainer confirming the rules in code match
   the cited methodology.

**Adding or changing an indicator** requires fixture-anchored unit tests per
Principle IV. Refactors MUST preserve numerical outputs within the
documented tolerance for that indicator.

**Every PR** MUST identify which principles it touches. PRs that appear to
relax a NON-NEGOTIABLE principle (I or III) MUST be rejected unless they
include a constitutional amendment in the same series.

**Quarterly strategy review**: maintainers re-verify, once per calendar
quarter, that each shipped strategy's code still matches its cited rules and
that its backtest is reproducible on the then-current data snapshot. Drift
findings are filed as issues and resolved before the next release.

## Governance

This constitution supersedes all other practices in this repository. Where a
template, README, agent instruction, or external document conflicts with the
constitution, the constitution wins until amended.

**Amendment procedure**: a PR that edits this file MUST (a) update the
Sync Impact Report comment at the top, (b) increment the version per the
semver rules below, (c) propagate any changes to dependent templates
(`.specify/templates/*.md`) and runtime guidance docs (`CLAUDE.md`), and
(d) be reviewed by a maintainer who is not the author.

**Versioning policy**:
- MAJOR: removal or backward-incompatible redefinition of a principle, of a
  NON-NEGOTIABLE rule, or of the governance procedure.
- MINOR: addition of a new principle or section, or materially expanded
  guidance within an existing principle.
- PATCH: clarifications, wording fixes, typo corrections, non-semantic
  refinements.

**Compliance review**: every PR review MUST confirm data sourcing rules
(Principle I), strategy transparency (II), backtest discipline (III),
indicator test coverage (IV), and user-facing disclosure (V) are intact.
Violations block merge unless explicitly justified under the plan's
Complexity Tracking section with a written rationale.

**Runtime guidance**: `CLAUDE.md` and the active feature plan under
`specs/` are the authoritative sources for technology stack, structure, and
implementation details. This constitution governs *what must be true*; those
documents govern *how it is built*.

**Version**: 1.2.0 | **Ratified**: 2026-06-10 | **Last Amended**: 2026-07-08
