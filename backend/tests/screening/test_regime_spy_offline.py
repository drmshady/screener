"""Offline SPY regime fallback (daily-baked parquet).

The hosted image excludes the raw Stooq archive and SPY is not in the screening
parquet, so without a baked SPY series the regime master switch falls to Unknown
whenever request-time yfinance is unreachable. These tests cover the daily bake
(`refresh_spy_history`) and the `_load_spy` fallback that reads it.
"""
from __future__ import annotations

import pandas as pd

from backend.src.screening import regime


class _FakeProvider:
    """Stand-in for YFinancePriceProvider with an injectable SPY frame."""

    def __init__(self, frame: pd.DataFrame | None) -> None:
        self._frame = frame

    def fetch_ohlcv(self, tickers, *, start_date=None, end_date=None):  # noqa: ANN001
        return self._frame if self._frame is not None else pd.DataFrame()


def _spy_frame(closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="B")
    return pd.DataFrame(
        {
            "ticker": "SPY",
            "as_of_date": dates,
            "close": closes,
        }
    )


def test_refresh_spy_history_writes_readable_parquet(tmp_path) -> None:
    target = tmp_path / "spy_history.parquet"
    rows = regime.refresh_spy_history(
        provider=_FakeProvider(_spy_frame([100.0, 101.0, 102.0])), path=target
    )
    assert rows == 3
    assert target.exists()

    loaded = regime._spy_from_baked(target)
    assert loaded is not None
    assert list(loaded.columns) == ["as_of_date", "close", "ticker"]
    assert len(loaded) == 3


def test_refresh_spy_history_does_not_clobber_on_empty_fetch(tmp_path) -> None:
    target = tmp_path / "spy_history.parquet"
    regime.refresh_spy_history(provider=_FakeProvider(_spy_frame([100.0, 101.0])), path=target)
    assert target.exists()

    # An empty fetch must leave the prior good file intact and report 0 rows.
    rows = regime.refresh_spy_history(provider=_FakeProvider(None), path=target)
    assert rows == 0
    loaded = regime._spy_from_baked(target)
    assert loaded is not None and len(loaded) == 2


def test_regime_computes_from_baked_parquet_when_yfinance_unavailable(
    tmp_path, monkeypatch
) -> None:
    # Baked series: a clean uptrend so the last close sits above its 200-day SMA.
    target = tmp_path / "spy_history.parquet"
    closes = [100.0 + i for i in range(260)]
    regime.refresh_spy_history(provider=_FakeProvider(_spy_frame(closes)), path=target)

    # yfinance is unreachable; the baked parquet is the only offline source.
    monkeypatch.setattr(regime, "YFinancePriceProvider", lambda: _FakeProvider(None))
    monkeypatch.setattr(regime, "_SPY_HISTORY_PARQUET", target)
    monkeypatch.setattr(regime, "_spy_from_stooq", lambda: None)

    result = regime.market_regime()
    assert result["regime"] == "Trending up"
    assert result["allows_new_entries"] is True
    assert result["spy_sma_200"] is not None
    assert "baked(daily)" in result["note"]
