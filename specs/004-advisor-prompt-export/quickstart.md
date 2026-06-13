# Quickstart: Advisor Prompt Export

How to generate and verify an advisor prompt once the feature is implemented.
Assumes the 001/002 local dev setup (see `specs/001-screener-mvp/quickstart.md`).

## Generate a prompt (API)

```powershell
# Backend running (uvicorn) on the frozen snapshot.
# Neutral mode (default — compliant):
curl "http://localhost:8000/analyze/AMAT/advisor-prompt"

# Personal-use directive mode (single-user only; requires the constitutional
# amendment before defaulting on):
$env:SCREENER_PERSONAL_USE_DIRECTIVE = "1"
# (restart backend) then:
curl "http://localhost:8000/analyze/AMAT/advisor-prompt"
```

## Generate a prompt (UI)

1. Open a candidate detail page (e.g. `/candidate/AMAT`) or the analyze page.
2. Click **Copy advisor prompt** on the strategy-match card.
3. Paste into the Claude Project advisor (see `claude-project/`) or any fresh
   AI chat — the prompt is self-contained.

## Verify it (the honesty + correctness checks)

- **Complete**: the pasted text lists every gate (proximity, trend, volume,
  quality, gross profitability, low asset growth, sector strength) and all eight
  modifications with citations.
- **Honest**: it contains the survivorship caveat ("historical performance is
  optimistic … no delisted tickers"), the `data_as_of` date, and the disclaimer.
- **Grounded**: entry/stop/target match `GET /analyze/AMAT`.
- **Deterministic**: run the curl twice — the `prompt` field is identical.
- **Scope**: with `SCREENER_PERSONAL_USE_DIRECTIVE` unset, the prompt contains
  no "buy/sell/recommended" language.

## Run the tests

```powershell
python -m pytest backend/tests/agent            # builder + endpoint + flag
npm --prefix frontend run test                  # Vitest
npx --prefix frontend playwright test advisor-prompt-copy no-directive-copy
```

## Keep it in sync

The prompt is built from the live strategy declaration and the backtest
artifact, so it cannot drift. After changing the strategy's parameters,
modifications, or the backtest, re-run `backend/tests/agent` — the
declaration-drift test fails if the prompt omits a newly-declared modification.
This is also the moment to re-sync the `claude-project/` knowledge files.
