from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from backend.src.api.app import app
from backend.src.models.portfolio import PortfolioCaps, SizingHolding, SizingRequest
from backend.src.portfolio.exposure import aggregate_exposure
from backend.src.portfolio.sizing import size_position


def _six_stock_portfolio() -> list[SizingHolding]:
    return [
        SizingHolding(
            ticker="AAA",
            shares=Decimal("4"),
            current_price=Decimal("100"),
            sector="Health Care",
        ),
        SizingHolding(
            ticker="BBB",
            shares=Decimal("3"),
            current_price=Decimal("90"),
            sector="Industrials",
        ),
        SizingHolding(
            ticker="CCC",
            shares=Decimal("2"),
            current_price=Decimal("110"),
            sector="Technology",
        ),
        SizingHolding(
            ticker="DDD",
            shares=Decimal("5"),
            current_price=Decimal("60"),
            sector="Utilities",
        ),
        SizingHolding(
            ticker="EEE",
            shares=Decimal("6"),
            current_price=Decimal("50"),
            sector="Financials",
        ),
        SizingHolding(
            ticker="FFF",
            shares=Decimal("2"),
            current_price=Decimal("120"),
            sector="Materials",
        ),
    ]


def test_exposure_aggregates_sectors_and_flags_concentration() -> None:
    exposure = aggregate_exposure(
        holdings=[
            SizingHolding(
                ticker="AAA",
                shares=Decimal("15"),
                current_price=Decimal("100"),
                sector="Technology",
            ),
            SizingHolding(
                ticker="BBB",
                shares=Decimal("4"),
                current_price=Decimal("100"),
                sector="Technology",
            ),
        ],
        total_capital=Decimal("5000"),
        caps=PortfolioCaps(per_position_cap_pct=0.10, per_sector_cap_pct=0.25),
    )

    technology = next(
        sector for sector in exposure.sectors if sector.sector == "Technology"
    )
    assert technology.dollar_value == Decimal("1900.00")
    assert technology.over_cap is True
    assert {flag.kind for flag in exposure.concentration_flags} == {
        "position",
        "sector",
    }


def test_50_sampled_candidate_sizes_never_breach_caps() -> None:
    holdings = _six_stock_portfolio()
    sectors = [
        "Health Care",
        "Industrials",
        "Technology",
        "Utilities",
        "Financials",
        "Materials",
    ]
    total_capital = Decimal("5000")
    caps = PortfolioCaps(per_position_cap_pct=0.10, per_sector_cap_pct=0.25)

    for index in range(50):
        entry = Decimal(12 + (index % 17) * 3)
        sector = sectors[index % len(sectors)]
        request = SizingRequest(
            candidate_ticker=f"NEW{index}",
            entry=entry,
            candidate_sector=sector,
            total_capital=total_capital,
            holdings=holdings,
            caps=caps,
        )

        response = size_position(request)

        if response.caps_respected:
            assert response.suggested_shares >= 1
            assert (
                response.resulting_position_pct_of_capital <= caps.per_position_cap_pct
            )
            assert response.resulting_sector_pct_of_capital <= caps.per_sector_cap_pct
        else:
            assert response.suggested_shares == 0
            assert "Cannot size without breaching cap" in response.reasoning


def test_cannot_size_when_one_share_breaches_position_cap() -> None:
    response = size_position(
        SizingRequest(
            candidate_ticker="BIG",
            entry=Decimal("501"),
            candidate_sector="Technology",
            total_capital=Decimal("5000"),
            holdings=[],
            caps=PortfolioCaps(per_position_cap_pct=0.10, per_sector_cap_pct=0.25),
        )
    )

    assert response.caps_respected is False
    assert response.suggested_shares == 0
    assert "Cannot size without breaching cap" in response.reasoning


def test_sizing_endpoint_returns_structured_422_body_for_cap_breach() -> None:
    client = TestClient(app)

    response = client.post(
        "/sizing",
        json={
            "candidate_ticker": "BIG",
            "entry": "501",
            "candidate_sector": "Technology",
            "total_capital": "5000",
            "holdings": [],
            "caps": {"per_position_cap_pct": 0.10, "per_sector_cap_pct": 0.25},
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["caps_respected"] is False
    assert payload["suggested_shares"] == 0
    assert "Cannot size without breaching cap" in payload["reasoning"]
