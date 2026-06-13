# Contract: Mid-Term Gate Order & Oracle Expectations

**Feature**: 002-app-strategy-validation
**Target**: `backend/src/strategies/midterm_52w_high_momentum.py` — "Mid-Term
52-Week High Momentum", George & Hwang (2004).

This is the behavioral contract the mid-term validation asserts. It is the
oracle the `backend/tests/validation/` module checks the strategy against on
the frozen snapshot. Symbols are snapshot-relative (see Decision 3); the
*structure* of expectations is fixed.

---

## Declaration contract (FR-004)

The strategy MUST expose, and the registry MUST refuse to load it without:

| Field | Required value / shape |
|-------|------------------------|
| `NAME` | "Mid-Term 52-Week High Momentum" |
| `CITATION` | "George & Hwang (2004)" |
| `TIMEFRAME` | "Mid-term" |
| `PARAMETERS` | dict incl. `lookback_days` (252), `proximity_pct` (0.05), `max_per_sector`, `max_debt_equity` (1.5), `target_volatility`, `trend_sma_length` (200), `min_gp_assets_percentile` |
| `REGIME_FAVORABILITY` | present, non-empty |
| `MODIFICATIONS` | list; each item carries its **own** citation |
| `rules()` | pure callable (same input → same output) |

Declared modifications (each MUST carry a citation):
1. **Volatility scaling** — Barroso & Santa-Clara.
2. **Sector-relative ranking** — sector-concentration / relative-strength.
3. **Quality screen** — QMJ-style (Asness, Frazzini & Pedersen).

---

## Gate order contract (FR-005)

Gates MUST be applied in this exact sequence, and the funnel MUST report the
surviving count after each:

```
liquidity → proximity → trend → volume → quality → gross_profitability → asset_growth
```

- **liquidity** (universe-wide, FR-008): ADV ≥ $1M (20-day) AND price ≥ $5.
- **proximity**: within `proximity_pct` (default 5%) of the 252-day high.
- **trend**: price above the `trend_sma_length` (200-day) SMA.
- **volume**: recent-window volume confirmation (≥ documented ratio).
- **quality**: D/E ≤ `max_debt_equity` (1.5) AND FCF > 0.
- **gross_profitability**: top half by GP/assets across the peer universe.
- **asset_growth**: bottom half by YoY asset growth across the peer universe.

> Note: the **sector-strength** gate is intentionally **disabled** on the
> current snapshot (T192, `sector_strength_top_fraction = 1.0`). The validation
> MUST confirm it is disabled (not silently re-enabled) and record that as the
> expected state, not a defect.

---

## Reference-ticker oracle (FR-006, SC-004)

≥4 tickers spanning at least the proximity, quality, and asset-growth gates.
Confirmed against the frozen snapshot at run time; if the candidate set has
shifted, record the then-current set and re-derive expectations from the rules.

| Ticker(s) | Expected | Expected gate (if fail) | Rationale |
|-----------|----------|-------------------------|-----------|
| EA, BELFB, ASYS, AMAT, ROST | **pass** (candidate) | — | T192 restored candidate set; clears every gate |
| WYY | **fail** | asset_growth | ~11.5% YoY asset growth exceeds the bottom-half ceiling |
| (snapshot name >5% below high) | **fail** | proximity | outside the 5% proximity band |
| (snapshot name D/E>1.5 or FCF≤0) | **fail** | quality | violates the QMJ-style quality screen |

A mismatch (wrong outcome, or right outcome at the wrong gate) is a **defect**,
not a data-tier limitation.

---

## Modification-effect contract (FR-006a)

Toggling each modification MUST change the screen output on the snapshot:

| Modification | Toggle method | Expected observable effect |
|--------------|---------------|----------------------------|
| Volatility scaling | widen/neutralize `target_volatility` | sizing/ranking shifts |
| Sector-relative ranking | disable sector ranking | within-sector ordering changes |
| Quality screen | relax `max_debt_equity` / FCF | additional names survive quality |

A modification with **zero** effect on the snapshot is flagged for inspection
(potential inert declaration → transparency defect, Constitution II).

---

## Determinism contract (FR-007, SC-005)

Running `rules()` (and the screen, regime, sizing, backtest) twice on the
frozen snapshot MUST yield byte-identical candidate sets, ordering, and gate
counts. Any difference is a **blocker defect**.
