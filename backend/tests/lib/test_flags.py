from __future__ import annotations

from backend.src.lib import flags


def test_feature_015_flag_defaults_preserve_current_surfaces(monkeypatch):
    for name in (
        "SCREENER_BACKTEST_REBALANCE",
        "SCREENER_BACKTEST_COST_BPS",
        "SCREENER_BACKTEST_MIN_RELIABLE_TRADES",
        "SCREENER_SIZING_FALLBACK_ATR_MULT",
        "SCREENER_PORTFOLIO_HEAT_CEILING",
        "SCREENER_REGIME_RISK_BUDGET",
        "SCREENER_REGIME_RISK_BUDGET_UNFAVORABLE",
    ):
        monkeypatch.delenv(name, raising=False)

    assert flags.backtest_rebalance() == "Q"
    assert flags.backtest_cost_bps() == 10.0
    assert flags.backtest_min_reliable_trades() == 10
    assert flags.sizing_fallback_atr_mult() > 0
    assert flags.portfolio_heat_ceiling() >= 1.0
    assert flags.regime_risk_budget_enabled() is False
    assert flags.regime_risk_budget_unfavorable() == 0.5


def test_feature_015_flags_parse_types_and_truthy(monkeypatch):
    monkeypatch.setenv("SCREENER_BACKTEST_REBALANCE", "m")
    monkeypatch.setenv("SCREENER_BACKTEST_COST_BPS", "7.5")
    monkeypatch.setenv("SCREENER_BACKTEST_MIN_RELIABLE_TRADES", "4")
    monkeypatch.setenv("SCREENER_SIZING_FALLBACK_ATR_MULT", "8.25")
    monkeypatch.setenv("SCREENER_PORTFOLIO_HEAT_CEILING", "0.06")
    monkeypatch.setenv("SCREENER_REGIME_RISK_BUDGET", "yes")
    monkeypatch.setenv("SCREENER_REGIME_RISK_BUDGET_UNFAVORABLE", "0.35")

    assert flags.backtest_rebalance() == "M"
    assert flags.backtest_cost_bps() == 7.5
    assert flags.backtest_min_reliable_trades() == 4
    assert flags.sizing_fallback_atr_mult() == 8.25
    assert flags.portfolio_heat_ceiling() == 0.06
    assert flags.regime_risk_budget_enabled() is True
    assert flags.regime_risk_budget_unfavorable() == 0.35


def test_backtest_rebalance_falls_back_to_quarterly(monkeypatch):
    monkeypatch.setenv("SCREENER_BACKTEST_REBALANCE", "weekly")

    assert flags.backtest_rebalance() == "Q"
