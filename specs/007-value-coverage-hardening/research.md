# Phase 0 Research — Value Coverage & Correctness Hardening

The spec's Decisions Record already resolved the four operator-level questions
(profitability gate, min-risk ATR fallback, momentum floor default −0.20, spec
first). This document records the remaining technical decisions and rationale.
No open NEEDS CLARIFICATION items remain.

## D1 — EDGAR cache entry classification

**Decision**: Classify each cache file by inspecting its JSON, not by re-fetching
blindly:
- **fixable-stub**: `fetch_failed: true` OR empty `facts.us-gaap` (the 82-byte
  `{"facts":{"us-gaap":{}},"sic":null,...}` shape) **and** the ticker resolves to
  a CIK in SEC `company_tickers.json` **and** is classified common equity (D2).
- **non-equity-stub**: stub/empty but classified preferred/ADR/CEF/ETF (D2) — not
  re-fetched; filtered from the value universe instead.
- **partial**: has facts but is `schema_version < 3` or missing
  `dei:EntityCommonStockSharesOutstanding` / value `NEEDED_TAGS` → re-fetch.
- **complete**: schema-v3 with dei shares + value tags → leave alone.
- **not-cached**: no file → out of scope for the refresh (a separate seeding
  concern), counted and reported.

**Rationale**: Measured baseline is 530 stubs (<500 B) + 253 partial (500 B–5 KB)
out of 4,242. Re-fetching only fixable stubs/partials avoids hammering SEC for
the ~3,459 already-complete files and for instruments that will never have
facts. **Alternatives rejected**: (a) blanket re-fetch all 4,242 — slow, abusive
of SEC fair-access, rewrites good data; (b) trust the existing `fetch_failed`
flag alone — misses pre-v3 partials that have facts but no value/dei tags.

## D2 — Non-US-GAAP instrument detection

**Decision**: A small `instruments.classify(ticker, payload)` returning one of
`common_equity | preferred | adr | fund | unknown`, using layered signals:
- **Ticker shape**: a class suffix via `_`/`-`/`.` (`ALL_B`, `AHT_D`, `APO_A`,
  `AKO-B`) → preferred/secondary class.
- **SIC code** (when present in payload): `6726` (investment offices / closed-end
  funds) and ETF/trust SICs → fund.
- **Facts presence**: a name that resolves to a CIK but whose companyfacts has no
  `us-gaap` revenue/equity concepts across all history → treat as non-operating
  (fund/ADR shell) rather than a fetch failure.
- **dei entity type** when available.

A name is **common_equity** only if it is not matched by the above and has (or can
re-fetch) real us-gaap operating facts.

**Rationale**: The 530 stubs are dominated by preferred classes, ADRs (`AEG`,
`ABVEF`), and closed-end funds (`ACP`, `ADX`, `AIO`, `AFB`, `ANL`) — these have no
US-GAAP common-equity fundamentals by nature and must be *excluded*, not fetched
in a loop. **Alternatives rejected**: relying only on the ticker suffix (misses
suffix-less ADRs/CEFs like `AEG`/`ACP`); relying only on SIC (many stubs have
`sic: null`). Layering catches both. Conservative default: `unknown` stays in the
universe but is reported, so we never silently drop a real equity.

## D3 — SEC fetch etiquette for the refresh

**Decision**: Reuse `FundamentalsLoader.fetch_company_facts` (httpx) with the
existing descriptive `User-Agent`; cap throughput to ≤ 8 req/s with a small sleep,
exponential backoff on 429/5xx, resume from a progress marker, and **never**
overwrite a good (complete) payload with a worse one (write-if-better). No API key
exists or is needed.

**Rationale**: SEC fair-access guidance is ~10 req/s with a UA identifying the
caller. Idempotent/resumable matches Principle III reproducibility and survives
interruption (the earlier servers-exit-255 episode). **Alternatives rejected**:
bulk `companyfacts.zip` (gigabytes, includes everything, heavier than re-fetching
~500–780 names); parallel unthrottled fetch (risks an SEC block).

## D4 — Profitability gate (FR-005)

**Decision**: Add a hard gate using Piotroski's two profitability signals already
computed in `indicators/piotroski.py`: **operating cash flow > 0** AND **return on
assets > 0** (net income / total assets > 0). Implemented as a new gate in
`rules()` (hard-mode filter) and a line in `evaluate()`; missing inputs →
**skipped** and excluded in hard mode (consistent with the F-Score gate, which is
not fail-open). Ordered *after* the F-Score gate, *before* leverage sanity.

**Rationale**: Directly answers the OIS case (negative earnings yield, composite
0.68 from averaging) — a loss-maker is removed regardless of how its composite
averages. Using Piotroski's own profitability signals keeps the citation honest
(Piotroski 2000) and reuses tested extraction. **Alternatives rejected**:
hard-excluding any negative earnings yield (drops legitimate turnaround value the
LSV thesis sometimes targets, and double-counts what the composite already
encodes); flag-only (operator chose a gate, not a flag).

## D5 — Minimum-risk stop floor (FR-006)

**Decision**: In both `derive_levels` and the vectorized `rules()` level block,
after choosing the SMA-200 trend stop, require `entry - stop ≥ k · ATR` with
**k = 1.0**; if the chosen stop is closer than `1·ATR` to entry, fall back to the
3-ATR disaster stop. The take-profit `R` multiple then derives from the floored
risk, so a degenerate `$0.11` risk can no longer print a "3.82R" target.

**Rationale**: Fixes the OIS level math at its root (SMA just below entry → near-
zero risk) with the smallest change, preserving the SMA trailing stop where it is
genuinely beyond a floor. `k=1·ATR` ties the floor to the name's own volatility
(scale-free), consistent with the 3-ATR disaster-stop basis already in use.
**Alternatives rejected**: ATR-as-primary-stop (larger behavior change, deferred —
revisit if backtest favors it); cap/flag-only (leaves the underlying stop
degenerate). Choice recorded by the operator.

## D6 — Momentum floor default ON at −0.20 (FR-007)

**Decision**: Change `PARAMETERS["min_momentum_12_1"].default` from `-1.0` to
`-0.20`. The per-run override path (frame `attrs["min_momentum_12_1"]`, env
`SCREENER_VALUE_MIN_MOMENTUM`, UI toggle) already exists and stays. The UI toggle
flips to **default-checked** for the value strategy. Missing momentum still passes
through (fail-open). `return_12_1` must be present in the value universe frame for
the live screen (already computed in the engine row builder).

**Rationale**: Operator decision; protects against falling-knife value traps
(CTSH/EPAM/WDAY/SMPL profile) out of the box while remaining overridable.
**Alternatives rejected**: keep OFF (operator chose ON); a deeper −0.30 floor
(more aggressive than the operator selected).

## D7 — Price staleness gate: local-lag vs. delisting (FR-004)

**Decision**: Split the verdict in `_build_indicator_rows` / the data-note
assembly. A name whose last bar is > 5 sessions stale is reported as **"stale
local data — run ingest"** (and still surfaced, not silently dropped) when it is
still a member of the active liquid universe and other names are fresh; it is
labeled **"halted/suspended/delisted"** only when corroborated (e.g. absent from
the current universe seed, or stale beyond a wider delist horizon). `ingest_daily`
is extended to cover the full screened universe and retry tickers it failed, so
the lag is fixed at the source. A store-level warning fires once if *all* names
are stale (whole store behind) instead of flagging every name.

**Rationale**: AMWD/CTRA/EXAS/HOLX/APLS are actively trading; only CTLP is a
genuine delisting. The current single threshold conflates a local-feed gap with a
corporate event. **Alternatives rejected**: simply widening the 5-session
threshold (would let genuinely-frozen buyout prices like CTLP pass); removing the
gate (re-admits stale-price 52-week-high artifacts).

## D8 — Disclosure surfacing (FR-008..FR-012)

**Decision**:
- **Cheapness cut** becomes its own `evaluate()` entry (`gate: "Cheapness cut"`)
  separate from `"Value composite"`, with pass/fail vs the `composite_top_percentile`
  threshold; the composite line reverts to pure ranking context.
- **F-Score confidence**: when `f_score_evaluable < 9`, emit a `low_confidence`
  marker on the candidate (and in the gate detail) — surfaced as a UI badge.
- **Within-sector grouping/cap**: the engine attaches the sector group and the
  per-sector rank + which names the cap dropped, exposed as additive response
  fields and rendered grouped.
- **Regime-blind**: a `regime_available: bool` flag on the screen response; the UI
  shows a prominent banner when false (regime is the value strategy's master
  switch).
- **Data-quality flags**: per-candidate `data_quality_flags` (e.g.
  `negative_fcf`, `outlier_yield`) computed from existing row fields; rendered as
  badges, non-gating.

**Rationale**: Each maps 1:1 to a spec FR and to a finding from live operation;
all are additive (no breaking schema change) and pass the directive lint.
**Alternatives rejected**: gating on data-quality flags (operator framed CALM/AWR
as flags, not gates); a separate "diagnostics" endpoint (the screen response is
the single source the UI already consumes).

## D9 — Sequencing & regression safety (FR-014/FR-015)

**Decision**: Build order — (P1a) coverage refresh + classifier + non-equity
filter + staleness split; (P1b) strategy correctness (profitability gate,
min-risk floor, −0.20 default) test-first; (P2) disclosure fields + UI; then
(close) slim rebuild + value backtest regeneration + `claude-project/` re-sync +
a coverage-guard test. Each financial-logic change lands with a failing-first
test. The value backtest is regenerated last so its numbers reflect the final
gates.

**Rationale**: Coverage first means correctness/disclosure are validated on real
populated data; regenerating the backtest last avoids re-running the expensive
walk-forward more than once. Matches the operator's "spec first, then build" and
the test-first principle.
