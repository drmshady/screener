from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException

from ..lib.disclaimer import DISCLAIMER_TEXT

router = APIRouter(prefix="/strategies", tags=["backtest"])


def _artifact_path(slug: str) -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "backtests" / f"{slug}.json"


def _equity_curve_path(slug: str) -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "backtests"
        / slug
        / "equity_curve.parquet"
    )


@router.get("/{slug}/backtest")
def get_backtest(slug: str) -> dict[str, Any]:
    path = _artifact_path(slug)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Backtest not found")

    payload = json.loads(path.read_text(encoding="utf-8"))
    bias_check = payload.get("bias_check", {})
    if isinstance(bias_check, dict):
        payload["bias_check"] = [
            {
                "item": item,
                "passed": details.get("passed", False),
                "note": details.get("note", ""),
            }
            for item, details in bias_check.items()
        ]

    payload["window_meets_v1_floor"] = (
        payload.get("data_window_start", "") <= "2008-01-01"
        and payload.get("data_window_end", "") >= "2023-01-01"
    )
    payload["limited_window_warning"] = (
        None if payload["window_meets_v1_floor"] else "Limited backtest window"
    )
    payload["data_as_of"] = payload.get("computed_at") or payload.get(
        "data_sources", [{}]
    )[0].get("source_as_of")
    payload["disclaimer"] = DISCLAIMER_TEXT
    return payload


@router.get("/{slug}/backtest/equity-curve")
def get_backtest_equity_curve(slug: str) -> dict[str, Any]:
    backtest = get_backtest(slug)
    path = _equity_curve_path(slug)
    if not path.exists():
        return {
            "strategy_slug": slug,
            "points": [],
            "data_window_start": backtest.get("data_window_start"),
            "data_window_end": backtest.get("data_window_end"),
            "data_sources": backtest.get("data_sources", []),
            "data_as_of": backtest.get("data_as_of"),
            "disclaimer": DISCLAIMER_TEXT,
        }

    curve = pd.read_parquet(path)
    required = {"step", "equity"}
    if not required.issubset(curve.columns):
        raise HTTPException(status_code=500, detail="Equity curve artifact is invalid")

    curve = curve.sort_values("step")
    return {
        "strategy_slug": slug,
        "points": [
            {"step": int(row.step), "equity": float(row.equity)}
            for row in curve.itertuples(index=False)
            if pd.notna(row.step) and pd.notna(row.equity)
        ],
        "data_window_start": backtest.get("data_window_start"),
        "data_window_end": backtest.get("data_window_end"),
        "data_sources": backtest.get("data_sources", []),
        "data_as_of": backtest.get("data_as_of"),
        "disclaimer": DISCLAIMER_TEXT,
    }
