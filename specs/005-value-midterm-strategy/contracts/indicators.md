# Contract: value indicators (test-first, Principle IV)

Both modules are **pure** (no I/O, no network) and ship with golden-fixture tests
under `backend/tests/indicators/` that are written and **failing before** the
strategy imports them.

## `backend/src/indicators/valuation.py`

```python
def book_to_market(common_equity: float, market_cap: float) -> float | None: ...
def earnings_yield(net_income_ttm: float, market_cap: float) -> float | None: ...
def cashflow_yield(operating_cf_ttm: float, market_cap: float) -> float | None: ...
def sales_yield(revenue_ttm: float, market_cap: float) -> float | None: ...

def value_composite(
    yields: dict[str, float | None],
    universe_ranks: dict[str, "pd.Series"],   # per-metric cross-sectional rank context
) -> tuple[float | None, int]:
    """Return (composite_score, n_evaluable_yields). composite = mean of the
    available metrics' percentile ranks. None/0 when no metric is evaluable."""
```

Rules:
- `market_cap <= 0` or `None` → every yield returns `None`.
- A negative numerator returns a **negative** yield (sorts as least cheap) — it is
  NOT clamped and NOT treated as missing.
- `value_composite` ignores `None` members and reports how many it used.

**Golden fixtures** (`test_valuation.py`): hand-computed yields for a positive-,
a negative-earnings, and a negative-book-value firm; a composite over {4 present},
{2 present}, {0 present}; assert negative-book firm ranks below a positive-book
firm with the same other yields.

## `backend/src/indicators/piotroski.py`

```python
def f_score(current: "FundamentalsYear", prior: "FundamentalsYear")
    -> tuple[int, int, dict[str, int | None]]:
    """Return (f_score 0-9, n_evaluable 0-9, per-signal map). A signal whose
    inputs are missing is None in the map, scores 0, and decrements n_evaluable."""
```

The nine signals exactly as data-model §3. `current`/`prior` carry: net_income,
total_assets, operating_cf, long_term_debt, current_assets, current_liabilities,
shares_outstanding, gross_profit, revenue.

**Golden fixtures** (`test_piotroski.py`): reproduce Piotroski's worked example
(or a hand-built firm) scoring a known total; a firm missing two inputs scores the
reduced `n_evaluable`; assert no signal awards a point on missing data.

## Existing indicators reused (no change)

`indicators/volatility.calculate_atr` (stop levels), `moving_averages` (200-SMA)
— already fixture-tested; the value strategy consumes them unchanged.
