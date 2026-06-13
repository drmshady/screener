# Contract: `midterm_value_composite` strategy declaration

The strategy module MUST satisfy the same registry contract every strategy
satisfies (`backend/src/strategies/_registry.py` refuses to load otherwise), plus
the value-specific gate behavior below.

## Required module surface

```python
NAME: str                 # "Mid-Term Value Composite"
CITATION: str             # "Fama & French (1992); Lakonishok, Shleifer & Vishny (1994)"
TIMEFRAME: str            # "Mid-term"
DESCRIPTION: str
HOLDING_PERIOD: dict      # {"min": 60, "max": 180}
PARAMETERS: dict[str, StrategyParameter]   # every tunable has default (+ range where numeric)
REGIME_FAVORABILITY: dict # keys: "Trending up" | "Range-bound" | "Trending down"
MODIFICATIONS: list[Modification]          # each with name, description, citation
def rules(universe_df: pd.DataFrame) -> pd.DataFrame: ...
strategy = Strategy(...); registry.register(strategy)
```

Load-time guarantees (already enforced by the registry / `Strategy` model):
- Missing `citation` or `rules` → `ValueError` at import.
- `enabled_by_default = True` is auto-downgraded to `False` unless
  `backtest_summary` spans ≥15y including 2008–2009 (`_window_meets_floor`).

## `rules(universe_df)` contract

**Input** — a universe snapshot DataFrame containing at least: `ticker`,
`sector`, `close`, `atr`, and the value columns from data-model §2/§3
(`market_cap`, `book_to_market`, `earnings_yield`, `cashflow_yield`,
`sales_yield`, the nine F-Score signals). Optional `sma_200`,
`contraction_low_20` enable the stop levels. Missing value columns degrade to
recorded skips (never an exception).

**Output** — a DataFrame of survivors with these columns (superset of momentum):
`ticker, name, sector, close, entry, stop_loss, tighter_stop_loss, take_profit,
score, value_composite, f_score, f_score_evaluable, gate_results, warnings,
warning_count, reason`, plus `.attrs["gates_applied"]` / `.attrs["gates_skipped"]`.

**Behavioral requirements**:
1. **Liquidity** is assumed already applied by the engine (universe-wide gate) —
   `rules` MUST NOT re-screen liquidity.
2. **Value composite** ranks survivors; in hard mode the
   `composite_top_percentile` cut filters, in tiered mode it warns + ranks
   (reuse the momentum `_gate_mode()` switch).
3. **Piotroski gate**: keep `f_score >= min_f_score`; a name with low
   `f_score_evaluable` is reported `skipped` (partial), not a false `pass`.
4. **Within-sector ranking** (when `within_sector_ranking`): the composite is
   ranked among sector peers; then `rank_within_sector(..., max_per_sector)`.
5. **Determinism**: same `universe_df` → identical rows, order, and levels. No
   wall-clock, no RNG.
6. **Honest accounting**: every declared gate appears in `gates_applied` or
   `gates_skipped` with a reason; every survivor's `gate_results` lists each gate
   as `pass | fail | skipped` with a human-readable detail.
7. **Levels**: `entry = close`; `stop_loss` = trend (200-SMA when below entry)
   else 3-ATR fallback; `tighter_stop_loss` = structure (20-day low − ATR
   buffer); `take_profit = entry + take_profit_r_multiple × (entry − stop_loss)`.

## Single-ticker evaluability (FR-009)

The module MUST expose an `evaluate(row, context)` (and the universe-prep helper)
so `api/analyze.py` can grade one symbol against the live universe distribution —
the value-composite percentile and F-Score gates compute against the universe,
not silently skip for a single name (mirror momentum's `prepare_universe_gates` /
`evaluation_context`).
