# Workflow & Prompt Templates

The advisor is only as honest as the data you give it. Run the screener, copy
the **computed** output, paste it in. Don't ask Claude to figure out a stock's
numbers from memory — it can't, and it shouldn't pretend to.

> **The app now builds this prompt for you.** On any candidate (the candidate
> detail page or the Analyze page), click **"Copy advisor prompt"** — the app
> assembles a complete, self-contained prompt (candidate gate results, levels,
> regime, the full strategy context with citations, and the honesty/survivorship
> caveats) and copies it to your clipboard. Paste it straight into this Project,
> or even a fresh chat — it carries all the context itself, so Template A below
> is now mostly a fallback for manual/what-if questions.
>
> Directive (take/pass/size) framing in the generated prompt is gated behind the
> backend's personal-use flag `SCREENER_PERSONAL_USE_DIRECTIVE` (default **off** →
> neutral framing). Turn it on only for your own single-user machine; never for a
> shared or hosted instance (see [03-honesty-and-limitations.md](03-honesty-and-limitations.md)).
>
> The generated prompt works for **both mid-term strategies** — momentum
> (`midterm_52w_high_momentum`) and value (`midterm_value_composite`). It already
> carries the right strategy's gate breakdown, citations, and (for value) the
> value composite, its metric count, and the Piotroski F-Score with its evaluable
> count. The `Strategy:` line at the top tells you which one — read it first and
> reason from the matching knowledge files.

## What to gather before asking

For a single-candidate question, copy from your screener / single-ticker
analysis. **Common to both strategies:** ticker, sector, as-of date, close, ATR,
200-day SMA, 20-day low (for stops), market regime, and the per-gate
`gate_results` breakdown if you have it; plus your account size and
risk-per-trade % if you want sizing.

> **Feature 011:** the screener now also returns, per candidate, the **bounded
> levels** (`stop_loss`, `take_profit`, `levels_state`, and a `rationale`), a
> **fair value** + its **trust flag** (often `unavailable`/`out_of_range` for
> momentum names near their highs — that's expected), and **risk-per-trade
> sizing** with its `binding_constraint`. Paste these when you have them. The
> advisor should treat the app's bounded levels as authoritative and only
> *explain* them — the take-profit is a 3R/4R target **capped at a volatility
> ceiling**, and sizing is `(risk% × capital) / (entry − stop)` hard-bounded by
> the 10% position / 25% sector caps, not a "fill the cap" number.

**Momentum (`midterm_52w_high_momentum`) also wants:**

- **52-week high** (or `dist_to_high`), **return_12_1** (12-1 momentum)
- **debt_to_equity**, **fcf_ttm**, **gp_to_assets**, **asset_growth**
- **recent vs 50-day volume ratio**

**Value (`midterm_value_composite`) also wants:**

- the **value composite** + how many of the **4 yields** built it
  (`value_metrics_count`) — or the four raw yields (book/market, earnings,
  cash-flow, sales)
- the **Piotroski F-Score** + how many of the **9 signals were evaluable**
- **debt_to_equity** (leverage sanity)
- the name's **sector** (within-sector ranking depends on it)
- **return_12_1** (12-1 momentum) — only needed if the **optional momentum
  floor** variant is on (`min_momentum_12_1 > -1.0`, e.g. the `-0.20`
  "not a falling knife" variant); the default pure-value screen ignores it

The richer the paste, the fewer gates the advisor has to mark "unknown." For
value, the **metric count and evaluable count matter as much as the scores** —
always include them.

## Template A — "Should I take this MOMENTUM candidate?"

```
Strategy: midterm_52w_high_momentum. As-of: <date>. Regime: <regime>.

Ticker: <TKR> (<sector>)
close: <x>   52w_high: <x>   ATR: <x>   SMA200: <x>   20d_low: <x>
debt_to_equity: <x>   fcf_ttm: <x>   gp_to_assets: <x>   asset_growth: <x>
return_12_1: <x>   volume_ratio_recent: <x>
fair_value: <x>   fair_value_trust_flag: <trusted/unavailable/stale/out_of_range>
stop_loss: <x>   take_profit: <x>   levels_state: <ok/insufficient_data>   (if app-computed)
gate_results: <paste if available>

Account: $<x>, risk per trade: <x>% (default 1%).

Walk the gates in order. Use the app's bounded levels if I pasted them; else
derive entry/stop/take-profit (risk clamped to 1–4×ATR, 3R target capped at the
vol ceiling) and reward:risk. Size with risk-per-trade = (risk% × account) /
(entry − stop), capped at 10% position / 25% sector — name the binding
constraint. Treat fair value as context only (momentum names are usually above
it). Give a directive call with confidence and the biggest risk, then caveats.
Stop mode: trend (default).
```

## Template A-value — "Should I take this VALUE candidate?"

```
Strategy: midterm_value_composite. As-of: <date>. Regime: <regime>.

Ticker: <TKR> (<sector>)
close: <x>   ATR: <x>   SMA200: <x>   20d_low: <x>
value_composite: <x>   value_metrics_count: <n>/4
  (or yields — book_to_market: <x>  earnings_yield: <x>
   cashflow_yield: <x>  sales_yield: <x>)
f_score: <n>/9   f_score_evaluable: <n>/9
debt_to_equity: <x>
min_momentum_12_1: <-1.0 if pure value, else floor e.g. -0.20>   return_12_1: <x>
gate_results: <paste if available>

Account: $<x>, risk per trade: <x>%.

Walk the gates in order (composite → cheapness cut → F-Score → leverage →
momentum floor (only if min_momentum_12_1 > -1.0) → within-sector cap). Note
that SMA200 is the STOP only, not an entry filter.
Use the app's bounded levels if pasted; else derive entry/stop/take-profit
(risk clamped to 1–4×ATR, 4R target capped at the vol ceiling) and reward:risk.
Size with risk-per-trade = (risk% × account) / (entry − stop), capped at 10%
position / 25% sector. Give me a directive call with confidence and the biggest
risk (especially value-trap risk and how solid the F-Score / composite coverage
is), then the caveats.
```

## Template B — "Explain why this name matched / didn't"

```
Here is the gate breakdown my screener produced for <TKR> as of <date>:
<paste gate_results JSON or the pass/warn/skipped lines>

Explain in plain English why it matched (or where it failed/was skipped),
cite the source behind each gate, and tell me which "passes" are real vs
passed-through on missing data.
```

## Template C — "Should I trim / exit a position I hold?"

```
I'm holding <TKR> from <entry date> at avg cost <x>. Current close <x>,
ATR <x>, SMA200 <x>, original stop <x>, target <x>. Days held: <n>.
Regime now: <regime>.

Per this strategy's exit logic (trend/structure stop, 3R target, 60–180 day
horizon), what's the disciplined action? Give me the call and the level that
would change it.
```

## Template D — Teaching / understanding

```
Explain how the volatility-scaling modification interacts with the 12-1
momentum score, and when it would shrink my position. Use the strategy's
actual parameters.
```

## Good habits

- **Paste the as-of date every time.** A mid-term call on week-old data is a
  different call.
- **Ask "what are you assuming I didn't give you?"** to catch silent gaps.
- **For any "how well does this work?" question, expect — and want — the
  survivorship caveat.** If the advisor omits it, that's a bug in the persona;
  remind it.
- **Re-sync the knowledge files** after changing the strategy (see README).
