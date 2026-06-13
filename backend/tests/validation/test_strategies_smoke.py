from __future__ import annotations

from backend.src.screening.engine import run_strategy
from backend.src.strategies._registry import registry


def test_shortterm_strategies_load_declare_and_run() -> None:
    for slug in ["shortterm_minervini_vcp", "shortterm_atr_breakout"]:
        strategy = registry.get(slug)
        assert strategy is not None
        assert strategy.name
        assert strategy.citation
        assert strategy.timeframe == "Short-term"
        assert strategy.parameters
        assert strategy.regime_favorability
        assert strategy.modifications
        assert callable(strategy.rules)

        result = run_strategy(
            slug,
            parameters={"regime_gate": False, "refresh_events": False},
            filters={"exclude_earnings_within_days": 0},
        )
        assert result.data_as_of
        assert result.disclaimer
        assert result.candidate_count >= 0
