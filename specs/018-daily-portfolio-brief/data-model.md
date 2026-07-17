# Phase 1 Data Model: Daily AI Portfolio Brief

All new entities live in `backend/src/models/brief.py` (Pydantic v2). They are **synthesis
containers** over existing outputs — no new financial field is computed here. Money/percent
fields reuse the existing `models/portfolio.py` conventions (`Decimal` money, quantized).

## BriefModel

The fully-assembled, deterministic content for one target session (produced by
`brief/assemble.py`, consumed by `brief/render.py`).

| Field | Type | Notes |
|---|---|---|
| `target_session` | `str` (ISO date) | The completed session the brief reports on = snapshot `data_as_of`. |
| `generated_at` | `str` (ISO datetime, UTC) | Wall-clock generation time — presentational only; **excluded from the determinism hash** so re-runs on the same snapshot compare equal (FR-013). |
| `portfolio` | `PortfolioStatusSection` | Value, P&L, risk exposure/heat, attention list. |
| `news` | `list[NewsItem]` | News/sentiment items over held + watched tickers, since last brief (Decision 7). May be empty ⇒ "nothing material" copy (FR-004, US2 AC2). |
| `market_context` | `MarketContextLine` | Regime + market-events summary with source + as-of. |
| `recommendations` | `list[RecommendationItem]` | **Exactly 5**, priority-ordered (FR-005, SC-003). |
| `directive` | `bool` | Whether directive framing applied (result of `brief_directive_enabled()`). Drives copy + which disclosures render. |
| `data_as_of` | `str` | Newest as-of across composed sections (FR-008). |
| `disclaimer` | `str` | `DISCLAIMER_TEXT`. |
| `warnings` | `list[str]` | Active integrity/staleness warnings surfaced verbatim (FR-008). |
| `citations` | `list[str]` | Strategy citation(s) referenced by any directive item (FR-007). |

**Validation**: `len(recommendations) == 5` is enforced at construction (raises otherwise) —
the renderer never emits a brief with a different count.

## PortfolioStatusSection

| Field | Type | Notes |
|---|---|---|
| `total_value` | `Decimal` | From `PortfolioTotals.total_invested` (mark-to-market basis). |
| `realized_pnl` / `unrealized_pnl` / `total_pnl` | `Decimal \| None` | From `PortfolioTotals` (feature 016). `None`/0 with no closed lots. |
| `win_rate` | `float \| None` | From `PortfolioTotals`. |
| `total_capital_at_risk_pct` / `heat_ceiling_pct` / `heat_headroom_pct` | `float` | From `PortfolioTotals`. |
| `holdings` | `list[HoldingLine]` | Per-holding ticker, quantity, avg cost, current price, per-holding P&L, status. |
| `attention` | `list[AttentionItem]` | Holdings needing attention (see below). |
| `is_empty` | `bool` | True when the owner has no open holdings ⇒ explicit "portfolio is empty" copy, never a silent failure (US1 AC3). |

## AttentionItem

One holding flagged as needing attention. Ordered by the same precedence the recommendation
ranker uses (risk/heat breach > stop proximity > pipeline stage change).

| Field | Type | Notes |
|---|---|---|
| `ticker` | `str` | |
| `reason_code` | `enum` | `heat_breach` \| `risk_breach` \| `stop_proximity` \| `stage_change`. |
| `detail` | `str` | Neutral one-line fact (e.g. "within 3% of stop", "stage: ready → staged"). |
| `severity` | `int` | Rank tiebreaker within a reason class (deterministic). |

## NewsItem

A single dated news/sentiment signal mapped to the ticker(s) it affects (spec: News/Sentiment
Item). Sourced from the feature-014 pipeline; **not** re-derived here.

| Field | Type | Notes |
|---|---|---|
| `tickers` | `list[str]` | Affected held/watched ticker(s). |
| `headline` | `str` | Item title. |
| `sentiment_label` | `str \| None` | From the captured `SentimentReport` (`positive`/`negative`/`neutral`/`no_signal`). |
| `source` | `str` | Provider/source tag (FR-004 — each item carries its source). |
| `as_of` | `str` (ISO) | Item as-of date (FR-004). |
| `narrative_risk_label` | `str \| None` | Neutral non-directive narrative-risk label if present. |

## MarketContextLine

| Field | Type | Notes |
|---|---|---|
| `regime` | `str` | From `current_regime_response().regime`. |
| `regime_detail` | `str` | Concise regime verdict (e.g. SPY vs 200-SMA). |
| `market_events` | `list[str]` | Near-term FOMC/CPI/NFP/etc. from `EventsService`. |
| `source` | `str` | Source tag(s). |
| `as_of` | `str` (ISO) | As-of date (FR-004 US2 AC3). |

## RecommendationItem

One of **exactly five** prioritized entries (spec: Recommendation Item). Produced by
`brief/recommend.py`; wording gated by `directive`.

| Field | Type | Notes |
|---|---|---|
| `rank` | `int` | 1..5, ascending priority. |
| `subject` | `str` | The specific ticker **or** a portfolio-level action label. |
| `subject_kind` | `enum` | `holding` \| `watchlist` \| `portfolio`. |
| `reason` | `str` | One-line reason grounded **only** in facts already present in the brief (FR-005 — no fabricated signals). |
| `source_signal` | `enum` | `attention` \| `news_sentiment` \| `portfolio_action` — which ranking tier produced it (auditable, documented in `recommend.py`). |
| `citations` | `list[str]` | Strategy citation(s) for a directive item (FR-007); empty in neutral mode. |
| `text` | `str` | Rendered copy — neutral ("candidate for review", "consider reviewing") when `directive` is False; may use direct action language when True. **Lint-checked** to contain no directive verb in neutral mode (SC-004). |

**Selection & ordering invariant** (documented constants in `recommend.py`, tested):
1. Holdings-attention triggers first, in precedence `risk_breach`/`heat_breach` → `stop_proximity`
   → `stage_change`.
2. Then news/sentiment materiality (strongest signal over held → watched tickers).
3. Then portfolio-level actions to fill exactly five (e.g. "no action indicated for X",
   heat-headroom note) — never fabricating a signal (FR-005, US3 AC4).
Ties break deterministically on `(severity desc, ticker asc)` so the same snapshot + portfolio
yields identical ordering (FR-013).

## BriefDeliveryRecord (Delivery Run Record)

Persisted in `brief_runs.json` under `SCREENER_DATA_DIR` (Decision 2). Powers idempotency
(FR-010) and `GET /brief/status` (FR-014).

| Field | Type | Notes |
|---|---|---|
| `target_session` | `str` (ISO date) | Idempotency key. At most one `delivered` record per session. |
| `status` | `enum` | `delivered` \| `skipped` \| `failed`. |
| `recipient` | `str` | Must equal `SCREENER_BRIEF_RECIPIENT` (FR-009). |
| `reason` | `str \| None` | Skip reason (non-trading day) or failure detail (redacted — never the app password). |
| `attempts` | `int` | Send attempts made (FR-012). |
| `directive` | `bool` | Whether the delivered brief used directive framing. |
| `content_hash` | `str` | SHA-256 of the determinism-relevant `BriefModel` fields (excludes `generated_at`) — lets `GET /brief/status` and tests assert determinism (SC-005). |
| `timestamp` | `str` (ISO datetime) | When the run completed. |

## Response models (API surface)

- **`BriefRunResponse`** — `{ status, target_session, record: BriefDeliveryRecord, data_as_of, disclaimer }`.
- **`BriefStatusResponse`** — `{ enabled: bool, last_run: BriefDeliveryRecord | null, data_as_of, disclaimer }`.

## Configuration (runtime env only — never persisted/committed, FR-015)

| Env var | Purpose | Default |
|---|---|---|
| `SCREENER_BRIEF_ENABLED` | Master gate (`brief_enabled()`). | `0` (OFF) |
| `SCREENER_PERSONAL_USE_DIRECTIVE` | Existing flag; one of the three conditions for the directive carve-out. | `0` |
| `SCREENER_BRIEF_SMTP_HOST` | Gmail SMTP host. | `smtp.gmail.com` |
| `SCREENER_BRIEF_SMTP_PORT` | SMTP port (STARTTLS). | `587` |
| `SCREENER_BRIEF_SMTP_USER` | SMTP username (sender). | — (required when enabled) |
| `SCREENER_BRIEF_SMTP_PASSWORD` | Gmail **app password**. | — (required when enabled) |
| `SCREENER_BRIEF_RECIPIENT` | Single allowlisted owner address. | — (required when enabled) |
