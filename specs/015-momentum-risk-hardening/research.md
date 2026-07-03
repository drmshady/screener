# Phase 0 Research: Momentum Risk & Validation Hardening

All decisions preserve the current live-screen output by default and stay within the
existing app structure and deployment (baked read-only snapshot + BFF proxy + `SCREENER_*`
env flags). No new subsystem, router, external data source, or auth surface is introduced.

---

## Decision 1 — Rebalance cadence for the committed backtest (US1 / FR-001)

**Decision**: Move the *committed* momentum backtest off the annual, January-31-only cadence
(`runner._annual_as_of_dates`) to a **calendar-driven periodic cadence** (monthly or
quarterly month-end rebalance dates), reusing the exact approach already proven in
`backtests/study.py` (`rebalance_dates(trading_days, start, end, freq)` → month-ends, quarter
subset for mid-term). Cadence is a knob (`SCREENER_BACKTEST_REBALANCE=Q|M`, default `Q` for
the 126-day mid-term horizon). Entries occur across multiple dates per year; entry price is
the **next day's close/open after the signal date** (point-in-time, no look-ahead).

**Rationale**: `study.py` already demonstrates this is correct and reproducible on the frozen
snapshot; promoting its cadence logic into the served path is low-risk reuse, not new
invention. Quarterly rebalancing matches the strategy's ~6-month holding period without
starving it of trades, and multiplies the ~80-trade annual sample by roughly an order of
magnitude (SC-001).

**Alternatives considered**: (a) keep annual, add more years — rejected: still
single-calendar-date conditioned and sample stays tiny; (b) event-driven rebalance on new
52w-high — rejected: changes selection semantics (would look like a rule change) and
complicates point-in-time bookkeeping. Overlapping holds under higher cadence are handled by
the per-trade forward-return scoring already in the runner (each entry scored independently;
no compounding double-count), matching `study.py`.

---

## Decision 2 — Trading-cost / slippage model (US1 / FR-002, Principle III)

**Decision**: Apply a single, **disclosed per-side cost in basis points**, deducted from each
trade's return, defaulting to the value already used by `study.py` (`COST_ROUNDTRIP = 0.002`
= 0.10%/side, 0.20% round-trip). Knob: `SCREENER_BACKTEST_COST_BPS` (per side). The
`bias_check` `costs` line flips from self-reported "not included" to "modeled: N bps/side".

**Rationale**: Principle III explicitly requires realistic transaction costs; the current
committed baseline fails its own `costs` check. A flat bps figure is transparent,
deterministic, and sufficient to move reported returns off the frictionless baseline honestly
— the spec (Assumptions) deliberately scopes out a full market-impact model.

**Alternatives considered**: spread/ADV-scaled impact model — rejected as over-engineered for
a personal single-owner tool and harder to keep deterministic; a flat bps is the honest
minimum the constitution demands.

---

## Decision 3 — Per-period trade counts + low-reliability flags (US1 / FR-003, US7 / FR-020)

**Decision**: `backtests/metrics.yearly_metric(...)` already carries a per-year trade count;
add an explicit `reliability` field (`"ok"` vs `"low_sample"`) computed by a threshold knob
(`SCREENER_BACKTEST_MIN_RELIABLE_TRADES`, default e.g. 10). Surface both the count and the
flag through `api/backtest.py` (read-only pass-through) into `WalkForwardMetricsPanel.tsx`,
which visually distinguishes thin-sample years.

**Rationale**: Honesty fix — thin years must not read as stable estimates. Zero selection
impact; purely additive presentation, consistent with the existing `coverage_notes` amber
panel already rendered.

**Alternatives considered**: hide thin years — rejected (conceals evidence, violates the
honesty intent). Confidence intervals — deferred; a clear count + flag is the legible minimum
for a solo operator (US7 legibility goal).

---

## Decision 4 — Modeled-exit vs fixed-horizon comparison + gated re-baseline (US2 / FR-004, FR-005, FR-006)

**Decision**: Reuse the runner's existing `modeled_exits=True` path (already models the same
bounded stop/target the live screen shows, conservative when both are touched in a bar).
Produce a reproducible comparison artifact (fixed-horizon vs modeled-exit, and — for US5 —
with/without the regime overlay) under `specs/015-momentum-risk-hardening/` +
`backend/backtests/comparison/`, recording total return, hit rate, avg win/loss, drawdown,
and an **adoption verdict**. The committed `midterm_52w_high_momentum.json` baseline changes
**only** if the artifact documents an improvement; either way the artifact is retained.

**Rationale**: The scaffolding exists (011-US4); this feature operationalizes the comparison
and the constitution's "no silent baseline change" rule. The decision + verdict are recorded
and reproducible (byte-identical re-run on the same snapshot).

**Alternatives considered**: silently swap to modeled exits — rejected (violates FR-006 and
Principle III governance); a 3R cap may be cutting the right tail momentum depends on, which
is exactly what the artifact is meant to reveal.

---

## Decision 5 — Trailing protective level for open holdings (US3 / FR-007, FR-008)

**Decision**: Add a third `LevelBlock` — `trailing` — to `HoldingLevels`, computed in
`portfolio/holding_levels.py` from the **chandelier-exit series already in the snapshot**
(`chandelier_exit`, 22-bar high − 3×ATR, computed in `runner._build_snapshot` and
`screening/engine`). Entry basis for the trailing view is **current price** (not average
cost), so for a winner the trailing stop can sit above the purchase price. Graceful
degradation: if current price ≤ average cost, or the chandelier value is missing, the
trailing view must **not** present a looser level than the cost-anchored stop — it degrades
to "no additional protection" / `insufficient_data`, never fabricated.

**Rationale**: The gap is presentation, not data — the input already exists. Reuses the
`_block(...)` builder and `_status(...)` logic unchanged. Neutral, zero-directive rationale
per FR-008.

**Alternatives considered**: recompute a new trailing indicator — rejected (no new data
source needed; chandelier is already the strategy's documented trailing input in
`shortterm_atr_breakout` and `study.py`).

---

## Decision 6 — Conservative sizing fallback + portfolio heat (US4 / FR-009, FR-010)

**Decision (fallback)**: Replace the `_legacy_cap_fill` branch taken when the stop is
missing/invalid with a **conservative fallback**: size from a synthetic stop distance derived
from ATR/volatility (or a fixed conservative fraction of entry) so the "least risk
information" case yields a *small* position, not the full cap. Reasoning text states a
conservative fallback was used. Knob: `SCREENER_SIZING_FALLBACK_ATR_MULT` (default chosen so
the fallback size is strictly smaller than legacy cap-fill — SC-005).

**Decision (portfolio heat)**: Add an aggregate open-risk computation in `portfolio/exposure.py`:
sum of per-position risk-to-stop across existing holdings + the proposed position, bounded by
a configurable ceiling (`SCREENER_PORTFOLIO_HEAT_CEILING`, e.g. 6% of capital, default set so
current single-position sizing is unaffected until heat actually binds). When heat binds,
`size_position` reduces shares and reports `binding_constraint = "portfolio_heat"`.

**Rationale**: The current fail-open produces the largest position exactly when risk info is
weakest — the opposite of safe. Heat is the defense against correlated momentum stops firing
together (the crash scenario). Both reuse existing `SizingRequest.holdings` /
`aggregate_exposure` inputs; no new request shape needed beyond optional knobs.

**Alternatives considered**: refuse to size without a stop — rejected (breaks backward-compat;
contracts/sizing.md does not require a stop). Correlation-weighted heat — deferred as
over-engineered; a simple sum-of-risk ceiling is the honest, deterministic first cut. Empty/
single-holding portfolios behave sensibly (heat = the one position's risk).

---

## Decision 7 — Regime-aware risk budget overlay (US5 / FR-011)

**Decision**: Add an **opt-in** overlay (`SCREENER_REGIME_RISK_BUDGET=0` default OFF) that
multiplies `risk_per_trade_fraction()` by a regime scale: `1.0` in a favorable regime, a
reduced factor (`SCREENER_REGIME_RISK_BUDGET_UNFAVORABLE`, e.g. 0.5) in an unfavorable one,
using the **existing** `regime/calculator.py` signal. When the regime is unavailable it fails
open to `1.0` (never errors). When the flag is OFF, sizing is **byte-identical** to today.
Adopted as a default only if the strengthened backtest (Decision 4 artifact) shows a
documented drawdown improvement (US4 "test, don't trust" rule).

**Rationale**: Regime is currently display-only and vol-scaling only reorders rank; this is
the natural, cited defense (Faber 2007-style) against the 2020–2022 momentum crash. Gating on
real data respects the project rule to A/B before applying.

**Alternatives considered**: a regime *master switch* that blocks new entries (as in
`study.py`'s `regime_gated` variant) — kept as a measured comparison variant but not adopted
into live sizing here; scaling the risk budget is the softer, opt-in change that stays within
sizing rather than touching selection.

---

## Decision 8 — Honest level rationale + reward ceiling (US6 / FR-012, FR-013)

**Decision**: In `strategies/levels.py`, make the `rationale` name the constraint that
**actually set** the stop. Today it always credits `stop_rule` (e.g. "200-day SMA trend
stop") even when `risk_cap`/`risk_floor` in `bounds_applied` moved the number. Fix: when
`"risk_cap"` (or `"risk_floor"`) bound the risk distance, attribute the stop to the ATR risk
cap in the rationale. For the reward ceiling: the volatility-horizon term
(`reward_ceiling_z * atr * sqrt(horizon_days)`) is currently unreachable at the default
horizon (126–180 days makes it huge). **Recalibrate** `reward_ceiling_z` / horizon basis so
it can bind within the holding horizon, **or** omit the volatility-horizon basis from the
rationale when it cannot bind, so nothing decorative is presented as a constraint. Also: in
structure-stop mode with a missing swing low, keep returning `insufficient_data` (already the
behavior) rather than silently relabeling the ATR fallback as a structure stop.

**Rationale**: Pure honesty, changes no number materially. The owner is currently told the
stop came from a rule that did not set it and told there's a ceiling that can never bind.

**Alternatives considered**: leave as-is — rejected (mislabels what the owner sees, the
explicit finding). Recalibrating vs omitting the ceiling is decided by whether a calibrated z
produces a genuinely binding-in-range ceiling on real snapshot rows (verified in test-first
fixtures).

---

## Decision 9 — Presentation & workflow legibility (US7 / FR-017…FR-021)

**Decision**: Surface the new facts on the existing surfaces, additively and non-directively:
candidate card shows **risk distance (entry−stop)** and **reward-to-risk** alongside stop and
target; holding detail shows the **three** protective levels (original plan / current
condition / trailing) with at-a-glance status distinguishing a gains-protected trailing stop;
sizing result shows the **binding constraint** and remaining **portfolio-heat headroom**; the
walk-forward panel visually flags thin-sample years. All widen existing Zod/TS types and pass
the Playwright no-directive + `data_as_of`/`disclaimer` lints. Every surface degrades
gracefully when a level/heat/regime value is unavailable.

**Rationale**: Facts buried in dense tables don't change decisions; a solo operator
validating by driving the live app needs the risk picture legible and fast to scan (US7).
Additive fields keep the BFF proxy and frontend contract backward-compatible.

**Alternatives considered**: a new dedicated "risk" page — rejected (adds navigation and
clutter; the review asks for legibility on the surfaces already used).

---

## Deployment & determinism (cross-cutting — the explicit ask)

- **Baked-artifact compatibility**: the strengthened backtest is run **locally** via
  `python -m backend.src.backtests.runner --strategy midterm_52w_high_momentum`, the
  regenerated `backend/data/backtests/midterm_52w_high_momentum.json` is committed, and shipped
  through the **existing** `scripts/publish_chain.ps1` / daily-refresh `force_rebuild` path. The
  hosted backend continues to serve the JSON read-only via `GET /strategies/{slug}/backtest`
  and never runs the heavy backtest (matches 010 hosted-mode "no heavy in-host ingest").
- **Flag defaults preserve output**: every knob defaults to today's behavior, so a code-only
  deploy (no re-baked artifact, flags unset) is byte-identical to production now. Only an
  explicit knob change or a gated re-baseline moves numbers.
- **Determinism**: cadence, cost, heat, trailing, and regime-scale are all pure functions of
  the frozen snapshot + config; same snapshot in → byte-identical numbers out (FR-015, SC-003).
- **No secrets, no new provider**: nothing in this feature reads or writes a secret or adds an
  external feed; the secret-scan release check is unaffected.
