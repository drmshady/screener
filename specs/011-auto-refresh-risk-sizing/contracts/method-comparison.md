# Contract: Method-Comparison Artifact (US4, FR-019/020)

**Surface:** a deterministic harness (under `tools/`) that runs on a **frozen**
snapshot and emits a regenerable report justifying every adopted default and
stating any backtest-baseline impact. No app-runtime API.

## Inputs

A frozen snapshot id; the candidate **level methods**, **sizing methods**, and
**fair-value bases** (Decisions 1–3).

## Output (regenerable, deterministic — SC-007)

Per method:
- **Realism**: degenerate rate; distribution of risk distance and reward distance
  vs price / ATR / horizon; count of targets beyond the realistic ceiling.
- **Robustness**: stability of the above across the universe.
- **Coverage/reliability**: fair-value availability + trust rate.
- **`backtest_baseline_delta`**: the effect of level-driven modeled exits on the
  committed backtest baseline (the re-baseline is **gated** on this showing an
  improvement, FR-020).
- **`selected_default`** per dimension — the adopted choice.

## Invariants

- Regenerates byte-identically on the frozen snapshot (SC-007).
- The defaults shipped in code **equal** `selected_default`.
- Any backtest-baseline impact is surfaced explicitly; the one-time re-baseline is
  performed **only** when the artifact shows the new method is an improvement, with
  a constitution reproducibility re-check, never silently (FR-020).

## Tests

Re-run ⇒ identical bytes; the harness flags if shipped defaults diverge from the
artifact's selection; the backtest-delta section is present and populated.
