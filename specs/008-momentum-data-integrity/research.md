# Research: Strategy Defect Detection & Output Integrity (Momentum Pilot)

**Feature**: 008-momentum-data-integrity | **Date**: 2026-06-15

All NEEDS CLARIFICATION are resolved. The three operator-facing decisions were settled in `spec.md` clarifications (2026-06-15); the rest are design decisions grounded in the existing code.

---

## Decision 1 — Adjustment basis for momentum figures

**Decision**: Compute `return_12_1` and `52w_high` from a **split+dividend-adjusted** price series. The displayed entry/price is the **latest raw close** — which equals the latest `adj_close` (adjustment factor = 1 at the most recent bar), so the contract's `entry == close` coherence invariant still holds and the entry remains the true tradable price.

**Rationale**: BELFB's spurious +221% 12-1 return and inflated high come from mixing adjustment bases across the lookback. Adjusting the *windowed* figures removes the artifact; keeping the displayed entry raw avoids confusing the operator with a price their broker won't show. This is presentation/data-correctness only — no rule, default, or backtest baseline changes (FR-023; the backtest path never calls the live snapshot builder, so SC-010 holds).

**Alternatives considered**: (a) *fully adjusted incl. entry* — most internally consistent but the displayed entry can diverge from the broker's last price; rejected for operator confusion. (b) *split-adjusted only* — simplest, but leaves large cash distributions to the flagging backstop; rejected as the weaker correctness floor when the data to do better is already present.

---

## Decision 2 — Seam normalisation with zero new network calls

**Context (code-grounded)**: `backend/data/prices/stooq_parquet` carries **only** `ticker, as_of_date, open, high, low, close, volume` — **no `adj_close`** (verified). The warm yfinance store (`backend/data/prices/parquet`) carries `adj_close`. `screening/engine.py::_overlay_fresh_prices` stitches a fresh yfinance overlay onto the Stooq base but its `_OVERLAY_COLUMNS` **drops `adj_close`**, and `_compute_snapshot_rows` computes momentum on raw `close` only. Stooq daily bars are split-adjusted but **not** dividend-adjusted; yfinance `close` (auto_adjust=False) is raw. So a split or distribution between the Stooq archive cut and now produces two segments on different bases → the seam artifact.

**Decision**: 
1. Add `adj_close` to `_OVERLAY_COLUMNS` so it survives the stitch.
2. The overlay already fetches a **5-day overlap** with the Stooq tail. On overlapping `(ticker, date)` rows compute the adjustment factor `f = yfinance_adj_close / stooq_close`; take its window-stable (median) value per ticker and **back-adjust the entire Stooq segment** by `f` to put the whole history on the overlay's adjusted basis. Build `return_12_1` / `52w_high` on this unified adjusted series.
3. **Guardrail**: when the overlap is empty, `f` is unstable across the overlap (range beyond a tolerance), or a name is Stooq-only (no overlay), the series cannot be guaranteed consistent → **flag** the affected figures via the series-integrity invariant (FR-013) rather than silently correcting.

**Rationale**: Uses data already loaded (deterministic, no per-run network — preserves FR-024 and the snapshot cache model), directly repairs the BELFB seam class, and degrades to honest flagging exactly where free-tier data can't support a correct fix.

**Alternatives considered**: (a) *re-fetch full adj_close history per name from yfinance* — accurate but reintroduces per-name network on the live path (the whole reason the large-universe screen uses the Stooq archive); rejected. (b) *statistical-only seam detection* — kept, but only as the backstop in Decision 3, not the primary basis.

---

## Decision 3 — Corporate-action source of truth

**Decision**: Corporate-action knowledge comes from the providers' adjustment data — the `adj_close/close` ratio curve already present in the warm store (a step in the ratio = a split/dividend), plus yfinance split/dividend actions where the harness needs explicit events. Purely-statistical single-session-jump detection is a **backstop only** for gaps the feed misses; a move explained by a known action does **not** raise a flag (FR-015).

**Rationale**: Matches the spec clarification and Principle I (point-in-time, source-tagged). The ratio curve is free and already cached; statistical detection alone would false-positive on legitimate adjusted moves.

**Alternatives considered**: paid corporate-actions feed — out of free-tier scope (Assumptions); rejected.

---

## Decision 4 — Share-class integrity

**Decision**: The series-integrity / identity invariant verifies a candidate's price series and its fundamentals join resolve to a **single share-class ticker** (no BELFA price joined to BELFB fundamentals or vice-versa). A detected cross-class join flags the candidate (FR-014). Implementation checks the resolved ticker used for the price group against the ticker used for the EDGAR/profile lookup.

**Rationale**: BELFA/BELFB trade at different prices; a wrong-class join yields incoherent figures that internal coherence checks might not catch on their own.

---

## Decision 5 — Independent reference for the offline cross-check

**Decision**: A **free-tier third-party quote vendor outside the snapshot pipeline**, behind a small `IndependentQuoteProvider` interface (mirrors `PriceProvider`). **Primary: Finnhub** — `/quote` gives current price; `/stock/metric?metric=price` exposes the 52-week high — both fields the cross-check needs (FR-010). **Fallback: Alpha Vantage** `GLOBAL_QUOTE` (price; 52-week high derived where unavailable). The provider is imported **only by the harness**, never by any live screen path. The API key is read from `SCREENER_INDEPENDENT_QUOTE_API_KEY` at process start and is **never written to any file** (per the project's key-handling rule). No paid feed is introduced.

**Rationale**: Finnhub/Alpha Vantage are different vendors from Stooq and yfinance, satisfying true independence (FR-009); both have free tiers whose TOS permit personal-use display. The interface keeps the vendor swappable and keeps the live path provably network-free.

**Alternatives considered**: (a) *fresh Stooq quote* — same vendor family as the base; weak independence; rejected as primary. (b) *yfinance live quote* — same vendor as the overlay; shares vendor-level errors; rejected as primary.

---

## Decision 6 — CI enforcement split

**Decision**: The **seeded-defect suite** runs as a deterministic pytest under `backend/tests/integrity/` and is a **blocking CI gate** (SC-001: 100% detection, no network). The **independent cross-check** runs on demand via `scripts/run_integrity_harness.py` and is **not** a CI gate — a network outage or `UNVERIFIED` result reports but never fails an unrelated build (FR-007).

**Rationale**: Proves robustness-to-unknown-bugs in CI without flakiness from a third-party network dependency.

---

## Decision 7 — Where live series-integrity signals are computed

**Decision**: Compute lightweight series-integrity signals (dates monotonic+unique, max single-session jump, seam-consistent flag + factor, corporate-action-in-window flag, `adj_close_basis_used`) **once inside the existing per-ticker loop in `_compute_snapshot_rows`**, attached as row columns. The contract reads these columns; it performs **no** series I/O of its own at check time.

**Rationale**: Keeps the live contract a cheap, deterministic, no-network row check (FR-002, SC-005 < 5% runtime) since the per-ticker series is already in hand during snapshot construction; avoids a second pass over price history.

---

## Decision 8 — Detection runs after `rules()`, not inside it

**Decision**: The engine validates the **output** of `strategy.rules(universe)` in `_screen_from_universe`, not inside each strategy. Strategies only *declare* their contract.

**Rationale**: Keeps `rules()` unchanged (FR-023), keeps the detector strategy-agnostic (FR-001), and means the same engine validates momentum now and the value backstop (FR-006/SC-009) with no per-strategy engine code.

---

## Decision 9 — Plausibility bounds (deferred, A/B-validated)

**Decision**: The one operator-facing threshold — **10% divergence** — is fixed by the spec. Other exact bounds (the `return_12_1` plausibility ceiling, score-reproduction tolerance, seam-factor stability tolerance, single-session-jump threshold) are **implementation defaults tuned and A/B-validated on the real 2026-06-12 snapshot before being locked**, per the operator's "test, don't trust reports" practice. Initial defaults mirror the value-composite backstop's spirit (e.g. reject `|return_12_1|` implying >~10x over 11 months) and are recorded in `contracts/momentum-contract.md`.

**Rationale**: Bounds that are too tight cause false positives (violates SC-002/FR-005); too loose miss defects. They must be calibrated against real data, not guessed.
