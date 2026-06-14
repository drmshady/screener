# Contract — Value Strategy Gates & Levels (updated)

Changes to `backend/src/strategies/midterm_value_composite.py`. The strategy's
declared gate order and level math are part of its transparency contract
(Principle II), so this records the new authoritative order.

## Declared gate order (hard mode)

1. **Value composite available** — name has ≥1 evaluable yield (else excluded,
   recorded).
2. **Cheapness cut** — `value_composite ≥ composite_top_percentile` threshold.
   NOW SHOWN AS ITS OWN GATE in `evaluate()` (FR-008), distinct from the composite
   ranking line.
3. **Piotroski F-Score** — `f_score ≥ min_f_score` (default 6); unscoreable ⇒
   excluded (not fail-open). A sub-9 `f_score_evaluable` sets
   `f_score_low_confidence = true` (FR-009).
4. **Profitability** (NEW, FR-005) — `operating_cf > 0 AND roa > 0`. Missing
   inputs ⇒ skipped + excluded in hard mode. Cited to Piotroski (2000).
5. **Leverage sanity** — `debt_to_equity ≤ max_debt_equity` (default 2.0); missing
   D/E passes through (fail-open).
6. **Momentum floor** (FR-007) — `return_12_1 ≥ min_momentum_12_1`,
   **default now −0.20** (was −1.0/off). Unknown momentum passes through.
   Overridable via UI toggle / frame attrs / `SCREENER_VALUE_MIN_MOMENTUM`.
7. **Within-sector concentration cap** — top `max_per_sector` (5) by composite,
   ranked within sector. The kept/dropped split is exposed (FR-010).

## Level derivation (FR-006)

```
entry          = close
atr_stop       = entry − 3·ATR
trend_stop     = sma_200      if 0 < sma_200 < entry  else atr_stop
structure_stop = contraction_low_20 − buffer·ATR  (validated)
chosen         = trend_stop                      # prior behaviour
# NEW minimum-risk floor:
if (entry − chosen) < 1·ATR:                      # degenerate risk
    chosen      = atr_stop                        # 3-ATR fallback
    stop_basis  = "atr_floor_fallback"
stop_loss      = chosen
risk_per_share = entry − stop_loss                # guaranteed ≥ 1·ATR
take_profit    = entry + take_profit_r_multiple · risk_per_share
```

Applies identically in `derive_levels` (single name) and the vectorized `rules()`
block. Invariant: `risk_per_share ≥ 1·ATR` for every returned candidate.

## PARAMETERS changes

| Param | Old default | New default |
|-------|-------------|-------------|
| `min_momentum_12_1` | −1.0 (off) | **−0.20 (on)** |
| `min_risk_atr_multiple` (NEW) | — | **1.0** (floor for the stop, FR-006) |

`min_f_score`, `composite_top_percentile`, `max_debt_equity`,
`take_profit_r_multiple`, `within_sector_ranking`, `max_per_sector` unchanged.

## evaluate() output additions

- A `"Cheapness cut"` gate entry (pass/fail vs threshold).
- A `"Profitability"` gate entry (pass/fail/skipped).
- F-Score entry carries the evaluable count and sets `f_score_low_confidence`.

All new detail strings MUST be free of directive language (lint).
