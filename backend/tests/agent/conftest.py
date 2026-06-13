from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.src.api.app import app
from backend.src.models.strategy import AnalyzeResponse, GateResult
from backend.src.strategies._registry import registry
from backend.src import strategies as _strategies  # noqa: F401 - register strategies

# Candidates known on the reference snapshot (the validation oracle set). The
# endpoint tests probe these and use the first that analyzes successfully.
_REFERENCE_TICKERS = ["AMAT", "ROST", "EA", "BELFB", "ASYS"]


@pytest.fixture(scope="session")
def midterm_strategy():
    return registry.get("midterm_52w_high_momentum")


@pytest.fixture
def sample_result() -> AnalyzeResponse:
    """A deterministic, hand-built candidate result for builder unit tests.

    Includes a genuine pass, a fail, and a skipped gate so the honesty/fail-open
    assertions have something to bite on. No snapshot or network needed.
    """
    return AnalyzeResponse(
        ticker="TEST",
        name="Test Corp",
        sector="Technology",
        strategy="midterm_52w_high_momentum",
        as_of="2026-06-12",
        would_be_selected=True,
        current_price="100.00",
        entry="100.00",
        stop_loss="90.00",
        tighter_stop_loss="95.00",
        take_profit="130.00",
        return_12_1=0.42,
        vol_scalar=0.88,
        dist_to_high=0.018,
        atr=3.25,
        debt_to_equity=0.78,
        fcf_ttm=1_200_000_000.0,
        gp_to_assets=0.38,
        asset_growth=0.055,
        gate_results=[
            GateResult(
                gate="52-week-high proximity",
                status="pass",
                detail="2.0% below the 52-week high (within the 5% limit)",
            ),
            GateResult(
                gate="Quality (leverage + cash flow)",
                status="fail",
                detail="debt/equity 2.10 > 1.5; free cash flow positive",
            ),
            GateResult(
                gate="Low asset growth",
                status="skipped",
                detail="asset-growth data unavailable (passed through)",
            ),
        ],
        data_notes=["gross-profitability gate evaluated against the 591-name universe"],
        data_as_of="2026-06-12T00:00:00Z",
        disclaimer="This product is for informational purposes only and does not constitute financial advice. It does not place trades.",
    )


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def reference_ticker(client: TestClient) -> str:
    for ticker in _REFERENCE_TICKERS:
        resp = client.get(f"/analyze/{ticker}")
        if resp.status_code == 200:
            return ticker
    pytest.skip("no reference ticker analyzable on the current snapshot")
