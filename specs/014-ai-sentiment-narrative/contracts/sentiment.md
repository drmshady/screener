# Contract: POST /sentiment/report

On-request sentiment & narrative for **owner-selected** tickers only. Owner-secret gated in hosted
mode (like every router). Every response carries `data_as_of` + `disclaimer` (envelope middleware).
Informational-only: it never changes any gate result, rank, level, sizing, regime, or backtest.

## Request

```jsonc
POST /sentiment/report
{
  "selections": [
    { "ticker": "NVDA", "origin": "screener", "as_of": null },
    { "ticker": "COST", "origin": "holding" },
    { "ticker": "ZZZZ", "origin": "manual" }
  ]
}
```

- `selections` MUST be non-empty. An empty array ⇒ `400` with
  `{"detail": "Select at least one stock."}` (FR-S0c). Alternatively the frontend prevents the empty
  run; the backend still validates.
- `origin` ∈ `screener | holding | manual`. `manual` symbols are resolved independently of any
  screen/portfolio (FR-S0b).
- Only listed tickers are analyzed — **0 model/API calls for non-selected stocks** (SC-009).

## Response `200`

```jsonc
{
  "reports": [
    {
      "ticker": "NVDA",
      "origin": "screener",
      "label": "positive",                 // positive | mixed | negative | no_signal
      "label_basis": "FinBERT mean score +0.42 over 7 sourced items (P(pos)-P(neg)).",
      "sentiment_composite": 0.38,         // 24h/7d/30d/90d recency-weighted — presentation-only
      "narrative_risk": {                  // rules-based, neutral labels — presentation-only
        "score": 18,
        "label": "Low narrative activity",
        "signals": ["theme_repetition:low", "regulatory_severity:none"]
      },
      "narrative": "Recent coverage centers on ... (each claim maps to a listed source).",
      "narrative_source": "model",         // model (LLM, captured) | template | absent
      "budget_state": "ok",                // ok | budget_exhausted | unavailable
      "source_classes_present": ["news", "filing_8k", "analyst_opinion"],
      "source_classes_omitted": ["social", "earnings_transcript"],
      "sources": [
        { "id": "…", "source_class": "news", "title": "…", "publisher": "Reuters",
          "published_at": "2026-07-01T13:20:00Z", "reference_url": "https://…",
          "is_stale": false, "score": 0.61 }
      ],
      "fingerprint": "sha256:…"            // includes scorer_id + model_id + prompt_version
    },
    {
      "ticker": "ZZZZ",
      "origin": "manual",
      "label": "no_signal",
      "narrative_source": "absent",
      "budget_state": "unavailable",
      "resolution": "symbol_not_found",    // present only for unresolved manual symbols (FR-S0b)
      "sources": []
    }
  ],
  "period_spend_usd": 0.0140,
  "monthly_cap_usd": 5.00,
  "data_as_of": "2026-07-02T21:00:00Z",
  "disclaimer": "…"
}
```

## Guarantees

- **Determinism (FR-S5, SC-004).** For a given snapshot + ticker (same source set), `label` and
  `narrative` are byte-identical across runs — served from the fingerprint-keyed store, never
  regenerated. Re-posting the same selection returns the same artifacts and incurs **$0** additional
  spend.
- **Sourcing (FR-S2, SC-003).** Every narrative claim maps to a listed, dated `sources` item. No
  unsourced assertion appears. A `no_signal` name shows an explicit absent state (FR-S6) — never a
  fabricated neutral narrative (SC-005).
- **No directive language (FR-S4, SC-003).** `narrative`, `label_basis`, and every `narrative_risk`
  label contain zero directive trading terms; enforced by the existing copy lint extended to the
  sentiment surface, and validated server-side before a model narrative is stored.
- **Presentation-only (FR-S3, FR-S12, SC-008).** `label`, `sentiment_composite`, `narrative_risk`,
  and `narrative` never change a gate result, rank, level, sizing, regime, or backtest.
  `narrative_risk` omits any signal whose source is unavailable (e.g. the deferred social layer),
  never estimating it.
- **Fail-soft (FR-S7, SC-006).** A source/model outage sets that name's `budget_state:"unavailable"`
  and never blocks a screen, portfolio, or any other feature. Other selected names still return.
- **Budget cap (FR-S9, SC-007).** When a paid generation would exceed `monthly_cap_usd`, that name
  degrades to `narrative_source:"template"` + `budget_state:"budget_exhausted"` (deterministic,
  source-only). Spend never exceeds the cap.
- **Envelope + hosted (FR-S8).** `data_as_of` + `disclaimer` always present; owner-secret gated;
  `personal_use_directive()` forced OFF in hosted mode; captured store is runtime-writable and never
  touches the read-only baked snapshot.

## Errors

| Status | Condition |
|---|---|
| `400` | Empty `selections`. |
| `401` | Hosted mode, missing/incorrect owner secret (middleware). |
| `503` | Hosted mode misconfigured (missing owner secret). |

Per-name failures are **not** top-level errors — they are returned inside `reports[]` with
`budget_state:"unavailable"` / `resolution:"symbol_not_found"` so one bad name never fails the batch.
