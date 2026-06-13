import pandas as pd

from backend.src.strategies.shortterm_minervini_vcp import rules


def _row(
    ticker: str,
    close: float,
    pivot: float,
    contraction_low: float,
    adr_ratio: float,
    volume_ratio: float,
    sma_50: float = 90.0,
    sma_150: float = 80.0,
    sma_200: float = 70.0,
    sma_200_prev: float = 69.0,
) -> dict:
    return {
        "ticker": ticker,
        "name": ticker,
        "sector": "Technology",
        "close": close,
        "breakout_high_50": pivot,
        "contraction_low_20": contraction_low,
        "adr_ratio_20_20": adr_ratio,
        "volume_ratio_50": volume_ratio,
        "sma_50": sma_50,
        "sma_150": sma_150,
        "sma_200": sma_200,
        "sma_200_20d_ago": sma_200_prev,
    }


def test_minervini_vcp_filters_and_derives_levels():
    universe = pd.DataFrame(
        [
            _row("PASS", close=101.0, pivot=100.0, contraction_low=96.0, adr_ratio=0.55, volume_ratio=1.8),
            _row("WIDE", close=101.0, pivot=100.0, contraction_low=80.0, adr_ratio=0.55, volume_ratio=1.8),
            _row("NOADR", close=101.0, pivot=100.0, contraction_low=96.0, adr_ratio=0.90, volume_ratio=1.8),
            _row("NOVOL", close=101.0, pivot=100.0, contraction_low=96.0, adr_ratio=0.55, volume_ratio=1.0),
            _row("NOPIVOT", close=99.0, pivot=100.0, contraction_low=96.0, adr_ratio=0.55, volume_ratio=1.8),
            _row("NOTREND", close=101.0, pivot=100.0, contraction_low=96.0, adr_ratio=0.55, volume_ratio=1.8, sma_200_prev=71.0),
        ]
    )

    result = rules(universe)

    assert result["ticker"].tolist() == ["PASS"]
    row = result.iloc[0]
    assert row["entry"] == 100.0
    assert row["stop_loss"] == 96.0
    assert row["take_profit"] == 110.0
    assert "ADR contraction" in row["reason"]


def test_minervini_vcp_returns_empty_when_required_history_features_missing():
    result = rules(pd.DataFrame([{"ticker": "MISS", "close": 100.0}]))

    assert result.empty
