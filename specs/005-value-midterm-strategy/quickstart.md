# Quickstart: Value-Based Mid-Term Strategy

Local, single-machine, personal-use. Assumes the 001–004 dev environment is
already set up (Python 3.12 venv for `backend/`, Node 20 for `frontend/`) and the
frozen `backend/data/` snapshot (Stooq Parquet, EDGAR slim cache) is present.

## 0. Branch

```bash
git switch 005-value-midterm-strategy
```

## 1. Test-first: the new indicators (must fail before implementation)

```bash
cd backend
python -m pytest tests/indicators/test_valuation.py tests/indicators/test_piotroski.py -q
# EXPECT: failures/collection errors — modules don't exist yet (Principle IV)
```

Implement `src/indicators/valuation.py` and `src/indicators/piotroski.py` until
these golden-fixture tests pass. Do this BEFORE touching the strategy.

## 2. Extend the point-in-time fundamentals

Add `value_metrics_as_of` to `src/data/fundamentals.py` and the extra
`NEEDED_TAGS` to `src/backtests/runner.py`; thread the new columns through
`screening/engine.py` (`_edgar_profiles`, `_compute_snapshot_rows`).

```bash
python -m pytest tests/data/test_value_metrics_as_of.py -q   # point-in-time + missing-input rules
```

If the EDGAR slim cache predates the new tags, re-slim affected tickers:

```bash
python -m scripts.refresh_reference_thresholds --help   # see how the cache is rebuilt
# (or delete backend/data/edgar_cache/<TICKER>.json to force a re-fetch on next run)
```

## 3. Implement and register the strategy

Create `src/strategies/midterm_value_composite.py` (mirror
`midterm_52w_high_momentum.py`) + `_helpers/value_composite.py`. Confirm it loads:

```bash
python -c "from backend.src import strategies; from backend.src.strategies._registry import registry; s=registry.get('midterm_value_composite'); print(s.name, s.citation, s.enabled_by_default)"
```

## 4. Run the screen

```bash
# Backend API
uvicorn backend.src.main:app --reload
# In another shell — run the value strategy over the default/Shariah universe
curl -s -X POST localhost:8000/screen -H 'content-type: application/json' \
  -d '{"strategy_slug":"midterm_value_composite","filters":{"shariah_only":true}}' | jq '.candidate_count, .candidates[0]'
```

Verify: every listed name has `f_score >= min_f_score`, a non-null
`value_composite`, a populated `gate_results`, and the response carries
`data_as_of` + `disclaimer`.

## 5. Determinism check (SC-002)

```bash
# Same snapshot twice → identical candidate set + ranking + levels
curl -s -X POST localhost:8000/screen -d '{"strategy_slug":"midterm_value_composite"}' > /tmp/a.json
curl -s -X POST localhost:8000/screen -d '{"strategy_slug":"midterm_value_composite"}' > /tmp/b.json
diff <(jq '.candidates|map({ticker,entry,stop_loss,take_profit,score})' /tmp/a.json) \
     <(jq '.candidates|map({ticker,entry,stop_loss,take_profit,score})' /tmp/b.json) && echo IDENTICAL
```

## 6. Backtest (≥15y incl. 2008–2009)

```bash
cd backend
python -m src.backtests.runner --strategy midterm_value_composite --start 2008-01-01 --end 2024-12-31
# Writes backend/data/backtests/midterm_value_composite.json + backend/backtests/midterm_value_composite/
jq '.data_window_start, .data_window_end, .bias_check.survivorship_bias.passed, (.yearly_metrics|length), .coverage_notes' \
  data/backtests/midterm_value_composite.json
```

Expect: window 2008→2024, `survivorship_bias.passed=false` (Stooq), ≥15 yearly
rows (early years may be empty — the pre-2011 XBRL sparsity note appears in
`coverage_notes`; this is honest, not a bug).

## 7. Single-ticker analysis (FR-009)

```bash
curl -s -X POST localhost:8000/analyze -d '{"ticker":"INTC","strategy":"midterm_value_composite"}' | jq '.gate_results, .f_score, .value_composite'
```

The composite/F-Score gates evaluate against the live universe — not skipped.

## 8. Advisor prompt (FR-016)

```bash
curl -s -X POST localhost:8000/analyze/INTC/advisor-prompt -d '{"strategy":"midterm_value_composite"}' | jq -r .prompt | head -40
```

Confirm the prompt shows the Fama-French/LSV + Piotroski citations, the value
diagnostics, the honesty block with the survivorship FAIL, and — with the
personal-use flag off — zero directive language.

## 9. Frontend + lints

```bash
cd frontend
npm run test
npx playwright test no-directive-copy        # must stay green for the new surfaces
```

## 10. Full backend suite

```bash
cd backend && python -m pytest -q
```

## Definition of done

- Indicator golden tests pass (written first).
- Screen returns deterministic, F-Score-gated, value-ranked candidates with
  full gate accounting + `data_as_of`/`disclaimer`.
- Backtest artifact spans 2008–2024 with honest `bias_check`/`coverage_notes`;
  strategy stays `enabled_by_default=false` unless an explicit operator override
  is set.
- Strategy appears in `/strategies`, single-ticker analysis, the 003 comparison,
  and the 004 advisor export; no-directive lint green.
