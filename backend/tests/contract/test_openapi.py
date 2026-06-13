from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import schemathesis
from backend.src.api.app import app
from fastapi.testclient import TestClient

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-screener-mvp"
    / "contracts"
    / "openapi.yaml"
)

SCHEMA = schemathesis.openapi.from_path(str(CONTRACT_PATH))
OPERATIONS = {
    (operation.method.upper(), operation.path): operation
    for result in SCHEMA.get_all_operations()
    for operation in [result.ok()]
}


def _call_case(client: TestClient, case: Any):
    kwargs = case.as_transport_kwargs()
    kwargs.pop("method", None)
    kwargs.pop("url", None)
    return client.request(case.method, case.formatted_path, **kwargs)


CONTRACT_CASES = [
    ("GET", "/healthz", {}),
    ("GET", "/meta", {}),
    ("GET", "/strategies", {"query": {"enabled_only": False}}),
    (
        "GET",
        "/strategies/{slug}",
        {"path_parameters": {"slug": "midterm_52w_high_momentum"}},
    ),
    (
        "GET",
        "/strategies/{slug}/backtest",
        {"path_parameters": {"slug": "midterm_52w_high_momentum"}},
    ),
    (
        "GET",
        "/strategies/{slug}/backtest/equity-curve",
        {"path_parameters": {"slug": "midterm_52w_high_momentum"}},
    ),
    (
        "POST",
        "/strategies/{slug}/run",
        {
            "path_parameters": {"slug": "midterm_52w_high_momentum"},
            "body": {
                "parameters": {
                    "tickers": ["UNH"],
                    "regime_gate": False,
                    "refresh_events": False,
                },
                "filters": {"exclude_earnings_within_days": 0},
            },
        },
    ),
    ("GET", "/candidates/{ticker}", {"path_parameters": {"ticker": "HFRO"}}),
    ("GET", "/analyze/{ticker}", {"path_parameters": {"ticker": "UNH"}}),
    (
        "GET",
        "/candidates/{ticker}/history",
        {"path_parameters": {"ticker": "HFRO"}, "query": {"days": 400}},
    ),
    ("GET", "/regime", {}),
    ("GET", "/events/market", {"query": {"days_ahead": 60}}),
    ("GET", "/events/ticker/{ticker}", {"path_parameters": {"ticker": "UNH"}}),
    ("GET", "/shariah/status/{ticker}", {"path_parameters": {"ticker": "AAPL"}}),
    (
        "POST",
        "/sizing",
        {
            "body": {
                "candidate_ticker": "TEST",
                "entry": "50",
                "candidate_sector": "Technology",
                "total_capital": "5000",
                "holdings": [],
                "caps": {
                    "per_position_cap_pct": 0.1,
                    "per_sector_cap_pct": 0.25,
                },
            }
        },
    ),
    (
        "POST",
        "/portfolio/quotes",
        {
            "body": {
                "holdings": [
                    {
                        "ticker": "UNH",
                        "strategy_slug": "midterm_52w_high_momentum",
                    }
                ]
            }
        },
    ),
]


@pytest.mark.parametrize("method,path,overrides", CONTRACT_CASES)
def test_openapi_positive_cases_validate_response_schema(
    method: str, path: str, overrides: dict[str, Any]
):
    operation = OPERATIONS[(method, path)]
    case = operation.as_strategy(**overrides).example()
    response = _call_case(TestClient(app), case)

    assert response.status_code < 500
    case.validate_response(response)
