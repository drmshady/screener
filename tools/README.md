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

## Daily-refresh automation (US1) — heavy Stooq bundle stays OFF the daily path

`.github/workflows/daily-refresh.yml` runs `scripts/publish_chain.ps1` on a
weekday cron. That chain only ever runs the **incremental** `ingest_daily`
(prices/events/Shariah/fundamentals delta) — never `-FullStooq`. The ~90-day
deep-history Stooq bundle (`scripts/refresh_stooq_history.py`) stays on its
existing, separate, infrequent cadence (quarterly `workflow_dispatch` or a
manual `scripts\publish.ps1 -FullStooq` run); putting it on the daily path
would be slow, wasteful, and unnecessary for end-of-day incremental freshness
(research.md Decision 5).
