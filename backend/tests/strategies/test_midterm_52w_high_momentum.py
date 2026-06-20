import pandas as pd
import pytest

from backend.src.strategies.midterm_52w_high_momentum import rules


@pytest.fixture(autouse=True)
def _hard_gate_mode(monkeypatch):
    # These tests assert the HARD-filter behavior (legacy mode). The default is now
    # tiered (soft gates warn+rank, Decision 7), so pin hard mode here.
    monkeypatch.setenv("SCREENER_GATE_MODE", "hard")


def _row(ticker, sector, close, high, ret, fcf, de, atr, sma_200, gp):
    return {
        "ticker": ticker,
        "name": ticker,
        "sector": sector,
        "close": close,
        "52w_high": high,
        "return_12_1": ret,
        "fcf_ttm": fcf,
        "debt_to_equity": de,
        "atr": atr,
        "sma_200": sma_200,
        "contraction_low_20": close - (2 * atr),
        "gp_to_assets": gp,
    }


def test_midterm_strategy_filters_and_ranks_frozen_universe():
    universe = pd.DataFrame(
        [
            # AAA: near high, above 200-SMA, clean quality, strong GP -> sole survivor
            _row("AAA", "Technology", 100.0, 102.0, 0.40, 10_000_000, 0.4, 2.0, 80.0, 0.50),
            # BBB: too far below 52w high -> dropped at proximity gate
            _row("BBB", "Technology", 95.0, 120.0, 0.60, 10_000_000, 0.3, 3.0, 70.0, 0.45),
            # CCC: negative FCF -> dropped at quality gate
            _row("CCC", "Health Care", 50.0, 51.0, 0.30, -1, 0.2, 1.0, 40.0, 0.40),
            # DDD: debt/equity above ceiling -> dropped at quality gate
            _row("DDD", "Health Care", 80.0, 82.0, 0.35, 5_000_000, 2.0, 1.5, 60.0, 0.30),
        ]
    )

    result = rules(universe)

    assert result["ticker"].tolist() == ["AAA"]
    row = result.iloc[0]
    assert row["entry"] == 100.0
    # The 200-day SMA trend stop is bounded to the configured ATR band.
    assert row["stop_loss"] == 92.0
    assert row["risk_distance"] == 8.0
    assert row["take_profit"] == 124.0
    assert "52-week high" in row["reason"]


def test_trend_filter_excludes_stock_below_its_200_day_sma():
    universe = pd.DataFrame(
        [
            _row("UP", "Technology", 100.0, 101.0, 0.30, 10_000_000, 0.3, 2.0, 90.0, 0.50),
            # DOWN is near its high but trades below its 200-day SMA -> excluded.
            _row("DOWN", "Technology", 100.0, 101.0, 0.30, 10_000_000, 0.3, 2.0, 110.0, 0.50),
        ]
    )

    result = rules(universe)

    assert result["ticker"].tolist() == ["UP"]


def test_gross_profitability_gate_drops_bottom_half_of_universe():
    universe = pd.DataFrame(
        [
            # Both pass proximity / trend / leverage / FCF; differ only on GP/Assets.
            _row("HIGHGP", "Technology", 100.0, 101.0, 0.30, 10_000_000, 0.3, 2.0, 80.0, 0.60),
            _row("LOWGP", "Industrials", 50.0, 50.5, 0.30, 10_000_000, 0.3, 1.0, 40.0, 0.10),
        ]
    )

    result = rules(universe)

    assert result["ticker"].tolist() == ["HIGHGP"]


def test_missing_sma_column_yields_no_levelled_candidate():
    universe = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "name": "Alpha",
                "sector": "Technology",
                "close": 100.0,
                "52w_high": 102.0,
                "return_12_1": 0.40,
                "fcf_ttm": 10_000_000,
                "debt_to_equity": 0.4,
                "atr": 2.0,
                "contraction_low_20": 96.0,
            }
        ]
    )

    result = rules(universe)

    assert result.empty
