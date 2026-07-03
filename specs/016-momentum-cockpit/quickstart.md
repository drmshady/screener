# Quickstart: Momentum Cockpit (016)

Local runbook + manual verification + deploy notes. Windows dev conventions (`py -3.12`,
`npm.cmd`, Next prod build for headless, no env-var-in-build).

## Prerequisites

- Backend deps installed; `py -3.12 -m pytest` green on a clean checkout of the branch.
- Frontend deps installed; `npm.cmd run test` and a `npm.cmd run build` green.

## Enable the feature locally

The cockpit board is gated by a backend flag (default OFF). Set it in the process environment
(never in a build step, never written to a file):

```powershell
$env:SCREENER_PIPELINE_ENABLED = "1"        # exposes POST /pipeline/board
# optional: $env:SCREENER_FIT_REWARD_TO_RISK_FLOOR = "1.5"   (default)
# optional directive labels (personal use, non-hosted only):
# $env:SCREENER_PERSONAL_USE_DIRECTIVE = "1"
```

Start the backend, then the frontend (prod build for headless parity). With the flag OFF the
board 404s and the home page renders today's panels — that path must stay byte-identical to 015.

## Manual verification (matches spec acceptance scenarios)

1. **Record transactions in-app** (US4 / SC-010): on the portfolio page use the
   **Record transaction** form to enter a buy, then a partial sell. Confirm the holding
   aggregates *identically* to the same rows via **Import from Sheet** (the secondary path still
   works). Correct a transaction (delete) and confirm holdings/P&L update.
2. **Win/loss** (US4 / SC-011): confirm the P&L summary card shows realized P&L + win/loss on the
   closed portion, unrealized P&L on the remaining open shares, and a portfolio total + win rate.
   Remove a quote (unpriceable ticker) and confirm graceful degradation (cost basis + flag).
3. **Available cash** (US2 / SC-003/004): enter **available cash**; confirm total capital derives
   = cash + holdings market value. Set cash low → a candidate's suggested size is capped with
   `binding_constraint: available_cash`; set cash to 0 → suggested size 0 for the same reason.
4. **Ready & fit** (US1 / SC-001/002): watch a few momentum tickers; open home → status strip
   (regime · heat · cash · N ready&fit · N attention), regime banner, heat gauge with headroom,
   the fit-ranked ready&fit list with inline sizing preview + the **cumulative-heat** line
   marking where the ceiling binds, and the sector-clustering flag.
5. **Alerts & stages** (US3): confirm "newly ready" badges + "ready for N days" counters, the
   holdings-needing-attention list, and a stage badge on screen rows / candidate detail /
   watchlist / holdings.
6. **Momentum-only UI** (SC-009): confirm home + nav show **no** value/short-term/compare entry
   points, while `py -3.12 -m pytest backend/tests/strategies backend/tests/backtests` for
   value/short-term stays green (reversibility invariant).
7. **Directive gating** (US5 / SC-006): with `SCREENER_PERSONAL_USE_DIRECTIVE` off, no directive
   verbs anywhere (Playwright lint). Toggle on (non-hosted) → optional labels appear. Confirm
   hosted mode never shows them.
8. **Graceful degradation** (SC-005): unset `SCREENER_PIPELINE_ENABLED` → home falls back to
   today's panels + links, no error.

## Test commands

```powershell
# Backend — from repo root
py -3.12 -m pytest backend/tests/pipeline backend/tests/portfolio backend/tests/contract
py -3.12 -m pytest        # full suite; value/short-term suites must stay green

# Frontend
npm.cmd run test          # Vitest: derivePipelineStage, store v6→7 migration, P&L formatting
npm.cmd run build         # prod build (headless parity)
npx.cmd playwright test frontend/tests/e2e/cockpit.spec.ts   # heat gauge, ordering, attention, 404 fallback, no-directive lint
```

## Determinism check

Run the board twice against the same snapshot + same persisted portfolio; assert identical JSON
(ties break on a stable key). Assert a flag-OFF run of the existing APIs is byte-identical to 015.

## Deploy notes (compatible with 010 hosted architecture)

- No new external data source, no baked-snapshot change, no new in-host compute. The board is a
  batch of existing single-ticker computations over the watchlist.
- Ship code-only via the existing CI path (Vercel frontend + HF backend image
  force-rebuild) as with 012/014. `SCREENER_PIPELINE_ENABLED` and
  `SCREENER_FIT_REWARD_TO_RISK_FLOOR` are **runtime env** on the backend Space; do not bake them
  into the image or any artifact.
- Hosted mode continues to force `personal_use_directive()` OFF and non-waivable — assert no
  `directive_label` is ever present in hosted responses.
- The new pipeline state key rides the existing `PUT /portfolio/state` sync; the backend passes
  it through untouched (owner blob stays opaque).
