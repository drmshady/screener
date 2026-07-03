"""Feature 016 reversibility invariant (SC-009, D10 / T039).

The momentum-only product surface (feature 016) removes the value and short-term
entry points from the *frontend* only. Their strategy code, registry entries, and
declarations must stay intact and green so the removal is a pure UI reversal — no
strategy rule, citation, indicator, or backtest baseline change. This test locks
that invariant at the registry seam: every strategy still registers with its full
declaration even though the UI no longer links to value / short-term.
"""
from __future__ import annotations

from backend.src import strategies as _strategies  # noqa: F401 - triggers registration
from backend.src.strategies._registry import registry

_MOMENTUM = "midterm_52w_high_momentum"
_VALUE = "midterm_value_composite"
_SHORTTERM = ("shortterm_atr_breakout", "shortterm_minervini_vcp")


def test_value_and_shortterm_still_registered_despite_ui_removal() -> None:
    slugs = {s.slug for s in registry.list_all()}
    # Momentum (primary) plus the surfaces removed from the UI must all remain
    # loadable from the backend registry.
    assert {_MOMENTUM, _VALUE, *_SHORTTERM} <= slugs


def test_removed_ui_strategies_keep_full_declaration() -> None:
    for slug in (_VALUE, *_SHORTTERM):
        s = registry.get(slug)
        assert s is not None, f"{slug} must still register"
        # Same completeness the loader enforces (NAME/CITATION/TIMEFRAME/rules/etc.).
        assert s.name and s.citation and s.timeframe
        assert callable(s.rules)
        assert s.parameters
        assert set(s.regime_favorability) >= {
            "Trending up",
            "Range-bound",
            "Trending down",
        }
        assert s.modifications and all(m.citation for m in s.modifications)


def test_momentum_remains_the_primary_registered_strategy() -> None:
    s = registry.get(_MOMENTUM)
    assert s is not None
    assert s.timeframe == "Mid-term"
    assert callable(s.rules)
