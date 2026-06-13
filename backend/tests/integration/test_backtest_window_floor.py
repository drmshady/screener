from __future__ import annotations

from datetime import date

from backend.src import strategies as _strategies  # noqa: F401 - register strategies
from backend.src.strategies._registry import registry


def test_enabled_strategies_meet_15_year_and_2008_2009_backtest_floor():
    enabled = [
        strategy for strategy in registry.list_all() if strategy.enabled_by_default
    ]
    assert enabled, "At least one strategy should be enabled for v1"

    for strategy in enabled:
        summary = strategy.backtest_summary
        assert summary is not None, f"{strategy.slug} is enabled without a backtest"
        start = date.fromisoformat(str(summary.data_window_start))
        end = date.fromisoformat(str(summary.data_window_end))

        assert (end - start).days >= 365 * 15, strategy.slug
        assert start <= date(2008, 1, 1), strategy.slug
        assert end >= date(2009, 12, 31), strategy.slug
