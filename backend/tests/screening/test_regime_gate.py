import numpy as np
import pandas as pd

from backend.src.screening.regime import market_regime, strategy_is_regime_sensitive


def _spy(closes, end="2024-01-31"):
    dates = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({"ticker": "SPY", "as_of_date": dates, "close": closes})


def test_regime_uptrend_allows_entries():
    # 260 days rising into the as-of date -> close well above 200-day SMA.
    closes = np.linspace(300, 480, 260)
    r = market_regime(spy_prices=_spy(closes))
    assert r["regime"] == "Trending up"
    assert r["allows_new_entries"] is True


def test_regime_downtrend_blocks_entries():
    # Rise then fall, ending below the 200-day SMA.
    closes = np.concatenate([np.linspace(300, 480, 180), np.linspace(480, 330, 80)])
    r = market_regime(spy_prices=_spy(closes))
    assert r["regime"] == "Trending down"
    assert r["allows_new_entries"] is False


def test_regime_fails_open_on_insufficient_history():
    r = market_regime(spy_prices=_spy(np.linspace(300, 320, 50)))  # < 200 bars
    assert r["regime"] == "Unknown"
    assert r["allows_new_entries"] is True  # never silently halt the screener


def test_regime_fails_open_on_missing_data():
    r = market_regime(spy_prices=pd.DataFrame(columns=["ticker", "as_of_date", "close"]))
    assert r["allows_new_entries"] is True


def test_strategy_regime_sensitivity_flag():
    assert strategy_is_regime_sensitive({"Trending down": "Unfavorable"}) is True
    assert strategy_is_regime_sensitive({"Trending down": "Neutral"}) is False
    assert strategy_is_regime_sensitive({}) is False
