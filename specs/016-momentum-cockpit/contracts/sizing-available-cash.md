# Contract: `size_position` available-cash constraint (additive)

Extends `backend/src/portfolio/sizing.py:size_position` with an optional `available_cash`
hard limit. **No flag** — an absent value is byte-identical to today.

## Change

- `SizingRequest` gains **`available_cash: Decimal | None = None`**.
- When present, cap `suggested_shares` so `suggested_shares × entry ≤ available_cash`.
- When that cap is the limiting factor, `SizingResponse.binding_constraint = "available_cash"`.
- `binding_constraint` vocabulary is extended (documented in the model): `risk_target |
  conviction | position_cap | sector_cap | portfolio_heat | conservative_fallback |
  available_cash`.

## Invariants (tests — `backend/tests/portfolio/test_sizing_available_cash.py`)

1. **Absent ⇒ byte-identical** — a request with `available_cash` unset produces exactly today's
   `SizingResponse` (regression fixture over existing cases).
2. **Binds correctly** — with `available_cash` below the cost of the otherwise-suggested
   position, `suggested_shares` is reduced so `shares × entry ≤ available_cash` and
   `binding_constraint == "available_cash"`.
3. **Zero cash is honest** — `available_cash = 0` ⇒ `suggested_shares == 0`,
   `binding_constraint == "available_cash"` (not a fabricated non-zero size).
4. **Does not override a tighter constraint** — if risk/position/sector/heat already bind below
   the cash limit, that constraint remains reported (cash only binds when it is the tightest).
5. **Vocabulary test extended** — the binding-constraint enum test includes `available_cash`.
