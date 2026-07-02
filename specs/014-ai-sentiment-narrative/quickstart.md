# Quickstart: AI Sentiment & Narrative Intelligence (+ 3 bug fixes)

Local dev + hosted runbook for feature 014. Reuses the existing dev environment (see the 013/010
quickstarts). Windows dev conventions: `py -3.12`, `npm.cmd`, Next prod build for headless.

## 0. Prereqs
- **Scoring (label/score):** FinBERT runs **locally, free, offline**. The **runtime** path (and the
  baked HF image) uses the light **ONNX** wheels; the vendored Loughran-McDonald lexicon is the
  zero-dep fallback, so the app still scores without the model present.
  ```
  py -3.12 -m pip install onnxruntime tokenizers          # runtime inference (light — goes in the image)
  py -3.12 -m pip install "screener-backend[export]"      # torch+transformers+optimum — EXPORT ONLY, never baked
  py -3.12 scripts/export_finbert_onnx.py                 # one-time: writes backend/data/finbert_onnx/ (~100 MB)
  ```
  Deployment note: `torch` is **never** installed into the HF backend image — only the ONNX runtime +
  the baked model are. See [contracts/deploy-finbert.md](./contracts/deploy-finbert.md).
- **Optional narrative prose:** provider-swappable, only for the plain-language storyline (scoring
  needs no LLM). Install whichever provider you use; absent ⇒ deterministic `template` narrative.
  ```
  py -3.12 -m pip install google-genai              # Gemini (free tier) — default when key present
  # or: py -3.12 -m pip install anthropic            # Claude Haiku alternative
  ```
- News: `yfinance` (already installed) is the no-key baseline; **Finnhub + Alpha Vantage** keys (owner-
  provided) are configured backups.

## 1. Configuration (env only — never written to any file)

| Env var | Default | Purpose |
|---|---|---|
| `SCREENER_SENTIMENT_ENABLED` | `0` | Master switch for the sentiment overlay. |
| `SCREENER_SENTIMENT_SCORER` | `finbert` | `finbert` (local) \| `lexicon` (fallback / hosted-light). |
| `SCREENER_SENTIMENT_NEWS_PROVIDERS` | `yfinance` | Ordered chain, e.g. `yfinance,finnhub,alphavantage` (fail-soft). |
| `FINNHUB_API_KEY` | — | Backup news headlines (owner-provided). Runtime env only. |
| `ALPHAVANTAGE_API_KEY` | — | Backup news + optional vendor-sentiment cross-check (owner-provided). |
| `SCREENER_SENTIMENT_LLM_PROVIDER` | `gemini` | `gemini` \| `anthropic` \| `none` (template only). |
| `GEMINI_API_KEY` | — | Optional narrative prose — free tier ⇒ $0 (owner-provided). |
| `SCREENER_SENTIMENT_LLM_MODEL` | (provider default) | e.g. a Gemini Flash-Lite id, or `claude-haiku-4-5`. |
| `ANTHROPIC_API_KEY` | — | Only if `LLM_PROVIDER=anthropic`. |
| `SCREENER_SENTIMENT_MONTHLY_CAP_USD` | `5.00` | Hard monthly spend cap (pre-call enforced; $0 on Gemini free tier). |
| `SCREENER_SENTIMENT_SOCIAL` | `0` | Off — no free licensing-permissible source yet (fail-soft omit). |

All keys (Finnhub / Alpha Vantage / Gemini / Anthropic) are process-local / runtime env only, never
committed or written to any artifact (api-keys-never-write rule; `scripts/secret_scan.ps1` release check).

## 2. Run the bug fixes (ship first, independently)

- **Bug A (watchlist parity):** run a screen → add a candidate from the **table** and from the
  **candidate detail page**; confirm the visible confirmation and that the name appears on
  `/watchlist` with its entry/stop/target snapshot; re-add ⇒ "already watched", no duplicate.
- **Bug B (regime SPY SMA):** with the live feed unreachable (offline / hosted), open the regime
  panel; confirm a **numeric SPY close + 200-day SMA + above/below verdict + source + as-of** — not
  "Unknown". Force true insufficient history ⇒ an explicit reason ("gate fails open"), not "Unknown".
  Run twice on one snapshot ⇒ identical.
  ```
  # regenerate the daily-baked SPY series locally when needed
  py -3.12 scripts/ingest_daily.py
  ```
- **Bug C (market events staleness):** after `scripts/ingest_daily.py` reseeds the econ calendar,
  confirm `/events/market` returns `is_stale: false` (re-seeded today) and shows upcoming
  FOMC/CPI/NFP/PCE/PPI with real dates — no spurious "Stale events data" badge, no empty window.

## 3. Run the sentiment report (on-request only)

```
# backend (repo root)
py -3.12 -m uvicorn backend.src.api.app:app --reload
```
Frontend: from `/sentiment` (or from screener results / portfolio holdings), **select** one or more
tickers (or type a manual symbol) → **Run report**. Verify:
- A sentiment **label** (positive/mixed/negative/no-signal) + a short **narrative** per selected name.
- Every claim maps to a listed, **dated** source; source classes present/omitted are labeled.
- A selected symbol with no coverage ⇒ explicit **no-signal** / "symbol not found" — never fabricated.
- Re-running the same selection on an unchanged snapshot ⇒ **byte-identical** label + narrative and
  **$0** additional spend (served from the captured store).
- **Nothing runs for non-selected names**; nothing generates without the explicit trigger.

### Budget behavior
Watch `period_spend_usd` vs `monthly_cap_usd` in the response. When the cap is reached, names degrade
to `narrative_source: "template"` + `budget_state: "budget_exhausted"` (source-only, deterministic);
spend never exceeds the cap. To test, set `SCREENER_SENTIMENT_MONTHLY_CAP_USD=0.001`.

## 4. Determinism, no-directive, disclaimer checks
```
# backend suites (from repo root)
py -3.12 -m pytest backend/tests -q
# frontend lints (extended to the new /sentiment surface)
cd frontend && npm.cmd run test && npx playwright test no-directive-copy disclaimer-everywhere
```
- `no-directive-copy.spec.ts` now sweeps `/sentiment` — the narrative must contain zero directive
  terms (the sentiment surface is **not** exempt like the personal-use advisor preview).
- `disclaimer-everywhere.spec.ts` confirms `data_as_of` + disclaimer on the sentiment surface.
- Sentiment label lexicon has golden-fixture tests; Bug B regime has determinism + reason tests.

## 5. Hosted deployment notes
- The report runs hosted (owner-secret gated) but is **light + owner-triggered** — it is not the
  blocked `POST /data/refresh` heavy ingest. The captured-report store is **runtime-writable** and
  never writes the read-only baked snapshot (atomic-snapshot serving intact).
- Determinism holds via the captured artifact for the life of the deployment; a redeploy (which also
  refreshes the snapshot) may re-author a name's narrative — expected and documented.
- `personal_use_directive()` stays forced OFF in hosted mode; `ANTHROPIC_API_KEY` is a hosted runtime
  secret only.
- Bug B's daily-baked `spy_history.parquet` and Bug C's reseeded econ calendar are produced by the
  daily refresh and baked into the image (as today) — the fixes make both surfaces stay fresh
  without owner action.

## 6. Green-build gate
End on a suite-green commit: backend pytest, frontend Vitest, and the no-directive / disclaimer /
determinism Playwright specs all pass, with the sentiment overlay disabled-by-default
(`SCREENER_SENTIMENT_ENABLED=0`) so the byte-identical baseline is preserved (SC-008).
