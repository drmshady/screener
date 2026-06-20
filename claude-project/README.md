# Claude Project: Mid-Term Strategy Advisor

This folder is everything you need to stand up a **Claude Project** (claude.ai
or Claude Desktop) that acts as an expert, honest advisor for the **two mid-term
strategies** in this screener:

- `midterm_52w_high_momentum` — 52-week-high momentum (George & Hwang 2004)
- `midterm_value_composite` — multi-metric value, F-Score gated (Fama & French
  1992; Lakonishok, Shleifer & Vishny 1994; Piotroski 2000)

All facts here are pulled directly from
`backend/src/strategies/midterm_52w_high_momentum.py`,
`backend/src/strategies/midterm_value_composite.py`, the
`indicators/valuation.py` + `indicators/piotroski.py` modules, and the project
constitution. If the code changes, re-sync these files (see "Keeping it honest"
below).

## Setup (one time, ~3 minutes)

1. Go to **claude.ai → Projects → Create project** (or Claude Desktop →
   Projects). Name it e.g. *"52W-High Momentum Advisor"*.
2. Open **`00-custom-instructions.md`**, copy its entire body, and paste it into
   the project's **Custom instructions** box. (This is the persona + the rules
   it must obey — it is *not* a knowledge file.)
3. Upload the remaining files as **Project knowledge**:
   - `01-strategy-rules.md` *(momentum rules)*
   - `02-modifications-and-citations.md` *(momentum modifications)*
   - `03-honesty-and-limitations.md` *(shared — applies to both strategies)*
   - `04-workflow-and-prompts.md` *(shared — templates for both)*
   - `05-value-strategy-rules.md` *(value rules)*
   - `06-value-modifications-and-citations.md` *(value modifications + the 9
     F-Score signals)*
4. Start a chat in the project. Use the prompt templates in
   `04-workflow-and-prompts.md` — there's one per strategy. The advisor picks the
   right knowledge files from the `Strategy:` line in your pasted prompt.

## The one rule that makes this honest

Claude in the app **cannot run your Python**. It must never compute gate
math itself (it can get arithmetic confidently wrong). The workflow is:

> **Your screener computes the numbers → you paste the computed output →
> Claude interprets, advises, and caveats.**

`04-workflow-and-prompts.md` shows exactly what to paste.

## Personal-use scope

This advisor is configured for **directive personal-use mode** (it will give
you concrete buy/sell/size calls). That is fine because this tool is yours,
single-user, not redistributed. **If you ever host or share it, the
no-advice boundary in the constitution snaps back on** — switch the persona
back to neutral "analyst" framing and remove the directive permission.

## Keeping it honest (re-sync)

These files are a snapshot of the code. After any change to **either** strategy
file, its parameters, modifications, or its backtest artifact, regenerate the
affected file (`01`/`02` for momentum, `05`/`06` for value) so the advisor isn't
reasoning from stale rules. **Cross-cutting mechanics shared by both strategies —
the feature-011 bounded levels (`strategies/levels.py`), the fair-value estimate
(`indicators/fair_value.py`), and risk-per-trade sizing (`portfolio/sizing.py`) —
are documented once in `01` ("Fair value" / "Position sizing"), referenced from
`05`, and caveated in `03` §10; re-sync those if the level/sizing/fair-value
defaults change.** The survivorship-bias caveat in
`03-honesty-and-limitations.md` stays until each backtest's `bias_check`
actually passes (delisted tickers added) — for value, the backtest artifact may
not exist yet, so its survivorship is *unconfirmed*, which is no better than
failed.
