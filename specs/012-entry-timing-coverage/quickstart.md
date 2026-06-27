# Quickstart: Entry-Timing & Candidate Coverage (feature 012)

Local single-user dev runbook for the three slices. Windows conventions per
[[windows-dev-runbook]]: `py -3.12`, `npm.cmd`, Next prod-build for headless. All three
features default **OFF/at-current-behaviour** — the baseline screen is byte-identical until
you opt in (SC-009).

## Prerequisites

- Backend deps installed (`py -3.12 -m pip install -r backend/requirements.txt`).
- A warm snapshot (run `py -3.12 scripts/ingest_daily.py` once) so the momentum screen has
  candidates to annotate.
- Run pytest from the **repo root** (per [[deploy-010-gotchas]]).

## US1 — Entry-timing overlay

The overlay attaches only to `midterm_52w_high_momentum`. It is computed from the existing
snapshot; **bump the Stooq snapshot cache version** when the base/pivot columns are added so
old cached snapshots are invalidated (per [[snapshot-cache-version-gotcha]]) — otherwise the
new columns are silently absent.

```bash
# Run a momentum screen; every candidate carries `entry_timing` (state + 6 components +
# diagnostics). Default: annotate all (entry_ready_only OFF).
# Narrow to entry-ready names only:
#   screen request parameters: { "entry_ready_only": true }

# Tune thresholds without code edits (lib/flags.py knobs), e.g.:
set SCREENER_ENTRY_PIVOT_MAX_EXT=0.05
set SCREENER_ENTRY_VOL_RATIO_MIN=1.4
set SCREENER_ENTRY_BASE_DEPTH_MAX=0.33
set SCREENER_ENTRY_SMA200_EXT_MAX=0.40
```

Verify: each candidate's six component values reproduce the spec thresholds from the exposed
diagnostics (SC-001); toggling `entry_ready_only` yields a strict, repeatable subset
(SC-002); no directive language appears (SC-008). The new `indicators/base_pattern.py` must
be **golden-fixture green before** the overlay consumes it (Principle IV).

## US2 — Expanded coverage (three-tier gates)

```bash
# Default OFF → output identical to today. Enable per-screen:
#   screen request parameters: { "expanded_coverage": true }
```

With it ON, momentum candidates that fail/cannot-evaluate a **preferred** gate (market
regime, sector strength, relative strength) are retained, tagged `skipped_gates` + reason,
and demoted below all clean names. Essential failures (liquidity, data-integrity, 52w-high
proximity) and disqualifier triggers (climax-top, huge-gap) are **always** excluded. The
three-tier map shows in the strategy gates panel. Verify SC-003 (count rises; added names
fail only preferred gates), SC-004 (clean always above skipped), SC-009 (default-off
identity).

## US3 — Quarterly Shariah refresh (90-day cadence)

```bash
# Routine ingest now consults the cadence guard before any Halal Terminal API call.
# Inside the 90-day window: cache reused, ZERO API calls.
py -3.12 scripts/ingest_daily.py

# Force a refresh now (bypass the 90-day gate; needs HALAL_TERMINAL_API_KEY):
py -3.12 scripts/ingest_daily.py --force-shariah

# Skip the Shariah refresh entirely:
py -3.12 scripts/ingest_daily.py --skip-shariah
```

Behaviour: < 90 days since last success → skip (no call); ≥ 90 days + key → refresh; ≥ 90
days + no key → reuse cache + loud "compliance data stale" warning; missing timestamp →
treated as due. The manifest `refresh_interval_days` for `halal_terminal` is **90** so
staleness messaging matches. The API key is read for presence only, never written to a file
([[api-keys-never-write]]).

## Tests

```bash
py -3.12 -m pytest backend/tests/indicators/test_base_pattern.py        # US1 indicator (test-first)
py -3.12 -m pytest backend/tests/screening/test_entry_timing.py         # US1 overlay
py -3.12 -m pytest backend/tests/screening/test_gate_tiers.py           # US2 coverage + ordering
py -3.12 -m pytest backend/tests/shariah/test_refresh_cadence.py        # US3 cadence (injected clock)
# Frontend: zero-directive lint + entry-timing/skipped-gate rendering + default-off identity
cd frontend && npm.cmd run test
```

Expect the full backend + frontend suites green on a clean checkout; momentum stays primary
and the value strategy's existing tests still pass (per [[momentum-primary-value-postponed]]).
