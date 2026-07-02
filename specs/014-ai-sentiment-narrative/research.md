# Phase 0 Research: AI Sentiment & Narrative Intelligence (+ 3 bug fixes)

All decisions honor the constitution's non-negotiables: data provenance (Principle I),
determinism / reproducibility (Principle III), and the no-advice boundary (Principle V).
"Search for free or low-budget options" (spec) is executed here — it is a planning
instruction, not a user-facing search feature.

---

## Decision 1 — Sentiment/narrative **data sources** (bounded, labeled, fail-soft)

**Decision.** Draw sources only from an explicitly bounded, owner-disclosed set, each class
individually labeled on the report and omitted (never fabricated) when unavailable:

| Source class | Provider | Cost / key | Notes |
|---|---|---|---|
| Free news headlines (primary) | `yfinance` `Ticker.news` | Free, **no key** (already a dependency) | Title, publisher, link, publish time. Zero-config baseline. |
| News backup A | **Finnhub** company-news | Free (60/min); **key available** | Headlines only (the news-*sentiment* endpoint is premium — we score locally, so we don't need it). Reliability backup for the scrapey yfinance feed. |
| News backup B | **Alpha Vantage** `NEWS_SENTIMENT` | Free 25/day; **key available** | Headlines **plus** a vendor ticker-sentiment score used only as an optional *cross-check* against FinBERT — never as the label (opaque weights → Principle II). |
| Corporate events / filings | **existing** EDGAR 8-K + earnings pipeline (`events/service.py`) | Free (already ingested) | Reuse `TickerEventsSnapshot`; 8-K **item codes** feed regulatory/legal severity (Decision 10). |
| Analyst opinion / revisions | `yfinance` `upgrades_downgrades` / Finnhub `recommendation-trends` | Free | Labeled "analyst opinion (free feed)". |
| Earnings transcripts | **deferred / omitted** | — | No free, licensing-permissible full-transcript source (Seeking Alpha paywalled, Finnhub transcripts premium, scraping = ToS risk). Approximate "management tone" from the EDGAR 8-K / earnings press-release text; mark the transcript component omitted until a licensed source exists. |
| Social / retail sentiment | **deferred / omitted** | — | Reddit/StockTwits APIs are OAuth/commercial-restricted and stream-mutating (breaks determinism). Added later only under the same bounded-source rule, marked low-signal/noisy (FR-S10). Note: this is the class the narrative-risk *source-migration* and *bot-amplification* signals depend on (Decision 10). |

**Provider chain (fail-soft, FR-S7/S10).** Primary = yfinance (no key); backups = Finnhub then
Alpha Vantage (keys the owner has provided, runtime env only). Configurable via
`SCREENER_SENTIMENT_NEWS_PROVIDERS="yfinance,finnhub,alphavantage"`; a provider that is down, out of
quota, or keyless is skipped, never fabricated. Each contributing class is labeled on the report.

**Rationale.** Baseline needs **no key**; the owner-supplied Finnhub/Alpha Vantage keys add
redundancy and, via Alpha Vantage, a free vendor-sentiment *cross-check* (displayed as a second
opinion, not the label). Every item stays attributable + dated (FR-S2). Transcripts and social are
the two classes with no clean free/licensed source today, so they are omitted, not faked (Principle I).

**Keys.** Finnhub / Alpha Vantage keys are runtime env only, never written to any artifact
(api-keys-never-write rule; `scripts/secret_scan.ps1` release check).

---

## Decision 2 — Sentiment **label/score**: FinBERT (captured) + lexicon fallback

**Decision.** Compute the coarse label (positive / mixed / negative / no-signal) and its numeric
`score = P(positive) − P(negative)` with **FinBERT** (ProsusAI `finbert`, HF), a finance-tuned model,
run **locally and offline** over the collected, dated source titles/summaries. It's free (no
recurring cost), inspectable (Principle II — score is a documented probability difference), and its
argmax label is robust. A vendored **Loughran-McDonald lexicon** is the zero-dependency fallback
(and the hosted-tier default — see Decision 3 on deps). "Mixed" = both positive and negative evidence
clear a threshold on the same window; "no-signal" = no qualifying source data (FR-S6).

**Determinism (Principle III / SC-004).** Neural inference isn't guaranteed byte-identical across
hardware, so FinBERT's per-item scores are **captured into the fingerprinted store** (same capture-
once mechanism as the narrative) and served verbatim thereafter. Pin the model **revision** and run
eval/greedy. The lexicon fallback is deterministic by construction (no capture needed).

**Rationale.** FinBERT beats a generic lexicon on finance text (correctly scores "liability",
"crude", "guidance cut") while staying free and offline — a better fit than the LLM for the *label*,
which must be transparent and reproducible. Golden-fixture tested against the three worked examples
(guidance raise → +, SEC investigation → −, conference participation → neutral) (Principle IV).

**Time-window composite.** Aggregate captured per-item scores into 24h / 7d / 30d / 90d windows with
**recency weighting** (fresh negative news must not be cancelled by stale positive news); the 90-day
window matches the 60–180-day hold horizon. Composite ≈ `0.40·7d + 0.25·30d-trend +
0.20·earnings/press-release tone + 0.15·analyst-revision`, with **missing components renormalized**
(transcripts will often be absent) rather than injected as zeros. The composite is **presentation-
only** — it never feeds a gate, rank, or sizing (FR-S3, SC-008).

**Alternatives considered.** LLM classification for the label — rejected: non-deterministic and
would force capture for a value FinBERT/lexicon give more transparently. Vendor scores (Alpha
Vantage) — used only as an optional displayed *cross-check*, never the label (opaque weights →
Principle II).

---

## Decision 3 — Narrative **prose**: optional LLM, provider-swappable, capture-once, cap-gated

**Decision.** The plain-language storyline (FR-S1) is generated **once** on a cache miss and captured
verbatim (never regenerated per view). Because the scorer is FinBERT and the narrative-risk module is
rules-based (Decision 10), the LLM is **optional prose only** — it is given *only* the collected,
dated source items and instructed: zero directive language, no claim without a listed source
(FR-S2/S4); output is validated against the no-directive vocabulary before storage. Two paths:

1. **`template` (default, $0, deterministic)** — a structured "Recent sources: …" narrative assembled
   from the dated items. Always available; also the degrade path when budget/outage hits.
2. **`model` (optional prose)** — provider-swappable via `SCREENER_SENTIMENT_LLM_PROVIDER`:
   - **Gemini Flash-tier (e.g. Flash-Lite) — default when a key is present.** The owner has a Gemini
     key with a **free tier**, so nice prose costs **$0** within free-tier limits; SDK `google-genai`.
   - **Claude Haiku 4.5 (`claude-haiku-4-5`, $1/$5 per 1M) — alternative**, ≈ **$0.0035/ticker**, so
     the ~$5/month cap still funds ~1,400 reports/mo if chosen.

Provider choice does **not** affect determinism: whichever model runs, its output is captured-once
under the report fingerprint (Decision 4) and served byte-identically thereafter (FR-S5, SC-004).

**Rationale.** The scorer needs no LLM, so the LLM is a presentation nicety — use the resource the
owner already has (free-tier Gemini) and keep Claude Haiku as a drop-in alternative. Prose is a
transform over already-licensed source text, not a new data provider (Principle I note in plan).

**Alternatives considered.** LLM-only (no FinBERT) — rejected: pushes the *scoring* into a non-
deterministic, metered path. Larger models (Gemini Pro / Claude Sonnet/Opus) — unnecessary for short
extractive summarization.

---

## Decision 4 — **Determinism mechanism**: capture-once + fingerprint-keyed durable store

**Decision.** LLMs are not deterministic, and FR-S5 / SC-004 require *same snapshot + same ticker →
byte-identical label and narrative*. So the served result is **authored once and stored**, never
regenerated per view. A report is keyed by a **fingerprint**:

```
fingerprint = sha256( ticker
                    + sorted(source_item_ids_with_dates)
                    + snapshot_data_as_of
                    + model_id
                    + prompt_version )
```

On request: if the fingerprint exists in the store → serve the captured artifact verbatim (no model
call, no spend). If not → collect sources, compute the deterministic label, generate the narrative
(budget permitting), and **persist** the artifact under that fingerprint. New source data, a new
snapshot, a model change, or a prompt-version bump all yield a *new* fingerprint (a new, then-stable
capture) — old artifacts stay reproducible.

**Rationale.** This is precisely the constitution's "non-determinism MUST be captured/recorded"
requirement (Principle III) and the spec's FR-S5 "any non-deterministic generation MUST be
captured/snapshotted so the served result is stable and re-inspectable." The label needs no capture
(deterministic by construction); only the narrative does. Store = SQLite at
`backend/data/sentiment/reports.sqlite`.

**Alternatives considered.** `temperature=0` on the LLM — rejected: never guaranteed byte-identical,
and Claude 4.x models don't accept sampling params anyway. Baking reports into the image like the
SPY parquet — impossible: on-request tickers aren't known at bake time.

---

## Decision 5 — **Budget enforcement**: pre-call projection + graceful degrade

**Decision.** A persisted monthly ledger (`backend/data/sentiment/spend.json`, keyed by `YYYY-MM`)
records estimated spend. **Before every paid generation**, project the call's cost (token estimate ×
the **active provider's** rates — $0 on the Gemini free tier, Haiku list rates if Claude) and compare
against the remaining monthly allowance (`SCREENER_SENTIMENT_MONTHLY_CAP_USD`,
default `5.00`). If the projection would exceed the cap, **do not call the model**: degrade that name
to a deterministic, source-only template narrative ("Recent sources: …" listing the dated items) with
the lexicon label still shown, and mark the report `budget_exhausted`. The owner is told the quota is
spent; spend never exceeds the cap (FR-S9, SC-007). Cache hits cost $0 and are always served.

**Rationale.** A hard pre-call cap is the only way to *guarantee* the cap is never exceeded (a
post-hoc counter can overshoot). Degrade-not-fail keeps the app fully usable (FR-S7).

---

## Decision 6 — **Hosted-mode posture** for on-request generation

**Decision.** The report runs in hosted mode too, but stays within feature 010's guarantees.
Verified against the live pipeline (GitHub Actions `daily-refresh.yml` → `publish_chain.ps1` →
GHCR image → **HF Space** `occlusion2/screener` backend + **Vercel** BFF frontend). See
[contracts/deploy-finbert.md](./contracts/deploy-finbert.md) for the full compatibility contract.

- **BFF routing — no change.** The Vercel proxy (`api/proxy/[...path]`) forwards any path + `POST`,
  injects `X-Owner-Secret`, and requires a NextAuth session in hosted mode. `POST /sentiment/report`
  works unchanged; the new router just registers in `app.py` (owner-secret middleware gates all).
- **Light + owner-triggered.** A few free fetches + at most one cheap LLM call — not the blocked
  heavy `POST /data/refresh` ingest. FinBERT scoring is **ONNX INT8 (~100 MB) on CPU**, baked into
  the image and run offline (no runtime HF Hub fetch → FR-006 respected). Keep the runtime image
  slim: `onnxruntime` + `tokenizers` + `google-genai` in `pyproject` deps; **`torch` never in the
  image** (export-only extra used once to produce the ONNX). Hosted-light fallback:
  `SCREENER_SENTIMENT_SCORER=lexicon` keeps the image byte-identical and scores in-host.
- **Model baked like the snapshot.** `backend/data/` is gitignored (snapshot is *generated* by the
  publish chain, not committed), so a new `scripts/export_finbert_onnx.py` step writes
  `backend/data/finbert_onnx/` before the docker build, and the Dockerfile adds a scoped `COPY` —
  same pattern as `regime/`, `edgar_cache/`. No Git LFS.
- **Never writes the read-only baked snapshot.** The captured-report store lives in
  **`backend/data/cache/`** — already `.dockerignore`d + gitignored, so runtime-writable and never
  part of the atomic-swapped snapshot (FR-006 untouched).
- **Secrets in two places.** Runtime keys (`GEMINI_API_KEY`, `ALPHAVANTAGE_API_KEY`, `FINNHUB_API_KEY`)
  are **HF Space** secrets (backend runtime), distinct from the GitHub secrets used for CI/build.
  Env-only, never written to any artifact (`secret_scan.ps1` publish-chain gate stays green).
- **Envelope + directive.** `data_as_of` + `disclaimer` via existing middleware;
  `personal_use_directive()` forced OFF (hosted).
- **Determinism across rebuilds.** Fingerprints include `snapshot_data_as_of`; the daily factory-
  rebuild (new snapshot + fresh ephemeral cache) re-authors reports cleanly — stable within a day /
  deployment. Cross-rebuild persistence would need HF paid storage (not required).
- **Deploy trigger.** Code + baked model, no new trading session ⇒ ship via the existing code-only
  path: `workflow_dispatch` `force_rebuild=true` (`-SkipGuard`).

**Rationale.** Single-owner, gated, light, snapshot-safe, slim-image — fully consistent with the
010/011 hosted clause and the verified GitHub→GHCR→HF→Vercel pipeline.

---

## Decision 7 — **Bug B** root cause & fix (SPY 200-day SMA / regime "Unknown")

**Root cause.** `screening/regime.py::_load_spy` returns the **yfinance** frame whenever it is
non-empty and never falls through — even if that frame is short or partial (rate-limited). The
consumers (`market_regime`, `calculator._spy_inputs`) then return **Unknown** because
`len(close) < sma_length`, *ignoring the good daily-baked `spy_history.parquet`* that has full
history. Separately, `calculator._spy_inputs` returns a bare `spy_above=None` with no reason, and
the API caches that Unknown for a day.

**Fix (deterministic, no baseline change — FR-B1/B2/B3).**
1. `_load_spy` selects the source that actually yields **≥ `sma_length` usable rows** — prefer
   yfinance only when its frame is long enough; otherwise fall through to `baked(daily)` then
   `stooq(local)`. (Optionally merge yfinance's latest close onto the baked series so the displayed
   close is current while the SMA is computable.)
2. When the SMA genuinely can't be computed (true insufficient history), surface the **specific
   reason** and state the gate fails open — never a bare "Unknown" (FR-B2). `RegimeInputs` /
   `RegimeResponse` gain/propagate a concrete reason string + the SPY source + as-of (already
   partly present as `price_source_name`).
3. Frontend `RegimePanel` renders the numeric close/SMA/verdict/source/as-of, or the explicit reason.
4. The regime response cache does **not** persist an Unknown produced by a transient short frame
   (only cache a fully-resolved reading), so a one-off rate-limit doesn't pin Unknown for a day.

Golden-fixture tests: injected long baked frame + empty yfinance → numeric SMA + verdict; genuinely
short series → explicit reason (not "Unknown"); same snapshot twice → identical (determinism).

---

## Decision 8 — **Bug C** root cause & fix (Market Events "Stale events data" / empties out)

**Root cause.** The macro calendar is a **static curated YAML** (`backend/data/econ_calendar.yaml`,
`source_as_of: 2026-06-11`, `refresh_interval_days: 7`). The daily job's `seed_econ_calendar()`
re-seeds from that YAML but stamps `upsert_event_source(last_refreshed_at = payload.source_as_of)` —
the **static** date — so the derived-staleness check (`now - last_refreshed_at > 7 days`) trips ~7
days after 2026-06-11 (today is 2026-07-02 → already flagged). The finite hardcoded event list also
**empties out** as its dates pass, so the panel shows "No scheduled events in this window."

**Fix (presentation + freshness only — no strategy impact).**
1. On reseed, stamp `last_refreshed_at = now` (the reseed genuinely happened today) so a re-seeded,
   still-valid curated calendar is **not** spuriously flagged stale. Keep the YAML's `source_as_of`
   as the *content* as-of (surfaced separately), distinct from the *refresh* time.
2. Extend the curated window so it doesn't empty out: roll the published Fed/BLS/BEA schedules
   forward with **real, officially-published dates only** (constitution: no fabricated dates) — the
   recurring FOMC/CPI/NFP/PCE/PPI cadence has published annual schedules; when official schedules
   stop, the calendar stops (labeled), never projects fake dates.
3. `ingest_daily.py` already calls `seed_econ_calendar()`; the timestamp fix makes the daily deploy
   keep the panel fresh. `MarketEventsPanel` shows the stale badge **only** when the source is truly
   past its refresh interval, and shows a clear "schedule extends to <last real date>" when the
   curated window ends rather than a bare empty state.

**Rationale.** Honest freshness: distinguish "re-seeded today from a curated file" (fresh) from
"content genuinely old" (stale), and never fabricate macro dates (Principle I).

---

## Decision 10 — **Narrative Intelligence** module: feasible signals + non-directive labels

**Concept.** Distinct from sentiment (is the tone +/−?), narrative intelligence asks *is a story
forming, spreading, and escalating?* It produces a **`narrative_risk` score (0–100)** from detected
signals over the dated source set. It is **presentation-only** — it never demotes a candidate,
changes a gate, alters ranking/sizing/regime, or touches a backtest (FR-S3, SC-008).

**Feasible-now vs deferred signals** (clean public sources only, at first):

| Signal | Now (EDGAR + news) | Needs the deferred social layer |
|---|---|---|
| Repeated negative theme | ✅ across news + filings | |
| Regulatory/legal severity | ✅ 8-K item codes (e.g. 8.01, 4.02, 5.02) + keywords | |
| Velocity spike (mention count over time) | ⚠️ partial (news volume) | fuller via social |
| Credibility escalation (rumor→analyst→mainstream) | ⚠️ partial | |
| **Source migration** (low-quality → mainstream) | | 🔴 requires social/low-quality tier |
| **Bot-like amplification** | | 🔴 requires social; ToS/licensing minefield |

Ship the feasible subset first; **source-migration and bot-amplification are computed only once the
social layer exists** — not estimated from data we don't have (Principle I). Signals are captured
alongside the report so the score is reproducible (Principle III).

**🔴 Non-directive labels (Principle V / FR-S4 — the required correction).** The proposed score→
meaning table used directive trading language ("avoid new entry", "review existing position"), which
the no-directive copy lint forbids and which would push the overlay from informational toward
decision-affecting. The score and detected signals are fine to *display*; the action labels are
reworded to neutral descriptions:

| Score | Neutral, constitution-safe label |
|---|---|
| 0–20 | Low narrative activity |
| 21–40 | Monitor — mild recurring themes |
| 41–60 | Elevated — multiple fresh negative themes across sources |
| 61–80 | High — themes repeating and escalating across sources |
| 81–100 | Very high narrative risk — repeated regulatory/legal themes escalating across sources |

(The single-owner personal-use directive flag *could* legally re-enable take/pass phrasing locally,
but it is OFF by default and **non-waivable in hosted mode**, so the neutral wording is what ships.)

**Rationale.** Captures the genuinely valuable "is a dangerous story forming?" signal within
Principles I, III, and V — feasible signals only, deterministic + captured, and worded so it informs
without instructing.

---

## Decision 9 — **Bug A** design (add-to-watchlist parity + confirmation)

**Decision.** Extract a shared `AddToWatchlist` control used by both `CandidateRow` (table) and the
candidate **detail page** (which today only offers "Add to portfolio"). It calls the existing
`saveCandidate` store action (already idempotent per `ticker+strategy_slug` — see `store.ts`), shows
an **immediate visible confirmation** at the point of action, and, on a duplicate, informs the owner
it is already watched (FR-A1/A2/A3/A4). No backend change — the watchlist is browser-persisted; the
levels snapshot + originating strategy are already captured by `saveCandidate`.

**Rationale.** Smallest, highest-certainty fix; reuses the existing idempotent store and levels
snapshot; the only gaps are the missing detail-page control and the missing confirmation feedback.
