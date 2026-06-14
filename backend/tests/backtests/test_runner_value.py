"""Value-strategy branch of the backtest runner (research D9).

Offline: injects a synthetic price frame and stubs the SEC fundamentals fetch so
the value candidate-pool + _build_snapshot value path execute without network. The
real artifact (with point-in-time EDGAR fundamentals) is produced by T030.
"""
from datetime import date

import pandas as pd

from backend.src import strategies as _strategies  # noqa: F401
from backend.src.backtests import runner


def _synthetic_prices() -> pd.DataFrame:
    days = pd.bdate_range("2017-06-01", "2021-06-30")
    frames = []
    for i, ticker in enumerate(["AAA", "BBB", "CCC"]):
        base = 20.0 + i * 5
        close = base + pd.Series(range(len(days)), dtype=float) * 0.01
        frames.append(pd.DataFrame({
            "ticker": ticker,
            "as_of_date": days,
            "open": close.values,
            "high": (close * 1.01).values,
            "low": (close * 0.99).values,
            "close": close.values,
            "volume": 1_000_000.0,
        }))
    return pd.concat(frames, ignore_index=True)


def test_value_candidate_pool_is_liquid_universe():
    prices = runner.precompute_features(_synthetic_prices())
    pool = runner._candidate_pool(prices, date(2020, 1, 31), "midterm_value_composite")
    # No price pre-filter -> all liquid, seasoned names are eligible.
    assert set(pool["ticker"]) == {"AAA", "BBB", "CCC"}


def test_run_backtest_value_branch_well_formed(monkeypatch):
    # Stub the SEC fetch (empty facts -> value metrics resolve to None, no trades,
    # but the value branch + artifact assembly must run cleanly).
    monkeypatch.setattr(
        runner, "prefetch_fundamentals",
        lambda tickers, **k: ({t: {"facts": {"us-gaap": {}}} for t in tickers},
                              {t: "Tech" for t in tickers}),
    )
    monkeypatch.setattr(runner, "load_cached_profiles", lambda tickers: ({}, None))

    result = runner.run_backtest(
        "midterm_value_composite", date(2019, 1, 1), date(2021, 12, 31),
        prices=_synthetic_prices(),
    )
    assert result["strategy_slug"] == "midterm_value_composite"
    # Honest survivorship: the injected (Stooq-like) frame has no delisted names.
    assert result["bias_check"]["survivorship_bias"]["passed"] is False
    # One walk-forward row per annual as-of date in the window.
    assert len(result["yearly_metrics"]) == 3
    # The value strategy consumes fundamentals (sec_edgar source recorded).
    assert any(s["source_name"] == "sec_edgar_companyfacts" for s in result["data_sources"])
