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

## What to gather before asking

For a single-candidate question, copy from your screener / single-ticker
analysis:

- **Ticker, sector, as-of date**
- **close**, **52-week high** (or `dist_to_high`)
- **ATR**, **200-day SMA**, **20-day consolidation low** (for stops)
- **debt_to_equity**, **fcf_ttm**, **gp_to_assets**, **asset_growth**
- **return_12_1** (12-1 momentum), **recent vs 50-day volume ratio**
- the per-gate **`gate_results`** breakdown if you have it (pass / warn /
  skipped + detail)
- current **market regime** (Trending up / Range-bound / Trending down)
- your **account size** and **risk-per-trade %** if you want sizing

The richer the paste, the fewer gates the advisor has to mark "unknown."

## Template A — "Should I take this candidate?"

```
Strategy: midterm_52w_high_momentum. As-of: <date>. Regime: <regime>.

Ticker: <TKR> (<sector>)
close: <x>   52w_high: <x>   ATR: <x>   SMA200: <x>   20d_low: <x>
debt_to_equity: <x>   fcf_ttm: <x>   gp_to_assets: <x>   asset_growth: <x>
return_12_1: <x>   volume_ratio_recent: <x>
gate_results: <paste if available>

Account: $<x>, risk per trade: <x>%.

Walk the gates in order, derive entry/stop/take-profit and reward:risk,
give me a directive call with your confidence and the biggest risk, then the
caveats. Stop mode: trend (default).
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
