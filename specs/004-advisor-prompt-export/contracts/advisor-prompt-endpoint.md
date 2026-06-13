# Contract: Advisor Prompt Endpoint

A read-only endpoint on the existing `analyze` router. Generates the prompt on
demand; persists nothing.

## Request

```
GET /analyze/{ticker}/advisor-prompt?strategy=midterm_52w_high_momentum&as_of={YYYY-MM-DD}
```

- `ticker` (path, required): symbol; upper-cased server-side.
- `strategy` (query, optional, default `midterm_52w_high_momentum`): v1 supports
  only this strategy. Any other value → `400` (mirrors the analyze endpoint).
- `as_of` (query, optional): pin to a snapshot date for determinism.

## Response 200

```json
{
  "ticker": "AMAT",
  "strategy": "midterm_52w_high_momentum",
  "personal_use_directive": false,
  "prompt": "<full copy-ready text per advisor-prompt.schema.md>",
  "data_as_of": "2026-06-12T00:00:00Z",
  "disclaimer": "This product is for informational purposes only ..."
}
```

- `prompt`: the complete artifact; the only field the UI copies.
- `personal_use_directive`: echoes the resolved flag so the UI can label the
  preview and apply the scoped lint exemption.
- `data_as_of` + `disclaimer`: required on every data-bearing response
  (constitution I/V), consistent with sibling endpoints.

## Errors

- `404` — ticker not found in the snapshot, or insufficient indicator data to
  derive levels (same conditions as `GET /analyze/{ticker}`). When levels are
  unavailable the endpoint returns 404 rather than a prompt with fabricated
  numbers (FR-017).
- `400` — unsupported `strategy`.

## Guarantees

- Same `ticker` + `as_of` + flag → byte-identical `prompt` (FR-011, SC-004).
- The `prompt` satisfies `advisor-prompt.schema.md` in full.
- Numbers in `prompt` equal those from `GET /analyze/{ticker}` for the same
  inputs (SC-005).
