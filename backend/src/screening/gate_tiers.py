"""Feature 012 US2 — per-strategy three-tier gate classification.

Each strategy declares, per gate, whether the gate is:

- **essential** — a non-pass excludes the candidate (always, both modes);
- **preferred** — a non-pass is retained (marked ``skipped`` + reason) and
  demoted below all clean names when ``expanded_coverage`` is enabled, otherwise
  excluded (today's hard-mode behaviour);
- **disqualifier** — a positive detection hard-excludes / forces not-entry-ready
  (always).

This module only *declares* the tier map (contracts/gate-tiers.md). It changes no
gate threshold (FR-015): the engine and strategy reuse the existing tiered-mode
``warnings``/``warning_count`` machinery and the ``warning_count``/``data_suspect``
demotion sort to surface and order the retained names.
"""

from __future__ import annotations

from typing import Literal

from ..lib import flags

GateTier = Literal["essential", "preferred", "disqualifier"]

# Canonical per-strategy declaration (data-model §3 / FR-009a). Keys are the
# user-facing gate names surfaced in StrategyGatesPanel; the engine maps the
# strategy's own ``gate_results`` labels onto these tiers via ``gate_tier`` below.
GATE_TIERS: dict[str, dict[str, GateTier]] = {
    "midterm_52w_high_momentum": {
        "liquidity": "essential",
        "data_integrity": "essential",
        "52-week-high proximity": "essential",
        "market regime": "preferred",
        "sector strength": "preferred",
        "relative strength": "preferred",
        "climax-top exhaustion": "disqualifier",
        "huge-gap breakout": "disqualifier",
    }
}

# Keyword classification for the strategy's *actual* per-candidate gate labels,
# whose wording differs from the canonical declaration above (e.g. "Trend (above
# 200-day SMA)"). Anything not matched is **preferred** (demote-not-exclude) —
# a soft gate is never silently promoted to essential.
_ESSENTIAL_KEYWORDS = (
    "proximity",
    "52-week",
    "52 week",
    "liquidity",
    "data integrity",
    "data_integrity",
)
_DISQUALIFIER_KEYWORDS = (
    "climax",
    "huge gap",
    "huge-gap",
    "gap-extended",
    "gap extended",
)


def gate_tiers(strategy_slug: str) -> dict[str, GateTier]:
    """The canonical, configurable tier map for one strategy (FR-009)."""
    base = dict(GATE_TIERS.get(strategy_slug, {}))
    overrides = flags.gate_tier_overrides()
    if overrides:
        for key in list(base):
            if key.lower() in overrides:
                base[key] = overrides[key.lower()]  # type: ignore[assignment]
    return base


def gate_tier(strategy_slug: str, gate_name: str) -> GateTier:
    """Resolve the tier for one (possibly differently-worded) gate label.

    Order: env override → canonical exact match → disqualifier keyword →
    essential keyword → preferred (the default).
    """
    norm = str(gate_name).strip().lower()

    overrides = flags.gate_tier_overrides()
    for gate, tier in overrides.items():
        if gate == norm or gate in norm:
            return tier

    canonical = {k.lower(): v for k, v in GATE_TIERS.get(strategy_slug, {}).items()}
    if norm in canonical:
        return canonical[norm]

    if any(keyword in norm for keyword in _DISQUALIFIER_KEYWORDS):
        return "disqualifier"
    if any(keyword in norm for keyword in _ESSENTIAL_KEYWORDS):
        return "essential"
    return "preferred"
