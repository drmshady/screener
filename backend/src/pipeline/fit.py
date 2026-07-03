"""Pure candidate-fit synthesis for the momentum cockpit (Feature 016).

``score_fit`` maps a set of independent boolean *facts* — each already computed
by the API layer from numbers the app produces (entry timing, the real
``size_position`` result, regime favorability) — into a neutral ``fit_band`` plus
an internal 0-100 score used only for sort order. It is a **presentation /
synthesis** layer: it changes no gate, ranking, level, sizing, or backtest
output. It performs no I/O, so it is deterministic and golden-fixture testable
(constitution Principle IV).

The weights below are hardcoded, documented constants (research.md D3 — no
``fit_weight_*`` flags for a single-owner tool). They sum to 100 so the raw
score reads as a percentage internally.
"""

from __future__ import annotations

from ..models.pipeline import FitFacts, FitResult

# Fact weights (sum == 100). Ordered by how load-bearing each fact is for
# whether a momentum candidate is genuinely actionable right now.
FIT_WEIGHTS: dict[str, int] = {
    "entry_ready": 25,
    "meaningful_size_survives": 20,
    "regime_allows_entries": 15,
    "reward_to_risk_ok": 12,
    "heat_headroom_ok": 8,
    "sector_room_ok": 8,
    "not_overconcentrated": 7,
    "cash_sufficient": 5,
}

# Facts that, when false, structurally block a new entry regardless of the
# weighted score — the band collapses to "blocked" so the UI never presents a
# high score for a candidate that cannot actually be entered.
BLOCKING_FACTS: tuple[str, ...] = (
    "entry_ready",
    "meaningful_size_survives",
    "regime_allows_entries",
)

# Score thresholds for the non-blocked bands.
_STRONG_FIT_MIN = 90
_PARTIAL_FIT_MIN = 70

# Neutral, non-directive phrase for each fact when it fails (no take/pass/size
# verbs — keeps the Playwright language lint green on the default/hosted path).
_FAILED_FACT_PHRASES: dict[str, str] = {
    "entry_ready": "entry timing is not ready",
    "meaningful_size_survives": "no meaningful position size survives the caps",
    "regime_allows_entries": "market regime is unfavorable for new entries",
    "reward_to_risk_ok": "reward-to-risk is below the preferred floor",
    "heat_headroom_ok": "portfolio heat leaves little headroom",
    "sector_room_ok": "sector exposure is near its cap",
    "not_overconcentrated": "the position would be concentrated",
    "cash_sufficient": "available cash limits the position",
}

_ALL_PASS_RATIONALE = (
    "Entry-ready and a meaningful position fits within the heat, sector, "
    "concentration, and cash limits."
)

# The optional personal-use directive vocabulary, keyed by the neutral band.
_DIRECTIVE_BY_BAND: dict[str, str] = {
    "strong_fit": "consider_entry",
    "partial_fit": "size_down",
    "poor_fit": "hold_off",
    "blocked": "pass",
}


def _fact_items(facts: FitFacts) -> list[tuple[str, bool]]:
    """Facts in the documented weight order (stable, deterministic)."""
    return [(name, getattr(facts, name)) for name in FIT_WEIGHTS]


def _derive_band(score: int, facts: FitFacts) -> str:
    if any(not getattr(facts, name) for name in BLOCKING_FACTS):
        return "blocked"
    if score >= _STRONG_FIT_MIN:
        return "strong_fit"
    if score >= _PARTIAL_FIT_MIN:
        return "partial_fit"
    return "poor_fit"


def _rationale(failed_facts: list[str]) -> str:
    if not failed_facts:
        return _ALL_PASS_RATIONALE
    phrases = [_FAILED_FACT_PHRASES[name] for name in failed_facts]
    return "Fit limited: " + "; ".join(phrases) + "."


def score_fit(facts: FitFacts, *, directive: bool = False) -> FitResult:
    """Deterministically synthesize a ``FitResult`` from the boolean facts.

    ``directive`` is passed by the API layer (True only when
    ``personal_use_directive()`` is on AND the app is not hosted); it gates the
    optional ``directive_label`` and never alters the neutral band/rationale.
    """
    items = _fact_items(facts)
    score = sum(weight for name, weight in FIT_WEIGHTS.items() if getattr(facts, name))
    failed_facts = [name for name, passed in items if not passed]
    band = _derive_band(score, facts)
    directive_label = _DIRECTIVE_BY_BAND[band] if directive else None

    return FitResult(
        score=score,
        fit_band=band,  # type: ignore[arg-type]
        facts=facts,
        failed_facts=failed_facts,
        rationale=_rationale(failed_facts),
        directive_label=directive_label,  # type: ignore[arg-type]
    )
