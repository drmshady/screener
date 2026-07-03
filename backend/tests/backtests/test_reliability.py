from __future__ import annotations

from backend.src.backtests.metrics import yearly_metric


def test_yearly_metric_marks_low_sample_from_trade_threshold(monkeypatch):
    monkeypatch.setenv("SCREENER_BACKTEST_MIN_RELIABLE_TRADES", "3")

    assert yearly_metric(2020, [0.01, -0.02])["reliability"] == "low_sample"
    assert yearly_metric(2021, [0.01, -0.02, 0.03])["reliability"] == "ok"
