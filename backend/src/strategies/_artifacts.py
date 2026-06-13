from __future__ import annotations

import json
from pathlib import Path

from ..models.strategy import BacktestSummary


def artifact_path(slug: str) -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "backtests" / f"{slug}.json"


def load_backtest_summary(slug: str) -> BacktestSummary | None:
    path = artifact_path(slug)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary_metrics", {})
    source = (payload.get("data_sources") or [{}])[0]
    return BacktestSummary(
        data_window_start=payload["data_window_start"],
        data_window_end=payload["data_window_end"],
        total_return=float(summary.get("total_return", 0)),
        max_drawdown=float(summary.get("max_drawdown", 0)),
        hit_rate=float(summary.get("hit_rate", 0)),
        avg_win=float(summary.get("avg_win", 0)),
        avg_loss=float(summary.get("avg_loss", 0)),
        turnover=float(summary.get("turnover", 0)),
        source_name=str(source.get("source_name", "unknown")),
        source_as_of=str(source.get("source_as_of", payload.get("computed_at", ""))),
    )


def backtest_bias_passes(slug: str) -> bool:
    path = artifact_path(slug)
    if not path.exists():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    bias_check = payload.get("bias_check", {})
    return bool(bias_check) and all(item.get("passed") is True for item in bias_check.values())
