# tools/

Standalone scripts that are not part of the runtime app (backend/frontend) or
the CI automation workflow itself — investigation and comparison harnesses.

## compare_methods.py (planned, US4)

The FR-019 method-comparison harness for feature
[011-auto-refresh-risk-sizing](../specs/011-auto-refresh-risk-sizing/plan.md).
Runs on a frozen snapshot and deterministically reports, per candidate
level/sizing/fair-value method: realism metrics (degenerate rate, risk/reward
distance distributions vs price/ATR/horizon, over-ceiling count), robustness
metrics, fair-value coverage/trust rate, a head-to-head of the candidate
sizing-conviction modulators (fair value / inverse-vol / strategy-rank / none),
the backtest-baseline delta, and the `selected_default` per dimension — see
`specs/011-auto-refresh-risk-sizing/contracts/method-comparison.md`.

Not implemented yet — lands in Phase 6 (US4) of
`specs/011-auto-refresh-risk-sizing/tasks.md` (T033/T034).
