from __future__ import annotations

import pandas as pd


def _trade_stats(returns: list[float]) -> dict[str, float]:
    """Per-trade hit rate and average win/loss (order-independent)."""
    series = pd.Series(returns, dtype=float)
    wins = series[series > 0]
    losses = series[series < 0]
    return {
        "hit_rate": float((series > 0).mean()) if len(series) else 0.0,
        "avg_win": float(wins.mean()) if not wins.empty else 0.0,
        "avg_loss": float(abs(losses.mean())) if not losses.empty else 0.0,
    }


def yearly_metric(year: int, returns: list[float]) -> dict:
    """Metrics for one rebalance year.

    `total_return` is the EQUAL-WEIGHT MEAN of that year's trades — the return of
    holding the TOP_N candidates as one equal-weight basket — NOT the product of
    the individual trades (positions are held in parallel, not sequentially).
    `max_drawdown` is the worst single-name loss that year (a per-rebalance risk
    proxy; true path drawdown is computed on the compounded yearly curve).
    """
    if not returns:
        return {
            "year": year,
            "trades": 0,
            "hit_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
        }
    series = pd.Series(returns, dtype=float)
    stats = _trade_stats(returns)
    worst = series.min()
    return {
        "year": year,
        "trades": len(returns),
        "hit_rate": stats["hit_rate"],
        "avg_win": stats["avg_win"],
        "avg_loss": stats["avg_loss"],
        "total_return": float(series.mean()),  # equal-weight basket return
        "max_drawdown": float(abs(worst)) if worst < 0 else 0.0,
    }


def summarize_portfolio(
    yearly_returns: list[float], all_trade_returns: list[float]
) -> dict[str, float]:
    """Summary over the whole window.

    The equity curve compounds the per-year equal-weight basket returns
    (`yearly_returns`), so it reflects a real rebalanced portfolio rather than
    sequentially reinvesting every individual trade. Hit rate and average
    win/loss are computed across all individual trades.
    """
    if not all_trade_returns:
        return {
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "hit_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "turnover": 0.0,
        }
    yearly = pd.Series(yearly_returns, dtype=float)
    equity = (1 + yearly).cumprod()
    drawdown = (equity / equity.cummax()) - 1 if len(yearly) else pd.Series([0.0])
    stats = _trade_stats(all_trade_returns)
    return {
        "total_return": float(equity.iloc[-1] - 1) if len(yearly) else 0.0,
        "max_drawdown": float(abs(drawdown.min())) if len(yearly) else 0.0,
        "hit_rate": stats["hit_rate"],
        "avg_win": stats["avg_win"],
        "avg_loss": stats["avg_loss"],
        "turnover": float(len(all_trade_returns)),
    }


def summarize_returns(returns: list[float]) -> dict[str, float]:
    """DEPRECATED sequential-compounding summary (kept for callers/tests that pass
    a single basket's trades). Compounds the list as given; for portfolio-level
    metrics use `summarize_portfolio`, which compounds per-year basket means.
    """
    if not returns:
        return {
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "hit_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "turnover": 0.0,
        }
    series = pd.Series(returns, dtype=float)
    equity = (1 + series).cumprod()
    drawdown = (equity / equity.cummax()) - 1
    stats = _trade_stats(returns)
    return {
        "total_return": float(equity.iloc[-1] - 1),
        "max_drawdown": float(abs(drawdown.min())),
        "hit_rate": stats["hit_rate"],
        "avg_win": stats["avg_win"],
        "avg_loss": stats["avg_loss"],
        "turnover": float(len(series)),
    }
