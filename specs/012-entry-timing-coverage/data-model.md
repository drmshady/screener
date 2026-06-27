# Phase 1 Data Model: Entry-Timing & Candidate Coverage

Feature `012-entry-timing-coverage`. Entities derived from the spec's **Key Entities** and
Functional Requirements. All additions are **additive and optional** on existing models;
non-momentum strategies and default-off runs omit the new fields so output stays
byte-identical to the pre-feature baseline (SC-009).

---

## 1. EntryTimingClassification (US1)

Per-candidate result attached **only** to `midterm_52w_high_momentum` candidates (FR-023).
Carried on `Candidate.entry_timing` (Optional; `None` for other strategies / when the
overlay is not run).

| Field | Type | Notes |
|-------|------|-------|
| `state` | enum `entry_ready` \| `not_entry_ready` \| `entry_undetermined` | FR-001/003. `entry_ready` only when all six components pass and no disqualifier fires; `not_entry_ready` when ≥1 component fails or a disqualifier fires; `entry_undetermined` when a required input is missing and none has failed. |
| `components` | `EntryComponent[6]` | The six independently-reported components (below). FR-002. |
| `disqualifiers` | `Disqualifier[]` | Climax-top, huge-gap, short-lived-catalyst results (FR-022). |
| `diagnostics` | `EntryDiagnostics` | Auditable measured values (FR-004). |
| `summary` | string | Neutral, zero-directive one-liner (e.g. "near pivot, uptrend, confirming volume" / "extended >5% above pivot"). No "buy"/"sell"/"recommended" (SC-008). |

**Validation**: `state` is a pure function of `components` + `disqualifiers` (deterministic,
FR-008). A short-lived-catalyst disqualifier sets only an informational warning and does
**not** change `state` (FR-022).

### 1a. EntryComponent

| Field | Type | Notes |
|-------|------|-------|
| `name` | enum | `pivot_proximity` \| `trend` \| `volume_confirmation` \| `base_maturity` \| `base_depth` \| `not_extended` |
| `status` | enum `pass` \| `fail` \| `undetermined` | FR-002/003. |
| `value` | float \| null | The measured value backing the status (e.g. dist-above-pivot %, volume ratio, base weeks, base depth %, dist-above-SMA-200 %). |
| `reason` | string | Short neutral reason — e.g. "extended >5% above pivot", "weak-volume breakout", "immature base", "base too deep", "far above SMA-200", "insufficient data to assess entry". |

**Component pass rules** (thresholds configurable in `lib/flags.py`; defaults from spec FR-002):
- `pivot_proximity`: pass iff `0 ≤ (price − pivot)/pivot ≤ +0.05`; `> +0.05` → fail
  ("extended"); pivot/base undetectable → undetermined.
- `trend`: pass iff `price > sma_200`; SMA-200 unavailable (< 200 days) → undetermined.
- `volume_confirmation`: pass iff breakout-window volume `≥ 1.4×` 50-day avg (`≥ 1.5×`
  reported as the stronger tier); `< 1.4×` → fail; < 50 days of volume → undetermined.
- `base_maturity`: pass iff base length ≥ per-type threshold (flat ≥ 5 wk; cup /
  cup-with-handle / double-bottom ≥ 7 wk); shorter → fail ("immature base"); no base →
  undetermined.
- `base_depth`: pass iff `(base_high − base_low)/base_high ≤ 0.33` (default within the
  30–35% band); deeper → fail ("base too deep"); no base → undetermined.
- `not_extended`: pass iff `(price − sma_200)/sma_200 ≤ 0.40`; above → fail ("far above
  SMA-200"); SMA-200 unavailable → undetermined.

### 1b. Disqualifier

| Field | Type | Notes |
|-------|------|-------|
| `name` | enum `climax_top` \| `huge_gap` \| `short_lived_catalyst` | FR-022. |
| `triggered` | bool | True when its measured trigger is met. |
| `value` | float \| null | The measured trigger (e.g. +N% advance over the window; gap distance above pivot). |
| `reason` | string | "climax-top exhaustion (not entry)", "gap-extended above pivot", or the non-directive post-catalyst pullback-risk caution. |
| `forces_not_entry_ready` | bool | True for `climax_top`/`huge_gap`; **False** for `short_lived_catalyst` (warning only). |

### 1c. EntryDiagnostics (FR-004)

`pivot`, `base_type` (`flat`/`cup`/`cup_with_handle`/`double_bottom`/`none`),
`base_length_weeks`, `base_depth` (fraction), `breakout_volume_ratio`, `dist_above_pivot`
(fraction), `dist_above_sma_200` (fraction). All float|null; null when undetectable.

---

## 2. Base / Pivot (US1, FR-002a)

Produced by `indicators/base_pattern.py` for one ticker's adjusted OHLC history; reduced to
the EntryDiagnostics scalar columns on the snapshot row. **Not** persisted separately.

| Field | Type | Notes |
|-------|------|-------|
| `detected` | bool | False when no supported type meets its constraints → base-dependent components undetermined (FR-002a/003). |
| `base_type` | enum | `flat` \| `cup` \| `cup_with_handle` \| `double_bottom` \| `none`. Drives the per-type maturity threshold. |
| `pivot` | float \| null | Base high; **handle high** for cup-with-handle (FR-002). |
| `handle_high` | float \| null | Set only for cup-with-handle. |
| `base_start` / `base_end` | date \| null | Window of the most recent qualifying base. |
| `base_length_weeks` | float \| null | Length in weeks (FR-002 maturity rule). |
| `base_depth` | float \| null | `(high − low)/high` over the base (FR-002 depth rule). |
| `confidence` | float | 0–1; below a fixed cutoff → `detected=False` (high-precision stance). |

**Rule**: when multiple bases exist in the window, the **most recent qualifying** base wins
(deterministic tie-break by latest `base_end`, spec edge case).

---

## 3. GateClassification — three-tier (US2, FR-009/009a)

Per-strategy mapping, exposed by `screening/gate_tiers.py` and surfaced in strategy
metadata / `StrategyGatesPanel`. Configurable via `lib/flags.py` overrides.

| Field | Type | Notes |
|-------|------|-------|
| `strategy_slug` | string | The owning strategy. |
| `gate` | string | Gate identifier (matches the per-candidate `gate_results[].gate`). |
| `tier` | enum `essential` \| `preferred` \| `disqualifier` | FR-009. |

**Default map (`midterm_52w_high_momentum`, FR-009a)**:
- `essential`: liquidity (universe), data-integrity (feature 008), 52-week-high proximity
  (primary thesis).
- `preferred`: market regime, sector strength, relative strength.
- `disqualifier`: climax-top exhaustion, huge-gap breakout.

**Per-candidate effect** — `Candidate.skipped_gates: [{gate, reason}]` (Optional, default
`[]`): a non-pass on a **preferred** gate (when `expanded_coverage` enabled) records the
gate `skipped` + reason and demotes the candidate; carried verbatim into the advisor prompt
/ candidate detail (FR-014). **State transitions**:

| Condition | Effect |
|-----------|--------|
| essential gate fails | candidate excluded (always, regardless of toggle) — FR-011 |
| disqualifier triggers | candidate excluded / forced not-entry-ready (always) — FR-011/022 |
| preferred gate non-pass, `expanded_coverage` ON | retained, `skipped` + reason, demoted below all clean names — FR-010/012 |
| preferred gate non-pass, `expanded_coverage` OFF | candidate excluded (today's behaviour) — FR-013/SC-009 |

**Invariant (SC-004)**: across any ordered result set, no candidate with ≥1 `skipped_gates`
entry appears above any fully-clean candidate — enforced by the existing
`warning_count`/`data_suspect` sort in `_screen_from_universe`. No gate threshold changes
(FR-015).

---

## 4. CompliantUniverseRefreshState (US3, FR-016–021)

The cached Halal Terminal compliant universe plus refresh bookkeeping. Stored in the
existing `shariah_sources` table + `backend/data/manifest.json` source metadata; **no schema
change**.

| Field | Type | Notes |
|-------|------|-------|
| `source_name` | string | `halal_terminal`. |
| `last_success_at` | datetime \| null | Last successful refresh (manifest `source_as_of`); null/unreadable → treated as **due** (FR-018). |
| `refresh_interval_days` | int | **90** (was 7) — drives staleness messaging (FR-020). |
| `is_stale` | bool | True when ≥ interval elapsed without a successful refresh (FR-019) — surfaced loudly. |
| `cached_rows` | ticker[] | The compliant universe reused inside the window with zero API calls (FR-017). |

### 4a. RefreshDecision (pure, `should_refresh(...)`)

| Field | Type | Notes |
|-------|------|-------|
| `action` | enum `refresh` \| `skip` \| `stale` | Decision 4. |
| `elapsed_days` | float \| null | Calendar days since `last_success_at`. |
| `reason` | string | e.g. "within 90-day window — reusing cache", "≥90 days elapsed — refreshing", "≥90 days elapsed, no API key — serving stale". |

**Determinism (FR-021/SC-005)**: `action` is a pure function of `(now, last_success_at,
interval_days, force, key_present)`. Over a simulated year: ≤ ~4 `refresh` actions + any
forced ones; **zero** API calls on every `skip` (SC-006); `stale` surfaced 100% of the time
the window lapses without success (SC-007).

---

## Model field additions (summary)

`backend/src/models/strategy.py`:
- `Candidate.entry_timing: Optional[EntryTimingClassification] = None`
- `Candidate.skipped_gates: list[SkippedGate] = []`  (`SkippedGate = {gate: str, reason: str}`)
- New nested models: `EntryTimingClassification`, `EntryComponent`, `Disqualifier`,
  `EntryDiagnostics`.

`ScreenResult` shape is otherwise unchanged; `data_as_of` + `disclaimer` continue to ride
every response (constitution). Default-off / non-momentum runs leave the new fields at their
defaults so the serialized payload is byte-identical to the baseline (SC-009).
