# Contract: Deterministic Five-Item Recommendation Ranking

Module: `backend/src/brief/recommend.py`. Pure function
`select_recommendations(brief_inputs, *, directive: bool) -> list[RecommendationItem]` returning
**exactly five** items. Selection + ordering are deterministic (FR-005, FR-013); an AI narrative
model may only *phrase* the already-selected items (in `render.py`), never select or add signals.

## Ranking algorithm (documented constants in the module)

Build a candidate pool from existing signals, assign each a `(tier, sub_priority, tiebreak)`
sort key, sort ascending, take the top five. If fewer than five candidates exist, fill from the
portfolio-level tier (never fabricate).

**Tier 1 — Holdings attention** (highest priority). One candidate per `AttentionItem`:
- sub-priority: `risk_breach` = `heat_breach` (0) → `stop_proximity` (1) → `stage_change` (2).
- tiebreak: `(severity desc, ticker asc)`.

**Tier 2 — News/sentiment materiality.** One candidate per held/watched ticker with a material
news/sentiment signal in the window:
- sub-priority by signal strength (held before watched at equal strength).
- tiebreak: `(|sentiment_composite| desc, ticker asc)`.

**Tier 3 — Portfolio-level fill.** Deterministic portfolio actions to reach five:
- heat-headroom note, then "no action indicated for <ticker>" over remaining holdings in ticker
  order, then a watchlist-review note. Always enough to fill five (US3 AC4).

**Global order**: Tier 1 items, then Tier 2, then Tier 3, truncated/filled to exactly five.
Ranks assigned 1..5 in that final order.

## Wording gate

- `directive == False` ⇒ each `text` uses neutral framing ("candidate for review", "consider
  reviewing", "within N% of stop") and contains **no** directive verb ("buy"/"sell"/"strong
  buy"). `citations` empty.
- `directive == True` ⇒ `text` may use direct action language; each item's `citations` carries the
  relevant strategy citation(s); the item still relies only on facts already in the brief.

## Tests (`backend/tests/brief/test_recommend.py`) — test-first

1. Always returns exactly five items for: rich portfolio, sparse portfolio (< 5 holdings), empty
   portfolio, quiet news day (SC-003, US3 AC4).
2. Attention triggers rank above news items, which rank above portfolio-level fill (tier order).
3. Sub-priority + tiebreak ordering is exactly as specified (golden fixture).
4. Same inputs ⇒ identical ordered output on re-run (determinism, FR-013).
5. Neutral mode passes the no-directive lint on every `text`; directive mode attaches citations
   and is permitted direct verbs (SC-004, FR-007).
6. Fill tier never invents a ticker/signal not present in the inputs (FR-005).
