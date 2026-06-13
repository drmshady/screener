from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.src.api.app import app
from backend.src.strategies import midterm_52w_high_momentum as midterm


def test_midterm_backtest_window_metrics_and_caveat() -> None:
    payload = json.loads(Path("backend/data/backtests/midterm_52w_high_momentum.json").read_text())
    assert payload["data_window_start"] <= "2008-01-01"
    assert payload["data_window_end"] >= "2023-01-01"
    assert any(item["year"] == 2008 for item in payload["yearly_metrics"])
    assert any(item["year"] == 2009 for item in payload["yearly_metrics"])
    assert payload["bias_check"]["survivorship_bias"]["passed"] is False

    bias_md = Path("backend/backtests/midterm_52w_high_momentum/bias_check.md")
    assert "survivorship_bias" in bias_md.read_text(encoding="utf-8")
    assert "- [ ] survivorship_bias" in bias_md.read_text(encoding="utf-8")
    assert midterm.OPERATOR_TREAT_AS_VALID is True


def test_midterm_backtest_endpoint_is_reproducible() -> None:
    client = TestClient(app)
    first = client.get("/strategies/midterm_52w_high_momentum/backtest")
    second = client.get("/strategies/midterm_52w_high_momentum/backtest")
    assert first.status_code == second.status_code == 200
    assert first.json()["summary_metrics"] == second.json()["summary_metrics"]
    assert first.json()["yearly_metrics"] == second.json()["yearly_metrics"]
    assert first.json()["window_meets_v1_floor"] is True
    assert any(
        item["item"] == "survivorship_bias" and item["passed"] is False
        for item in first.json()["bias_check"]
    )
