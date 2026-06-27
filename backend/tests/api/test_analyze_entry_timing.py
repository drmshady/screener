import pandas as pd

from backend.src import strategies as _strategies  # noqa: F401
from backend.src.api import analyze


def _momentum_row(ticker="MOMO") -> pd.DataFrame:
    return pd.DataFrame(
        [
            dict(
                ticker=ticker,
                name="Momentum Inc",
                sector="Tech",
                close=102.0,
                atr=2.0,
                sma_200=90.0,
                contraction_low_20=98.0,
                **{"52w_high": 104.0},
                return_12_1=0.28,
                volume_ratio_recent=1.2,
                volume_ratio_50=1.5,
                debt_to_equity=0.4,
                fcf_ttm=10.0,
                gp_to_assets=0.5,
                asset_growth=0.05,
                pivot=100.0,
                base_type="flat",
                base_length_weeks=6.0,
                base_depth=0.18,
                breakout_volume_ratio=1.5,
                dist_above_pivot=0.02,
                dist_above_sma_200=0.13,
                climax_advance=0.1,
                prior_trend_weeks=4.0,
                gap_above_pivot=0.01,
                recent_short_lived_catalyst=False,
            )
        ]
    )


def test_momentum_analyze_attaches_entry_timing(monkeypatch):
    monkeypatch.setattr(
        analyze,
        "build_single_ticker_snapshot",
        lambda symbol, as_of=None: (_momentum_row(symbol), "2024-12-31T21:00:00Z", []),
    )
    monkeypatch.setattr(analyze, "_market_universe", lambda symbol, as_of: pd.DataFrame())
    monkeypatch.setattr(analyze, "_overlay_edgar", lambda *a, **k: None)

    result = analyze.compute_candidate_result("MOMO", strategy="midterm_52w_high_momentum")

    assert result.entry_timing is not None
    assert result.entry_timing.state == "entry_ready"
    assert result.entry_timing.diagnostics.pivot == 100.0
    assert {component.name for component in result.entry_timing.components} == {
        "pivot_proximity",
        "trend",
        "volume_confirmation",
        "base_maturity",
        "base_depth",
        "not_extended",
    }
