# Contract: `POST /pipeline/board`

Batch, momentum-only fit board. New router `backend/src/api/pipeline.py`, registered in
`api/app.py` behind the existing owner-secret dependency + CORS pin. Gated by
`pipeline_enabled()` (default OFF).

## Request

```json
{
  "tickers": ["AAPL", "NVDA", "MSFT"],
  "strategy_slug": "midterm_52w_high_momentum",
  "total_capital": "100000.00",
  "available_cash": "25000.00",
  "caps": { "per_position_cap_pct": 0.10, "per_sector_cap_pct": 0.25 }
}
```

- `strategy_slug` optional, defaults to `midterm_52w_high_momentum`.
- `available_cash` optional; when present it is threaded into every `size_position` call.
- Holdings are **not** sent — derived server-side from persisted transactions via
  `_assemble_holdings` so the board matches the portfolio page.

## Responses

| Status | When | Body |
|---|---|---|
| **404** | `pipeline_enabled()` is OFF | standard not-found (home degrades gracefully) |
| **422** | `strategy_slug` is anything other than `midterm_52w_high_momentum` | clear message: pipeline is momentum-only because readiness is only defined for momentum |
| **200** | flag on, momentum slug | `PipelineBoardResponse` |

### 200 body (`PipelineBoardResponse`)

```json
{
  "items": [
    {
      "ticker": "NVDA",
      "entry_timing_state": "entry_ready",
      "sizing_preview": { "...": "SizingResponse (incl. binding_constraint, portfolio_heat_after_pct, reward_to_risk)" },
      "fit": {
        "score": 88,
        "fit_band": "strong_fit",
        "facts": { "entry_ready": true, "meaningful_size_survives": true, "heat_headroom_ok": true, "sector_room_ok": true, "not_overconcentrated": true, "regime_allows_entries": true, "reward_to_risk_ok": true, "cash_sufficient": true },
        "failed_facts": [],
        "rationale": "Ready to enter; a meaningful position fits within heat, sector, concentration, and cash limits."
      },
      "sector": "Technology",
      "skipped_reason": null
    },
    {
      "ticker": "AAPL",
      "entry_timing_state": null,
      "sizing_preview": null,
      "fit": null,
      "sector": "Unclassified",
      "skipped_reason": "Ticker not found in current universe snapshot"
    }
  ],
  "regime": { "...": "existing regime payload" },
  "regime_allows_new_entries": true,
  "heat_ceiling_pct": 0.06,
  "heat_headroom_pct": 0.021,
  "available_cash": "25000.00",
  "personal_use_directive": false,
  "data_as_of": "2026-07-03T00:00:00Z",
  "disclaimer": "…"
}
```

- `fit.directive_label` is **present only** when `personal_use_directive()` is on AND the app is
  not hosted; omitted entirely otherwise.

## Invariants (contract tests — `backend/tests/contract/test_pipeline_board.py`)

1. **404 when flag off** — no board leaks when `pipeline_enabled()` is OFF.
2. **422 for non-momentum slug** — e.g. `midterm_value_composite` → 422 with a clear message.
3. **200 shape + envelope** — `items[]`, top-level regime/heat, `data_as_of` + `disclaimer` present.
4. **Per-ticker fail-soft** — an unknown/un-priceable ticker yields one item with
   `skipped_reason` set and `fit`/`sizing_preview` = null; the rest of the board still renders.
5. **Facts wired from real code** — heat/sector/cash facts derive from an actual `size_position`
   + one `aggregate_exposure` per request (not stubbed); holdings derived server-side.
6. **Determinism** — same snapshot + same persisted portfolio ⇒ identical board (ties break on a
   stable key).
7. **No directive hosted** — with hosted mode on, no `directive_label` on any item regardless of
   the personal-use flag.
