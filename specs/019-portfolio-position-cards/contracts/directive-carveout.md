# Contract: Card-instruction single-owner directive gate

Governs whether the position card may render Hold/Trim/Sell **verbs** (FR-008), per constitution
v1.2.0 Principle V and the feature-018 precedent.

## Gate predicate (backend, `lib/flags.py`)

`directive_enabled` on the `/portfolio/holdings` response is **true iff ALL** hold — identical to
`brief_directive_enabled()`:

1. `SCREENER_PERSONAL_USE_DIRECTIVE=1` (personal-use directive flag ON), **and**
2. `hosting.owner_secret()` is set — the enforced single-owner access gate fronting every route
   (feature 010 BFF allowlist), **and**
3. not multi-user (`SCREENER_MULTI_USER` not truthy).

Implementation reuses the existing single-owner-carve-out logic rather than the hosted-force-OFF
`personal_use_directive()`. Factor the shared body into a private predicate so the card gate and
`brief_directive_enabled()` cannot drift.

## Behavior

| Condition | `directive_enabled` | Card shows |
|-----------|--------------------|------------|
| All three above satisfied | `true` | Neutral `status_label` **and** the `hold`/`trim`/`sell` verb + rationale |
| Personal-use flag off | `false` | Neutral `status_label` only (no verb) |
| No owner secret (unguarded) | `false` | Neutral `status_label` only |
| Multi-user | `false` | Neutral `status_label` only |

- Default is OFF (neutral). The instruction/recommendation section is **never dropped** — only the
  verb is withheld (FR-006/FR-008 parity with 018).
- Even when ON, every card carries the strategy citation context, `data_as_of`, and the non-advice
  disclaimer (FR-012, constitution V).

## Tests

- Flag off / no owner secret / multi-user ⇒ `directive_enabled=false` and **zero** directive verbs
  in the serialized response (also enforced by the Playwright no-directive lint on the rendered page).
- All-satisfied ⇒ `directive_enabled=true` and verbs present.
- The card gate and `brief_directive_enabled()` return the same value for the same env (shared-predicate test).
