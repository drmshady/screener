# Quickstart: Portfolio Position Cards & Transaction Separation (019)

Local dev runbook for building and verifying this feature. Backend = Python 3.12 / FastAPI;
frontend = Next.js 15. No new services, stores, or migrations.

## 1. Backend — instruction mapper (test-first, Constitution IV)

```powershell
# Write golden-fixture tests FIRST (must fail before implementation lands):
#   backend/tests/portfolio/test_instruction.py
#   - sell: current_condition.status == "stop_breached"
#   - trim: near stop (|distance_to_stop_pct| <= 0.03) OR heat_headroom_pct <= 0
#   - hold: healthy / target_reached / gains_protected
#   - insufficient: levels_state == "insufficient_data" -> no verb, status_label set
#   - determinism: same inputs -> identical InstructionBlock
cd E:\screener\backend
pytest tests/portfolio/test_instruction.py -q          # RED first

# Implement the pure mapper + wire into /portfolio/holdings:
#   src/portfolio/instruction.py         (derive_instruction)
#   src/models/portfolio.py              (InstructionBlock + directive_enabled, additive)
#   src/api/portfolio.py                 (attach per-holding instruction in _assemble_holdings path)
#   src/lib/flags.py                     (shared single-owner carve-out predicate; card gate)
pytest tests/portfolio tests/api -q                    # GREEN
```

Verify additive/back-compat + neutral default:

```powershell
# Neutral default (carve-out OFF): no directive verb in the response
$env:SCREENER_PERSONAL_USE_DIRECTIVE=""; $env:SCREENER_MULTI_USER=""
pytest tests/api/test_portfolio_holdings.py -q

# Carve-out ON (single-owner hosted parity with feature 018):
$env:SCREENER_PERSONAL_USE_DIRECTIVE="1"; $env:SCREENER_OWNER_SECRET="dev-secret"
pytest tests/api -q -k instruction
```

## 2. Frontend — page split + cards

```powershell
cd E:\screener\frontend
# New:      src/app/transactions/page.tsx  (relocate ImportTransactions + record form + ledger + realized detail + Remove)
# Restruct: src/app/portfolio/page.tsx     (PositionCard grid + RealizedSummary; remove transaction UI)
# New:      src/components/PositionCard.tsx, src/components/RealizedSummary.tsx
# Edit:     src/components/AppShell.tsx     (add Transactions nav link)
# Edit:     src/lib/api.ts                  (optional instruction + directive_enabled on holdings schema)
npm run test        # Vitest: card render + degrade paths
npm run lint
```

## 3. End-to-end verification

```powershell
# Backend
cd E:\screener\backend; uvicorn src.api.app:app --reload
# Frontend (separate shell)
cd E:\screener\frontend; npm run dev
```

Manual checks (map to Success Criteria):
- **SC-001/US1**: each open holding shows a card with status, stop, target, news/events, sentiment,
  and an instruction (Hold/Trim/Sell when the carve-out is on; neutral status otherwise).
- **SC-002/US3**: record a full sell → its card vanishes from `/portfolio`; its rows remain on
  `/transactions`.
- **SC-003/US2**: `/portfolio` has a one-click link to `/transactions`, which holds all
  record/import/ledger/delete controls; `/portfolio` has none.
- **SC-004/US4**: `RealizedSummary` win/loss counts, win rate, and total realized P&L reconcile with
  the ledger; empty state reads "No realized history yet".
- **SC-005**: cards + levels + instruction render before per-card sentiment/news finish loading.
- Edge: capped sentiment → template narrative (not blank/error); missing levels → "Levels
  unavailable" (card still renders); repurchase → new card.

## 4. Playwright gates (must pass)

```powershell
npm run test:e2e -- portfolio transactions
# - no-directive lint on /portfolio with directive_enabled=false
# - data_as_of + disclaimer present
# - transaction controls absent from /portfolio, present on /transactions
```

## 5. Determinism & disclosure invariants

- `derive_instruction` is pure; no wall-clock/random inputs. Same snapshot ⇒ same instruction.
- `data_as_of`/staleness + disclaimer ride every card and the summary (FR-012).
- No new indicator, gate, sizing, or backtest baseline touched (FR-013) — momentum tests + value
  tests stay green.
