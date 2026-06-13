# Claude Project: Mid-Term 52-Week-High Momentum — Strategy Advisor

This folder is everything you need to stand up a **Claude Project** (claude.ai
or Claude Desktop) that acts as an expert, honest advisor for the
`midterm_52w_high_momentum` strategy in this screener.

All facts here are pulled directly from
`backend/src/strategies/midterm_52w_high_momentum.py` and the project
constitution. If the code changes, re-sync these files (see "Keeping it honest"
below).

## Setup (one time, ~3 minutes)

1. Go to **claude.ai → Projects → Create project** (or Claude Desktop →
   Projects). Name it e.g. *"52W-High Momentum Advisor"*.
2. Open **`00-custom-instructions.md`**, copy its entire body, and paste it into
   the project's **Custom instructions** box. (This is the persona + the rules
   it must obey — it is *not* a knowledge file.)
3. Upload the remaining files as **Project knowledge**:
   - `01-strategy-rules.md`
   - `02-modifications-and-citations.md`
   - `03-honesty-and-limitations.md`
   - `04-workflow-and-prompts.md`
4. Start a chat in the project. Use the prompt templates in
   `04-workflow-and-prompts.md`.

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

These files are a snapshot of the code. After any change to the strategy file,
its parameters, modifications, or the backtest artifact, regenerate the
affected file so the advisor isn't reasoning from stale rules. The
survivorship-bias caveat in `03-honesty-and-limitations.md` stays until the
backtest's `bias_check` actually passes (delisted tickers added).
