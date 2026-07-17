# Contract: `brief_directive_enabled()` — Single-Owner Directive Carve-Out

Function: `backend/src/lib/flags.py :: brief_directive_enabled() -> bool`. Implements the
constitution v1.2.0 single-owner-gated carve-out (FR-007/FR-007a). It is **separate** from
`personal_use_directive()`; that helper and its hosted force-OFF are left unchanged, so no other
surface's directive behavior moves.

## Truth table

`brief_directive_enabled()` returns **True** only when **all** conditions hold; otherwise False.

| Condition | Source | Required value |
|---|---|---|
| Personal-use directive flag ON | `SCREENER_PERSONAL_USE_DIRECTIVE` | truthy |
| Single-owner access gate enforced | `hosting.owner_secret()` is set (hosted single-email allowlist fronts all routes) | not None |
| Not multi-user / shared | no multi-user flag set (single-owner deployment) | single-owner |

| PERSONAL_USE_DIRECTIVE | owner_secret set | Result |
|:---:|:---:|:---:|
| off | — | **False** (neutral) |
| on | no | **False** (neutral — no enforced gate ⇒ FR-006 default) |
| on | yes | **True** (directive permitted) |

Note: unlike `personal_use_directive()`, this helper does **not** return False merely because
`hosted_mode()` is True — that is the whole point of the carve-out. The gate is the *owner-secret
access control*, which is exactly what proves the output reaches only the owner.

## Effect on the brief

- **True** ⇒ recommendations + copy may use direct action language; each directive recommendation
  attaches its strategy citation(s); the brief still carries `data_as_of` + non-advice/limitations
  disclosure (FR-007).
- **False** ⇒ neutral, non-directive framing across the whole brief; the recommendation section is
  still rendered with all five items (FR-007a — degrade framing, never drop the section). No
  directive verb appears (SC-004, lint-tested).

## Tests (`backend/tests/brief/test_directive_carveout.py`)

1. Truth table above — each row asserted.
2. With the carve-out True, a rendered brief may contain direct verbs **and** every directive
   recommendation carries a citation; with it False, the no-directive lint passes on the whole
   rendered brief.
3. `personal_use_directive()` (the general-UI helper) still returns False under `hosted_mode()`
   regardless of `brief_directive_enabled()` — proving the carve-out did not broaden directive
   output to any other surface.
