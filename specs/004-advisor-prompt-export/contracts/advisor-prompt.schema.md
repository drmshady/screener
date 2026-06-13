# Contract: Advisor Prompt Structure

The generated prompt MUST contain the following sections, in this order. Tests
assert presence and ordering. Section *content* is derived from live sources
(declaration, computed result, bias artifact) — never hand-maintained.

## 1. Task instruction

- **Personal-use flag ON**: instructs the advisor to walk the gates, derive
  levels, and give a **directive call** (take/pass/size) with explicit
  confidence and the single biggest risk, then the caveats.
- **Personal-use flag OFF**: instructs the advisor to **analyze** the candidate
  against the strategy's rules and explain the match neutrally. MUST contain no
  directive trading language ("buy", "sell", "recommended", "strong buy").

## 2. Strategy context (self-containing)

- Strategy name + slug.
- Core citation: `George & Hwang (2004)`.
- Timeframe (mid-term) + holding period (60–180 days).
- The list of gates in declared order.
- Every modification (currently 8) with its own citation, from the live
  `Strategy.modifications`.

## 3. Candidate result

- Ticker, name, sector.
- Matched status / rank and `data_as_of`.
- Entry, stop, tighter-stop (when present), take-profit, and reward:risk.

## 4. Gate-by-gate breakdown

- One line per gate: `PASS | FAIL | SKIPPED` + the gate's detail string.
- Skipped/passed-through gates MUST be visibly distinguished from real passes.

## 5. Regime

- Current market regime and its favorability label for this strategy
  (Favorable / Neutral / Unfavorable).

## 6. Honesty block (mandatory, every time)

- Survivorship-bias status from the backtest artifact; when failing, a plain
  statement that historical performance is optimistic and why (no delisted
  tickers).
- Notes for any gate skipped/passed-through on missing data for this candidate.
- Data freshness (`data_as_of`) and any stale-source note.
- The standard non-advice disclaimer.
- Personal-use scope reminder (directive guidance is for this single user only;
  not for redistribution).

## Invariants

- **Deterministic**: identical for a fixed snapshot + flag (no wall-clock in the
  body).
- **Complete**: every declared gate and every declared modification appears.
- **Honest**: the survivorship caveat appears whenever the artifact's
  `survivorship_bias.passed` is false; if the artifact is unreadable, the block
  states the status is unconfirmed rather than implying it is clean.
- **Grounded**: every numeric value equals the analyze surface's value.
