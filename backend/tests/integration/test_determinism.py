from __future__ import annotations

from backend.src import strategies as _strategies  # noqa: F401 - register strategies
from backend.src.screening.engine import run_strategy
from backend.src.strategies._registry import registry


def _candidate_signature(result):
    return [candidate.model_dump(mode="json") for candidate in result.candidates]


def test_each_strategy_screen_is_deterministic_on_same_snapshot():
    for strategy in registry.list_all():
        first = run_strategy(
            strategy.slug,
            parameters={"regime_gate": False, "refresh_events": False},
            filters={"exclude_earnings_within_days": 0},
        )
        second = run_strategy(
            strategy.slug,
            parameters={"regime_gate": False, "refresh_events": False},
            filters={"exclude_earnings_within_days": 0},
        )

        assert second.id == first.id, strategy.slug
        assert _candidate_signature(second) == _candidate_signature(
            first
        ), strategy.slug
