"""The value strategy declares every required field and registers (FR-002)."""
from backend.src import strategies as _strategies  # noqa: F401 - triggers registration
from backend.src.strategies._registry import registry


def test_strategy_is_registered_with_full_declaration():
    s = registry.get("midterm_value_composite")
    assert s is not None
    assert s.name and s.citation and s.timeframe == "Mid-term"
    assert s.holding_period_days.get("min") and s.holding_period_days.get("max")
    assert set(s.regime_favorability) >= {"Trending up", "Range-bound", "Trending down"}
    assert s.parameters  # documented tunables
    assert s.modifications and all(m.citation for m in s.modifications)


def test_core_citation_names_value_foundations():
    s = registry.get("midterm_value_composite")
    cite = s.citation.lower()
    assert "fama" in cite or "lakonishok" in cite


def test_enabled_by_default_via_operator_override():
    # The single operator has opted this strategy in (SCREENER_VALUE_TREAT_AS_VALID
    # defaults on), mirroring the momentum strategy. Strict gating is opt-out
    # (set the flag to 0). Either way the enable flag is a boolean.
    import os

    from backend.src.strategies import midterm_value_composite as mod

    s = registry.get("midterm_value_composite")
    assert isinstance(s.enabled_by_default, bool)
    if os.getenv("SCREENER_VALUE_TREAT_AS_VALID", "1") != "0":
        assert s.enabled_by_default is True


def test_survivorship_caveat_remains_honest_even_when_enabled():
    # Enabling the strategy must NOT alter the backtest's honest bias check: the
    # committed artifact still reports survivorship as failing (Stooq has no
    # delisted names), so the optimism caveat stays visible.
    from backend.src.strategies import midterm_value_composite as mod

    assert mod._backtest_bias_passes() is False
