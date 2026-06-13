import pandas as pd

from backend.src.strategies.shortterm_atr_breakout import rules


def _row(
    ticker: str,
    close: float,
    breakout_high: float,
    atr: float,
    sma_200: float = 90.0,
    sma_200_prev: float = 89.0,
    chandelier_exit: float = 98.0,
) -> dict:
    return {
        "ticker": ticker,
        "name": ticker,
        "sector": "Industrials",
        "close": close,
        "breakout_high_20": breakout_high,
        "atr": atr,
        "sma_200": sma_200,
        "sma_200_20d_ago": sma_200_prev,
        "chandelier_exit": chandelier_exit,
    }


def test_atr_breakout_filters_and_derives_levels():
    universe = pd.DataFrame(
        [
            _row("PASS", close=105.0, breakout_high=104.0, atr=2.0, chandelier_exit=98.0),
            _row("NOHIGH", close=103.0, breakout_high=104.0, atr=2.0, chandelier_exit=98.0),
            _row("NOTREND", close=105.0, breakout_high=104.0, atr=2.0, sma_200=110.0, chandelier_exit=98.0),
            _row("NOSLOPE", close=105.0, breakout_high=104.0, atr=2.0, sma_200=90.0, sma_200_prev=91.0, chandelier_exit=98.0),
            _row("NOATR", close=105.0, breakout_high=104.0, atr=0.0, chandelier_exit=98.0),
        ]
    )

    result = rules(universe)

    assert result["ticker"].tolist() == ["PASS"]
    row = result.iloc[0]
    assert row["entry"] == 105.0
    assert row["stop_loss"] == 102.0
    assert row["trailing_stop"] == 98.0
    assert row["take_profit"] == 112.0
    assert "ATR stop" in row["reason"]


def test_atr_breakout_returns_empty_when_required_history_features_missing():
    result = rules(pd.DataFrame([{"ticker": "MISS", "close": 100.0}]))

    assert result.empty
