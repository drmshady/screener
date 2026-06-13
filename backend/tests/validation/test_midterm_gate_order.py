from __future__ import annotations

import pytest

from backend.src.models.strategy import Strategy
from backend.src.strategies import midterm_52w_high_momentum as midterm
from backend.src.strategies._registry import StrategyRegistry

from .conftest import GATE_ORDER, hard_gate_funnel


def test_midterm_declaration_complete() -> None:
    assert midterm.NAME == "Mid-Term 52-Week High Momentum"
    assert "George & Hwang (2004)" in midterm.CITATION
    assert midterm.TIMEFRAME == "Mid-term"
    for key, expected_default in {
        "lookback_days": 252,
        "proximity_pct": 0.05,
        "max_debt_equity": 1.5,
        "target_volatility": 0.12,
        "trend_sma_length": 200,
        "min_gp_assets_percentile": 0.5,
    }.items():
        assert key in midterm.PARAMETERS
        assert midterm.PARAMETERS[key].default == expected_default
    assert midterm.REGIME_FAVORABILITY
    assert callable(midterm.rules)
    assert midterm.MODIFICATIONS
    assert all(mod.citation for mod in midterm.MODIFICATIONS)


def test_registry_rejects_incomplete_strategy() -> None:
    registry = StrategyRegistry()
    incomplete = Strategy(
        slug="incomplete",
        name="Incomplete",
        timeframe="Test",
        citation="",
        description="Missing citation should be rejected",
        holding_period_days={"min": 1, "max": 2},
        parameters={},
        regime_favorability={},
        default_exclude_earnings_within_days=0,
        enabled_by_default=False,
        modifications=[],
        rules=lambda df: df,
        backtest_summary=None,
    )
    with pytest.raises(ValueError, match="missing citation"):
        registry.register(incomplete)


def test_declared_hard_gate_funnel_and_sector_disabled(frozen_snapshot) -> None:
    funnel = hard_gate_funnel(frozen_snapshot)
    assert [stage["gate"] for stage in funnel] == GATE_ORDER
    assert funnel[0]["survivors"] == len(frozen_snapshot.us)
    assert all(stage["survivors"] >= 0 for stage in funnel)
    assert midterm.PARAMETERS["sector_strength_top_fraction"].default == 1.0
    assert frozen_snapshot.strong_sectors is None
