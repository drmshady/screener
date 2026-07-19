"""Pure, deterministic Hold/Trim/Sell instruction mapper (Feature 019).

`derive_instruction` maps already-computed status facts — the current-condition
level status, distance to the stop, portfolio heat headroom, and (optionally) the
lifecycle stage — onto a neutral status label plus a gated directive verb. It is
**pure presentation over existing numbers** (FR-013): it introduces no new
indicator, gate, or threshold, and the AI sentiment score is never an input
(FR-007). Same inputs always produce the same `InstructionBlock` (determinism).

Precedence (research Decision 2):

1. **Levels unavailable** — `levels_state == "insufficient_data"` (or an
   insufficient level status): no verb, the card still renders with a label.
2. **Sell** — the current-condition stop is breached (`stop_breached`).
3. **Trim** — deteriorating but not breached: within ``NEAR_LEVEL_PCT`` of the
   stop, OR the portfolio heat ceiling is reached (`heat_headroom_pct <= 0`).
4. **Hold** — a healthy position, including the non-directive "let it run /
   protected" states (`target_reached` / `gains_protected`).

The Hold/Trim/Sell *verb* only appears when ``directive_enabled`` is True (the
single-owner directive carve-out, FR-008); otherwise the block carries the
neutral ``status_label`` and ``rationale`` only — the section is never dropped.
"""

from __future__ import annotations

from ..models.portfolio import InstructionBlock, InstructionInputs

# The existing 3% near-level threshold (the frontend's NEAR_LEVEL_PCT). Reused,
# not introduced — no new indicator or gate (FR-013).
NEAR_LEVEL_PCT = 0.03

_INSUFFICIENT = "insufficient_data"


def derive_instruction(
    *,
    level_status: str,
    levels_state: str = "ok",
    distance_to_stop_pct: float | None = None,
    heat_headroom_pct: float | None = None,
    stage: str | None = None,
    directive_enabled: bool = False,
) -> InstructionBlock:
    """Map status facts to a neutral label + a (gated) Hold/Trim/Sell verb.

    Keyword-only and intentionally narrow: the AI sentiment score is not among
    the parameters, so it cannot influence the verb (FR-007).
    """
    inputs = InstructionInputs(
        level_status=level_status,
        distance_to_stop_pct=distance_to_stop_pct,
        heat_headroom_pct=heat_headroom_pct,
        stage=stage,
    )

    # 1. Levels unavailable — no verb regardless of the carve-out (edge case).
    if levels_state == _INSUFFICIENT or level_status == _INSUFFICIENT:
        return InstructionBlock(
            status_label="Levels unavailable",
            directive=None,
            rationale="Levels unavailable — insufficient data to derive a stop or target.",
            inputs=inputs,
        )

    verb: str
    status_label: str
    rationale: str

    near_stop = distance_to_stop_pct is not None and abs(distance_to_stop_pct) <= NEAR_LEVEL_PCT
    heat_breached = heat_headroom_pct is not None and heat_headroom_pct <= 0

    if level_status == "stop_breached":
        # 2. Sell — the protective stop has been breached.
        verb = "sell"
        status_label = "Stop breached"
        rationale = "Current-condition stop breached."
    elif near_stop or heat_breached:
        # 3. Trim — deteriorating but not breached: reduce exposure.
        verb = "trim"
        if near_stop:
            status_label = "Near stop"
            rationale = "Price is within the near-stop threshold of the current-condition stop."
        else:
            status_label = "Heat limit reached"
            rationale = "Portfolio heat ceiling reached — no open-risk headroom remaining."
    else:
        # 4. Hold — a healthy position (or a non-directive protected state).
        verb = "hold"
        if level_status == "target_reached":
            status_label = "Target reached"
            rationale = "Take-profit target reached; no breach of the current-condition stop."
        elif level_status == "gains_protected":
            status_label = "Gains protected"
            rationale = "Trailing stop is protecting gains above cost; no breach."
        else:
            status_label = "Holding"
            rationale = "Position within plan; the current-condition stop and target are intact."

    return InstructionBlock(
        status_label=status_label,
        directive=verb if directive_enabled else None,
        rationale=rationale,
        inputs=inputs,
    )
