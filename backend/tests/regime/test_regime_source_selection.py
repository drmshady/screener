from __future__ import annotations

import numpy as np
import pandas as pd

from backend.src.regime.calculator import current_regime_response
from backend.src.screening import regime


class _FakeProvider:
    def __init__(self, frame: pd.DataFrame | None) -> None:
        self._frame = frame

    def fetch_ohlcv(self, tickers, *, start_date=None, end_date=None):  # noqa: ANN001
        return self._frame if self._frame is not None else pd.DataFrame()


def _spy_frame(closes: list[float] | np.ndarray, end: str = "2026-01-31") -> pd.DataFrame:
    dates = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({"ticker": "SPY", "as_of_date": dates, "close": closes})


def test_load_spy_prefers_source_with_enough_sma_history(tmp_path, monkeypatch) -> None:
    target = tmp_path / "spy_history.parquet"
    short_live = _spy_frame([510.0, 511.0, 512.0])
    baked_full = _spy_frame(np.linspace(300.0, 560.0, 260))
    baked_full.to_parquet(target, index=False)

    monkeypatch.setattr(regime, "YFinancePriceProvider", lambda: _FakeProvider(short_live))
    monkeypatch.setattr(regime, "_SPY_HISTORY_PARQUET", target)
    monkeypatch.setattr(regime, "_spy_from_stooq", lambda: None)

    loaded, source = regime._load_spy("2026-01-31", 200)

    assert source == "baked(daily)"
    assert loaded is not None
    assert len(loaded.dropna(subset=["close"])) >= 200


def test_regime_response_is_deterministic_and_explains_true_insufficient_history() -> None:
    spy = _spy_frame([500.0, 501.0, 502.0])

    first = current_regime_response(
        as_of_date="2026-01-31",
        spy_prices=spy,
        breadth_prices=pd.DataFrame(columns=["ticker", "as_of_date", "close"]),
        constituents=[],
    ).model_dump(mode="json", exclude={"data_as_of"})
    second = current_regime_response(
        as_of_date="2026-01-31",
        spy_prices=spy,
        breadth_prices=pd.DataFrame(columns=["ticker", "as_of_date", "close"]),
        constituents=[],
    ).model_dump(mode="json", exclude={"data_as_of"})

    assert second == first
    assert first["inputs"]["spy_close"] == "502.0"
    assert first["inputs"]["spy_sma200"] is None
    assert first["inputs"]["spy_above_sma200"] is None
    assert first["inputs"]["price_source_name"] == "injected"
    assert first["inputs"]["unavailable_reason"]
    assert "insufficient spy history" in first["inputs"]["unavailable_reason"].lower()
    assert "gate fails open" in first["inputs"]["unavailable_reason"].lower()
