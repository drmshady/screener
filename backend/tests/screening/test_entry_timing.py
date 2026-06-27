import pandas as pd

from backend.src.screening.entry_timing import EntryThresholds, classify_entry_timing
from backend.src.models.strategy import Strategy
from backend.src.screening.engine import _screen_from_universe


def _ready_row(**overrides):
    row = {
        "close": 102.0,
        "sma_200": 90.0,
        "pivot": 100.0,
        "base_type": "flat",
        "base_length_weeks": 6.0,
        "base_depth": 0.18,
        "breakout_volume_ratio": 1.5,
        "dist_above_pivot": 0.02,
        "dist_above_sma_200": 0.1333333333,
        "climax_advance": 0.10,
        "prior_trend_weeks": 10.0,
        "gap_above_pivot": 0.0,
        "recent_short_lived_catalyst": False,
    }
    row.update(overrides)
    return row


def _component(classification, name):
    return next(c for c in classification.components if c.name == name)


def test_entry_ready_requires_all_components_and_no_forcing_disqualifier():
    result = classify_entry_timing(_ready_row(), thresholds=EntryThresholds())

    assert result.state == "entry_ready"
    assert [c.status for c in result.components] == ["pass"] * 6
    assert result.diagnostics.pivot == 100.0
    assert "buy" not in result.summary.lower()
    assert "sell" not in result.summary.lower()


def test_extended_above_pivot_is_not_entry_ready():
    result = classify_entry_timing(
        _ready_row(close=107.0, dist_above_pivot=0.07),
        thresholds=EntryThresholds(),
    )

    assert result.state == "not_entry_ready"
    assert _component(result, "pivot_proximity").status == "fail"
    assert "extended" in _component(result, "pivot_proximity").reason


def test_missing_base_yields_entry_undetermined_not_ready():
    result = classify_entry_timing(
        _ready_row(pivot=None, base_type="none", base_length_weeks=None, base_depth=None),
        thresholds=EntryThresholds(),
    )

    assert result.state == "entry_undetermined"
    assert _component(result, "pivot_proximity").status == "undetermined"
    assert _component(result, "base_maturity").status == "undetermined"
    assert _component(result, "base_depth").status == "undetermined"


def test_component_failures_cover_volume_maturity_depth_and_sma_extension():
    result = classify_entry_timing(
        _ready_row(
            breakout_volume_ratio=1.1,
            base_length_weeks=3.0,
            base_depth=0.40,
            close=150.0,
            dist_above_sma_200=0.6667,
        ),
        thresholds=EntryThresholds(),
    )

    assert result.state == "not_entry_ready"
    assert _component(result, "volume_confirmation").status == "fail"
    assert _component(result, "base_maturity").status == "fail"
    assert _component(result, "base_depth").status == "fail"
    assert _component(result, "not_extended").status == "fail"


def test_climax_and_gap_disqualifiers_force_not_entry_ready():
    result = classify_entry_timing(
        _ready_row(climax_advance=0.32, prior_trend_weeks=12.0, gap_above_pivot=0.08),
        thresholds=EntryThresholds(),
    )

    assert result.state == "not_entry_ready"
    forcing = [d.name for d in result.disqualifiers if d.forces_not_entry_ready and d.triggered]
    assert forcing == ["climax_top", "huge_gap"]


def test_short_lived_catalyst_is_warning_only_and_deterministic():
    row = _ready_row(recent_short_lived_catalyst=True)

    first = classify_entry_timing(row, thresholds=EntryThresholds())
    second = classify_entry_timing(row, thresholds=EntryThresholds())

    assert first == second
    assert first.state == "entry_ready"
    catalyst = next(d for d in first.disqualifiers if d.name == "short_lived_catalyst")
    assert catalyst.triggered is True
    assert catalyst.forces_not_entry_ready is False


def _screen_row(ticker: str, **overrides):
    row = {
        "ticker": ticker,
        "name": f"{ticker} Corp",
        "sector": "Technology",
        "close": 102.0,
        "entry": 102.0,
        "stop_loss": 94.0,
        "take_profit": 120.0,
        "score": 1.0,
        "reason": "within 5% of 52-week high",
        "gate_results": [],
        "warnings": [],
        "data_integrity_warnings": [],
        "data_suspect": False,
        "pivot": 100.0,
        "base_type": "flat",
        "base_length_weeks": 6.0,
        "base_depth": 0.18,
        "breakout_volume_ratio": 1.5,
        "dist_above_pivot": 0.02,
        "dist_above_sma_200": 0.13,
        "sma_200": 90.0,
        "climax_advance": 0.1,
        "prior_trend_weeks": 10.0,
        "gap_above_pivot": 0.0,
    }
    row.update(overrides)
    return row


def _strategy(slug: str, rows: list[dict]) -> Strategy:
    return Strategy(
        slug=slug,
        name="Stub Strategy",
        timeframe="Mid-term",
        citation="Test",
        description="Test strategy",
        holding_period_days={"min": 1, "max": 2},
        parameters={},
        regime_favorability={},
        default_exclude_earnings_within_days=0,
        enabled_by_default=True,
        modifications=[],
        rules=lambda universe: pd.DataFrame(rows),
    )


def test_screen_from_universe_attaches_entry_timing_and_filters_ready_only():
    rows = [
        _screen_row("READY"),
        _screen_row("EXTD", close=107.0, dist_above_pivot=0.07),
    ]
    strategy = _strategy("midterm_52w_high_momentum", rows)

    annotated = _screen_from_universe(
        strategy,
        strategy.slug,
        pd.DataFrame(rows),
        "2026-06-26T00:00:00Z",
        {},
        {},
        {},
        False,
        None,
    )
    filtered = _screen_from_universe(
        strategy,
        strategy.slug,
        pd.DataFrame(rows),
        "2026-06-26T00:00:00Z",
        {"entry_ready_only": True},
        {},
        {},
        False,
        None,
    )

    states = {c.ticker: c.entry_timing.state for c in annotated.candidates}
    assert states == {"READY": "entry_ready", "EXTD": "not_entry_ready"}
    assert [c.ticker for c in filtered.candidates] == ["READY"]


def test_default_off_parameters_preserve_momentum_candidate_identity():
    rows = [
        _screen_row("READY"),
        _screen_row("EXTD", close=107.0, dist_above_pivot=0.07),
    ]
    strategy = _strategy("midterm_52w_high_momentum", rows)

    implicit_defaults = _screen_from_universe(
        strategy,
        strategy.slug,
        pd.DataFrame(rows),
        "2026-06-26T00:00:00Z",
        {},
        {},
        {},
        False,
        None,
    )
    explicit_off = _screen_from_universe(
        strategy,
        strategy.slug,
        pd.DataFrame(rows),
        "2026-06-26T00:00:00Z",
        {"entry_ready_only": False, "expanded_coverage": False},
        {},
        {},
        False,
        None,
    )

    assert [c.ticker for c in implicit_defaults.candidates] == [
        c.ticker for c in explicit_off.candidates
    ]
    assert [
        c.model_dump(mode="json") for c in implicit_defaults.candidates
    ] == [
        c.model_dump(mode="json") for c in explicit_off.candidates
    ]


def test_screen_from_universe_leaves_non_momentum_entry_timing_empty():
    rows = [_screen_row("VALUE")]
    strategy = _strategy("midterm_value_composite", rows)

    result = _screen_from_universe(
        strategy,
        strategy.slug,
        pd.DataFrame(rows),
        "2026-06-26T00:00:00Z",
        {},
        {},
        {},
        False,
        None,
    )

    assert result.candidates[0].entry_timing is None
