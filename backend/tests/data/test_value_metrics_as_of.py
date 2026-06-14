"""Point-in-time value fundamentals (Principle I + III: no look-ahead).

Uses a synthetic companyfacts payload (no network). Verifies that only filings
filed on/before the as-of date are visible, that current AND prior annual values
are returned for the F-Score deltas, and that missing concepts yield None rather
than a fabricated number.
"""
from datetime import date

from backend.src.data.fundamentals import FundamentalsLoader


def _row(end: str, filed: str, val: float, form: str = "10-K") -> dict:
    return {"end": end, "filed": filed, "val": val, "form": form}


def _usd(rows: list[dict]) -> dict:
    return {"units": {"USD": rows}}


def _shares(rows: list[dict]) -> dict:
    return {"units": {"shares": rows}}


def _payload() -> dict:
    # Two annual periods filed in 2023 (FY2022) and 2024 (FY2023).
    def two(v2022: float, v2023: float) -> dict:
        return _usd([
            _row("2022-12-31", "2023-02-15", v2022),
            _row("2023-12-31", "2024-02-15", v2023),
        ])

    us_gaap = {
        "StockholdersEquity": two(900.0, 1000.0),
        "NetIncomeLoss": two(80.0, 120.0),
        "NetCashProvidedByUsedInOperatingActivities": two(90.0, 150.0),
        "Revenues": two(900.0, 1000.0),
        "Assets": two(1000.0, 1100.0),
        "Liabilities": two(500.0, 520.0),
        "GrossProfit": two(300.0, 420.0),
        "AssetsCurrent": two(400.0, 500.0),
        "LiabilitiesCurrent": two(200.0, 200.0),
        "LongTermDebtNoncurrent": two(200.0, 150.0),
        "EntityCommonStockSharesOutstanding": _shares([
            _row("2022-12-31", "2023-02-15", 100.0),
            _row("2023-12-31", "2024-02-15", 100.0),
        ]),
    }
    return {"facts": {"us-gaap": us_gaap}, "sic": "3571"}


def test_returns_current_and_prior_annual_values():
    m = FundamentalsLoader().value_metrics_as_of("TEST", date(2024, 3, 1), payload=_payload())
    # Current = FY2023
    assert m["common_equity"] == 1000.0
    assert m["net_income"] == 120.0
    assert m["operating_cf"] == 150.0
    assert m["revenue"] == 1000.0
    assert m["total_assets"] == 1100.0
    assert m["gross_profit"] == 420.0
    assert m["current_assets"] == 500.0
    assert m["current_liabilities"] == 200.0
    assert m["long_term_debt"] == 150.0
    assert m["shares_outstanding"] == 100.0
    # Prior = FY2022 (for the F-Score deltas)
    assert m["prior_net_income"] == 80.0
    assert m["prior_total_assets"] == 1000.0
    assert m["prior_operating_cf"] == 90.0
    assert m["prior_revenue"] == 900.0
    assert m["prior_gross_profit"] == 300.0
    assert m["prior_long_term_debt"] == 200.0


def test_point_in_time_hides_unfiled_year():
    # As of mid-2023, FY2023 (filed 2024-02-15) is NOT yet visible.
    m = FundamentalsLoader().value_metrics_as_of("TEST", date(2023, 6, 1), payload=_payload())
    assert m["net_income"] == 80.0          # latest visible = FY2022
    assert m["prior_net_income"] is None     # no FY2021 in the payload
    assert m["total_assets"] == 1000.0


def test_missing_concept_returns_none_not_fabricated():
    payload = _payload()
    del payload["facts"]["us-gaap"]["GrossProfit"]
    del payload["facts"]["us-gaap"]["LongTermDebtNoncurrent"]
    m = FundamentalsLoader().value_metrics_as_of("TEST", date(2024, 3, 1), payload=payload)
    assert m["gross_profit"] is None
    assert m["prior_gross_profit"] is None
    assert m["long_term_debt"] is None
    # Unaffected concepts still resolve.
    assert m["net_income"] == 120.0


def test_stale_us_gaap_shares_are_rejected():
    """Regression for the RTX bug: financials are current (2023) but the only
    us-gaap share count is from a 2009 filing. Pairing a years-stale share count
    with current financials produces a 1000x-wrong market cap, so the stale count
    MUST be rejected (shares -> None) rather than silently used."""
    payload = _payload()
    # Replace shares with ONLY a 2009-period row (no recent shares anywhere).
    payload["facts"]["us-gaap"]["EntityCommonStockSharesOutstanding"] = _shares(
        [_row("2009-12-31", "2010-02-11", 1_381_700.0)]
    )
    m = FundamentalsLoader().value_metrics_as_of("TEST", date(2024, 3, 1), payload=payload)
    assert m["shares_outstanding"] is None  # too stale vs the 2023 as-of


def test_dei_cover_page_shares_are_preferred():
    """The dei cover-page share count (full actual shares, all modern filers) is
    used when present, even across 10-Q forms."""
    payload = _payload()
    payload["facts"]["dei"] = {
        "EntityCommonStockSharesOutstanding": _shares([
            _row("2024-01-31", "2024-02-15", 1_340_000_000.0, form="10-K"),
        ])
    }
    m = FundamentalsLoader().value_metrics_as_of("TEST", date(2024, 3, 1), payload=payload)
    assert m["shares_outstanding"] == 1_340_000_000.0
