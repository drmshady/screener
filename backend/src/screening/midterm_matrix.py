"""Mid-term side-by-side variant matrix (feature 006).

Build the liquid-universe snapshot ONCE, then evaluate the four fixed variants
over it by toggling a single A/B parameter each (research Decision 2). The two
toggles are threaded into ``universe.attrs`` by
``engine._screen_from_universe`` exactly as the single-strategy path does:

  - momentum: ``sector_strength_top_fraction`` (default 1.0 = OFF; 0<f<1 = ON)
    forwarded at engine.py via ``universe.attrs["sector_strength_top_fraction"]``
  - value:    ``min_momentum_12_1`` (default -1.0 = OFF; > -1.0 = floor ON)
    forwarded at engine.py via ``universe.attrs["min_momentum_12_1"]``

Orchestration only — no strategy rule/default/backtest change (FR-008).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


from .. import strategies as _strategies  # noqa: F401 - registers strategies
from ..agent.advisor_prompt import load_survivorship_status
from ..models.strategy import VariantResult
from ..strategies._registry import registry
from .engine import (
    _build_screen_universe,
    _resolve_screen_inputs,
    _screen_from_universe,
)
from .regime import market_regime

MOMENTUM_SLUG = "midterm_52w_high_momentum"
VALUE_SLUG = "midterm_value_composite"

# The two A/B parameters the matrix owns. Any caller-supplied value for these is
# ignored so the four-variant matrix stays well-defined (FR-001 / FR-004).
MATRIX_OWNED_PARAMS = ("sector_strength_top_fraction", "min_momentum_12_1")


@dataclass(frozen=True)
class VariantSpec:
    """One of the four fixed variants (data-model.md). The two specs sharing a
    slug differ ONLY in ``toggle_value`` (SC-003)."""

    key: str
    label: str
    slug: str
    toggle_param: str
    toggle_value: float
    toggle_on: bool


# Fixed four-variant matrix in fixed order (research Decision 1).
VARIANT_SPECS: tuple[VariantSpec, ...] = (
    VariantSpec(
        key="momentum_sector_on",
        label="Momentum — sector gate ON",
        slug=MOMENTUM_SLUG,
        toggle_param="sector_strength_top_fraction",
        toggle_value=0.5,
        toggle_on=True,
    ),
    VariantSpec(
        key="momentum_sector_off",
        label="Momentum — sector gate OFF",
        slug=MOMENTUM_SLUG,
        toggle_param="sector_strength_top_fraction",
        toggle_value=1.0,
        toggle_on=False,
    ),
    VariantSpec(
        key="value_floor_on",
        label="Value — momentum floor ON",
        slug=VALUE_SLUG,
        toggle_param="min_momentum_12_1",
        toggle_value=-0.20,
        toggle_on=True,
    ),
    VariantSpec(
        key="value_floor_off",
        label="Value — momentum floor OFF",
        slug=VALUE_SLUG,
        toggle_param="min_momentum_12_1",
        toggle_value=-1.0,
        toggle_on=False,
    ),
)


@dataclass(frozen=True)
class MidtermMatrixRun:
    """Result of one matrix run: four variants + the shared snapshot context."""

    variants: list[VariantResult]
    regime: str | None
    data_as_of: str


def _shared_regime(as_of_date: str | None) -> str | None:
    """Compute the snapshot's market regime once (shared across all variants).
    Returns None when SPY data is unavailable (e.g. injected test universes)."""
    try:
        info = market_regime(as_of_date=as_of_date)
        return info.get("regime") if info else None
    except Exception:
        return None


def run_midterm_matrix(
    as_of_date: str | None = None,
    filters: dict[str, Any] | None = None,
    shariah_overrides: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None,
) -> MidtermMatrixRun:
    """Run the four fixed mid-term variants over ONE shared universe snapshot.

    The snapshot is built once (the expensive step); each variant then toggles
    its single A/B parameter on a private copy of the shared frame and calls its
    strategy's ``rules()``. All four share one ``data_as_of`` and one universe
    (FR-002). Deterministic on a fixed snapshot (FR-007). Each variant carries
    its strategy's honest survivorship verdict (FR-015 / Decision 6).
    """
    # Strip the matrix-owned A/B params so a caller can't perturb the matrix.
    base_parameters = {
        k: v
        for k, v in (parameters or {}).items()
        if k not in MATRIX_OWNED_PARAMS
    }

    # Resolve the shared snapshot inputs (any strategy works here — the universe
    # build is strategy-independent; per-variant filters are re-resolved below so
    # each strategy's own earnings-exclusion default is honoured).
    seed_strategy = registry.get(MOMENTUM_SLUG)
    (
        shared_params,
        _seed_filters,
        shared_overrides,
        shared_shariah_only,
    ) = _resolve_screen_inputs(seed_strategy, base_parameters, filters, shariah_overrides)

    # Build the universe ONCE (research Decision 2 — shared snapshot).
    universe, data_as_of = _build_screen_universe(
        shared_params, shared_overrides, shared_shariah_only, as_of_date
    )
    regime = _shared_regime(as_of_date)

    # Per-strategy survivorship verdict (same for both of a strategy's variants).
    bias_by_slug = {
        MOMENTUM_SLUG: load_survivorship_status(slug=MOMENTUM_SLUG),
        VALUE_SLUG: load_survivorship_status(slug=VALUE_SLUG),
    }

    variants: list[VariantResult] = []
    for spec in VARIANT_SPECS:
        strategy = registry.get(spec.slug)
        variant_params = {**base_parameters, spec.toggle_param: spec.toggle_value}
        (
            v_params,
            v_filters,
            v_overrides,
            v_shariah_only,
        ) = _resolve_screen_inputs(strategy, variant_params, filters, shariah_overrides)
        # Private copy so one variant's attrs/toggle never leak into the next.
        variant_universe = universe.copy(deep=True)
        screen = _screen_from_universe(
            strategy,
            spec.slug,
            variant_universe,
            data_as_of,
            v_params,
            v_filters,
            v_overrides,
            v_shariah_only,
            as_of_date,
        )
        variants.append(
            VariantResult(
                key=spec.key,
                label=spec.label,
                strategy=strategy,
                toggle_param=spec.toggle_param,
                toggle_value=spec.toggle_value,
                toggle_on=spec.toggle_on,
                screen=screen,
                bias_check=bias_by_slug[spec.slug],
            )
        )

    return MidtermMatrixRun(variants=variants, regime=regime, data_as_of=data_as_of)
