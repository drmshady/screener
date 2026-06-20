# Contract: Sizing — `size_position` v2 (US3, FR-013…017)

**Surface:** `size_position(request: SizingRequest) -> SizingResponse` in
[`sizing.py`](../../../backend/src/portfolio/sizing.py#L13). Same call site
([`api/portfolio.py`](../../../backend/src/api/portfolio.py)). `SizingRequest`
gains `stop_loss` and an optional `fair_value` (+ `trust_flag`); `SizingResponse`
gains the binding-constraint + risk/fair-value metadata (see data-model).

## Algorithm

1. **Risk-per-trade target.** `risk_budget = f · total_capital`;
   `risk_per_share = entry − stop_loss`; `target_shares = floor(risk_budget /
   risk_per_share)`. (Wider stop ⇒ fewer shares — SC-004.)
2. **Conviction modulation** — the **US4-adopted** signal (fair-value margin of
   safety / inverse-volatility / strategy-rank / none), applied only when its input
   is trusted: higher conviction ⇒ size **not reduced**, may increase per the
   documented monotonic rule; lower conviction ⇒ may shrink / cap. Sets
   `conviction_adjustment` (and, when fair value is the adopted signal,
   `fair_value_adjustment`). Fair value is one candidate, not assumed.
3. **Cap clamp.** Clamp to the lower remaining room of the per-position and
   per-sector caps (reuse existing `aggregate_exposure`). **Never breach** (FR-014).
4. **Fail-open.** Adopted signal's input missing/untrusted ⇒ skip step 2,
   `fair_value_used`/conviction flag `= false`, noted in `reasoning` (FR-016).
5. Set `binding_constraint` to whichever bound the final size; build a neutral,
   zero-directive `reasoning` (FR-017).

## Invariants

- `caps_respected == true` for any non-zero suggestion; no cap ever breached
  (FR-014, SC-004).
- Two candidates identical except a wider stop ⇒ the wider-stop one is sized
  **smaller** (SC-004).
- Higher conviction (per the adopted signal — e.g. larger margin of safety when fair
  value is adopted, lower vol when inverse-vol is adopted) sizes **≥** the
  otherwise-identical lower-conviction candidate (Acceptance #3).
- Missing/untrusted conviction input ⇒ risk-based-within-caps, no error (FR-016, SC-005).
- Deterministic on fixed input; existing zero-room "cannot size without breaching
  cap" branch preserved.

## Parameters

`risk_per_trade_fraction` (`f`, small, documented, env-overridable), the
**adopted conviction signal** (fair value / inverse-vol / strategy-rank / none),
and its modulation curve — all set by the US4 artifact.

## Tests (written first)

Risk-target math; wider-stop→smaller-size; fair-value monotonicity; fail-open;
cap-never-breached (incl. cap-binds-tighter-than-risk case); rationale names the
binding constraint + zero-directive; determinism.
