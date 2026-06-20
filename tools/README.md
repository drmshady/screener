# tools/

Standalone scripts that are not part of the runtime app (backend/frontend) or
the CI automation workflow itself — investigation and comparison harnesses.

## compare_methods.py (US4)

The FR-019 method-comparison harness for feature
[011-auto-refresh-risk-sizing](../specs/011-auto-refresh-risk-sizing/plan.md).
Runs on a frozen snapshot and deterministically reports, per candidate
level/sizing/fair-value method: realism metrics (degenerate rate, risk/reward
distance distributions vs price/ATR/horizon, over-ceiling count), robustness
metrics, fair-value coverage/trust rate, a head-to-head of the candidate
sizing-conviction modulators (fair value / inverse-vol / strategy-rank / none),
the backtest-baseline delta, and the `selected_default` per dimension — see
`specs/011-auto-refresh-risk-sizing/contracts/method-comparison.md`.

Implemented in Phase 6 (US4) as a deterministic JSON harness:

```powershell
py -3.12 tools\compare_methods.py --snapshot frozen-sample
```

The default offline sample keeps CI fast and proves byte-identical regeneration
plus shipped-default drift detection. Passing a JSON fixture path as `--snapshot`
lets the same report shape run against a larger frozen candidate snapshot.

The `sizing_metrics` and `backtest_baseline_delta` sections are **computed, not
stubbed**:

- `conviction_head_to_head` sizes every candidate through the real
  `portfolio.sizing.size_position` under each modulator (none / fair_value /
  inverse_vol / strategy_rank) and reports how many it actually modulates and the
  resulting share dispersion. `wider_stop_smaller_monotonicity` is verified on the
  real risk-per-trade output (cap-bound rows excluded), not asserted.
- `backtest_baseline_delta` runs the runner's own `_forward_return` (fixed
  horizon) vs `_modeled_exit_return` (level-driven) over forward bars. The offline
  frozen sample uses a deterministic price fixture (`basis =
  synthetic_fixture_mechanics_check`) — a mechanics/regression check that is never
  `rebaseline_eligible`. A `--snapshot` JSON whose candidates carry a
  `forward_bars` list (with optional `as_of`/`horizon_days`) makes the delta run on
  real bars (`basis = real_bars`); only then can a measured improvement open the
  re-baseline gate (T038, still never silent).

## Daily-refresh automation (US1) — heavy Stooq bundle stays OFF the daily path

`.github/workflows/daily-refresh.yml` runs `scripts/publish_chain.ps1` on a
weekday cron. That chain only ever runs the **incremental** `ingest_daily`
(prices/events/Shariah/fundamentals delta) — never `-FullStooq`. The ~90-day
deep-history Stooq bundle (`scripts/refresh_stooq_history.py`) stays on its
existing, separate, infrequent cadence (quarterly `workflow_dispatch` or a
manual `scripts\publish.ps1 -FullStooq` run); putting it on the daily path
would be slow, wasteful, and unnecessary for end-of-day incremental freshness
(research.md Decision 5).
