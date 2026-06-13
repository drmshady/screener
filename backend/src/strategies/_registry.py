from __future__ import annotations

from datetime import date

from ..models.strategy import Strategy


def _window_meets_floor(strategy: Strategy) -> bool:
    summary = strategy.backtest_summary
    if summary is None:
        return False
    start = date.fromisoformat(str(summary.data_window_start))
    end = date.fromisoformat(str(summary.data_window_end))
    spans_fifteen_years = (end - start).days >= 365 * 15
    spans_crisis = start <= date(2008, 1, 1) and end >= date(2009, 12, 31)
    return spans_fifteen_years and spans_crisis


class StrategyRegistry:
    def __init__(self):
        self._strategies: dict[str, Strategy] = {}

    def register(self, strategy: Strategy):
        if not strategy.citation:
            raise ValueError(f"Strategy {strategy.slug} missing citation")
        if not strategy.rules:
            raise ValueError(f"Strategy {strategy.slug} missing rules")
        if strategy.enabled_by_default and not _window_meets_floor(strategy):
            strategy.enabled_by_default = False
        self._strategies[strategy.slug] = strategy

    def get(self, slug: str) -> Strategy | None:
        return self._strategies.get(slug)

    def list_all(self) -> list[Strategy]:
        return list(self._strategies.values())


registry = StrategyRegistry()
