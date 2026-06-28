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
- **(feature 012) the entry-timing classification** — `entry_timing.state`
  (entry-ready / not-entry-ready / entry-undetermined), the six component
  pass/fail/undetermined results, the disqualifiers (climax-top, huge-gap,
  short-lived-catalyst), and the diagnostics (`base_type`, `pivot`,
  `base_length_weeks`, `base_depth`, `breakout_volume_ratio`,
  `dist_above_pivot`, `dist_above_sma_200`). Paste whatever the app shows.
- **(feature 012) any `skipped` preferred gates** if `expanded_coverage` is on
  (market regime / sector strength / relative strength) — these are retained,
  demoted, **not** passes.

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

## Search the news (feature 012 — for the catalyst / "sell-the-news" check)

The screener is an **end-of-day** tool — it has **no news feed**. The
entry-timing overlay can flag a **short-lived-catalyst** risk structurally (a
sharp recent advance), but it cannot read *why* a stock moved. That is the one
thing a Claude Project **can** add: it has web search. So for any momentum
candidate — especially one near its pivot or flagged not-entry-ready — ask the
advisor to **search recent news** and reconcile it with your pasted numbers:

```
Search the web for news on <TKR> from the last ~2 weeks. I'm evaluating it as a
52-week-high momentum entry as of <date>.
- Is the run-up driven by a one-off catalyst (earnings beat, single headline,
  M&A rumor, analyst upgrade, index add)? If so, flag "sell-the-news" /
  post-catalyst pullback risk.
- Any pending hard catalyst (earnings date, FDA/PDUFA, court ruling, lockup
  expiry) inside my 60–180 day horizon?
- Anything that would void a gate I can't re-check (dilution, going-concern,
  fraud/restatement, delisting risk)?
Cite each source with its date. Tell me where my as-of-<date> numbers are likely
stale versus the news. Do NOT invent prices or fundamentals from the news — only
flag what to re-verify in the screener.
```

Honesty rules that still apply (see `03-honesty-and-limitations.md` §11): web
results can be **wrong, dated, or paywalled-summarized** — the advisor must cite
and date every claim and never overwrite a *computed* gate result with something
it read in an article. News informs the **catalyst/timing risk narrative**; it
does **not** recompute the screen.

## Template A — "Should I take this MOMENTUM candidate?"

```
Strategy: midterm_52w_high_momentum. As-of: <date>. Regime: <regime>.

Ticker: <TKR> (<sector>)
close: <x>   52w_high: <x>   ATR: <x>   SMA200: <x>   20d_low: <x>
debt_to_equity: <x>   fcf_ttm: <x>   gp_to_assets: <x>   asset_growth: <x>
return_12_1: <x>   volume_ratio_recent: <x>
fair_value: <x>   fair_value_trust_flag: <trusted/unavailable/stale/out_of_range>
stop_loss: <x>   take_profit: <x>   levels_state: <ok/insufficient_data>   (if app-computed)
entry_timing.state: <entry-ready/not-entry-ready/entry-undetermined>   (feature 012, if shown)
entry_timing components/disqualifiers: <paste the pass/fail/undetermined lines + any climax-top / huge-gap / short-lived-catalyst flags>
skipped_preferred_gates: <paste if expanded_coverage on — these are retained, NOT passes>
gate_results: <paste if available>

Account: $<x>, risk per trade: <x>% (default 1%).

Walk the gates in order. Use the app's bounded levels if I pasted them; else
derive entry/stop/take-profit (risk clamped to 1–4×ATR, 3R target capped at the
vol ceiling) and reward:risk. Size with risk-per-trade = (risk% × account) /
(entry − stop), capped at 10% position / 25% sector — name the binding
constraint. Treat fair value as context only (momentum names are usually above
it).
Read the entry-timing classification as an OBJECTIVE technical STATE, not a
buy/sell call: explain WHY it is entry-ready / not-entry-ready / entry-undetermined
(which components failed or were undetermined, which disqualifiers fired). Then
SEARCH THE WEB for recent news on <TKR> (last ~2 weeks): if there is a
short-lived catalyst (earnings pop, single headline, one-off spike), flag the
"sell-the-news" / post-catalyst pullback risk; cite the sources and dates and
note that my pasted numbers may pre-date the news.
Give a directive call with confidence and the biggest risk, then caveats.
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

## Template E — "Scan this list → Enter / Watch" (momentum)

Use this when you paste a **whole screen** (not one name) and want it ranked
into two buckets. The advisor must follow the **ranking rubric** in
[00-custom-instructions.md](00-custom-instructions.md) — entry-timing is a
**tie-breaker / risk-veto, not a gate**, so a clean George & Hwang drift name
that is below its pivot or "weak-volume" still belongs in **Enter**.

> **Shortcut (momentum):** the app has a one-click **"Copy Project triage prompt
> (Enter / Watch)"** button on the screen page. It runs the wider
> *expanded-coverage* list (preferred-gate misses retained + demoted, Watch names
> kept) and copies a prompt that already carries this Enter/Watch task framing —
> paste it straight into the Project. The manual template below is the fallback
> when you've hand-built a list or pasted from elsewhere.

**Step 0 — pre-bucket checklist (gate the WHOLE list before bucketing).** The
advisor must confirm these first and refuse to produce a confident Enter list
while any is open:

1. **Regime verified?** If the market regime is **Unfavorable** (SPY below its
   200-day SMA → the Faber master switch suppresses *new* entries) or
   **Unknown/unverified**, say so up front; everything is at most "Watch" until
   regime is confirmed Favorable/Neutral.
2. **Halal/Shariah freshness re-checked?** If the compliance source
   (`halal_terminal` et al.) is **stale**, compliance can't be trusted — names
   must be re-verified before any Enter call. Flag it; don't silently bucket.
3. **Corporate-action / data-integrity scan done?** See standing excludes below.

**Standing excludes (drop from BOTH buckets, never just demote):**

- Any candidate carrying a **DATA INTEGRITY WARNING** → out.
- Any **stale corporate-action / pinned-price signature** (merger-arb, split/
  dividend mismatch, share-class confusion) → out.
- `data_suspect = true` → out of Enter (the app already sinks these below all
  clean names; treat them as exclude, not "low Enter").

**ENTER** = passes all **essential** gates (no hard fail; in `expanded_coverage`
a *skipped preferred* gate is OK but lowers rank) **AND** no **forcing
disqualifier** fired (climax-top, huge-gap) **AND** ranks high **AND** is not
dangerously **extended** above its SMA-200. Entry-timing only **demotes within
Enter** (extended / climax / short-lived-catalyst names sink); it never evicts a
clean drift name.

**WATCH** = clean essential gates but **one of**: a forcing disqualifier fired,
the name is materially **extended** above SMA-200, a non-forcing
**short-lived-catalyst** caution needs a news check first, `entry-undetermined`
from thin data, or it simply **ranks below the Enter cut**.

**Ranking order inside each bucket** (mirror the app's own sort, then add the
entry-timing veto):

1. cleanliness first — **fewer soft-gate warnings** (a clean name beats a
   higher-scoring demoted one);
2. then **strategy score** (`return_12_1 × vol_scalar / (1 + dist_to_high)`),
   highest first;
3. tie-break on **lower `dist_above_sma_200`** (less momentum-crash risk),
   then on better fundamental coverage (fewer fail-open / missing-data gates),
   then ticker for stability.

Always print each Enter name's **SMA-200 distance** and **entry-timing state**
in the table so the demotion logic is visible, not hidden.

```
Strategy: midterm_52w_high_momentum. As-of: <date>. Regime: <regime>.
Halal source freshness: <fresh / stale as of <date>>.

Here is my full screen (one row per candidate). Columns:
ticker | sector | score | dist_to_high | dist_above_sma_200 | warnings/skipped_gates |
entry_timing.state | disqualifiers fired | data_integrity_warning? | data_suspect?
<paste rows>

Rank this into ENTER and WATCH using the Project rubric:
- First run the pre-bucket checklist (regime, halal freshness, data-integrity /
  corporate-action). If regime is Unfavorable/Unknown or halal is stale, tell me
  and cap everything at Watch until I resolve it.
- Drop any DATA INTEGRITY WARNING / stale corporate-action / data_suspect name.
- ENTER = clean essential gates + no forcing disqualifier + high rank + not
  dangerously extended. Entry-timing only DEMOTES extended/climax/short-lived-
  catalyst names within Enter — do NOT exclude a clean below-pivot drift name.
- Rank within each bucket: fewer warnings, then score, then lower SMA-200
  distance. Show SMA-200 distance and entry-timing state per row.
- For the top few ENTER names, SEARCH THE WEB for recent news / catalysts and
  flag post-catalyst pullback risk; cite and date sources; never overwrite a
  computed gate.
Give the survivorship caveat once at the end. This is my decision, not yours.
```

## Good habits

- **Paste the as-of date every time.** A mid-term call on week-old data is a
  different call.
- **Ask "what are you assuming I didn't give you?"** to catch silent gaps.
- **For any "how well does this work?" question, expect — and want — the
  survivorship caveat.** If the advisor omits it, that's a bug in the persona;
  remind it.
- **Re-sync the knowledge files** after changing the strategy (see README).
