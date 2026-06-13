from datetime import date

import pytest

from backend.src.data.fundamentals import FundamentalsLoader


def _fact(end, filed, val):
    return {"form": "10-K", "end": end, "filed": filed, "val": val, "accn": f"acc-{end}"}


def _payload(tags):
    return {"facts": {"us-gaap": {tag: {"units": {"USD": rows}} for tag, rows in tags.items()}}}


def test_quality_metrics_as_of_excludes_filings_filed_after_as_of():
    # FY2021 was filed 2022-02-01; as of 2022-01-15 only FY2020 is visible.
    payload = _payload(
        {
            "GrossProfit": [
                _fact("2020-12-31", "2021-02-01", 400),
                _fact("2021-12-31", "2022-02-01", 999),
            ],
            "Assets": [
                _fact("2020-12-31", "2021-02-01", 1000),
                _fact("2021-12-31", "2022-02-01", 2000),
            ],
        }
    )
    loader = FundamentalsLoader()

    q = loader.quality_metrics_as_of("X", date(2022, 1, 15), payload=payload)
    # Uses FY2020 (filed 2021-02-01 <= as_of), not FY2021 (look-ahead).
    assert q["gross_profit"] == 400.0
    assert q["total_assets"] == 1000.0
    assert q["gp_to_assets"] == 0.4

    q_later = loader.quality_metrics_as_of("X", date(2022, 3, 1), payload=payload)
    # After the FY2021 filing date the newer figures become visible.
    assert q_later["gross_profit"] == 999.0
    assert q_later["gp_to_assets"] == 999.0 / 2000.0


def test_gross_profit_falls_back_to_revenue_minus_cogs():
    payload = _payload(
        {
            "Revenues": [_fact("2020-12-31", "2021-02-01", 1000)],
            "CostOfRevenue": [_fact("2020-12-31", "2021-02-01", 600)],
            "Assets": [_fact("2020-12-31", "2021-02-01", 800)],
        }
    )
    loader = FundamentalsLoader()

    q = loader.quality_metrics_as_of("X", date(2021, 6, 1), payload=payload)
    assert q["gross_profit"] == 400.0  # 1000 - 600
    assert q["gp_to_assets"] == 400.0 / 800.0


def test_quality_metrics_as_of_returns_none_when_nothing_filed_yet():
    payload = _payload({"GrossProfit": [_fact("2020-12-31", "2021-02-01", 400)]})
    loader = FundamentalsLoader()

    q = loader.quality_metrics_as_of("X", date(2020, 6, 1), payload=payload)
    assert q["gross_profit"] is None
    assert q["gp_to_assets"] is None


def test_asset_growth_point_in_time():
    # Assets grew 1000 -> 1200 (FY2020 -> FY2021) = +20% YoY.
    payload = _payload(
        {
            "Assets": [
                _fact("2019-12-31", "2020-02-01", 800),
                _fact("2020-12-31", "2021-02-01", 1000),
                _fact("2021-12-31", "2022-02-01", 1200),
            ],
        }
    )
    loader = FundamentalsLoader()

    # As of 2022-03-01: latest two visible are FY2020 (1000) and FY2021 (1200).
    q = loader.quality_metrics_as_of("X", date(2022, 3, 1), payload=payload)
    assert q["asset_growth"] == pytest.approx(0.20)  # 1200/1000 - 1

    # As of 2021-06-01: FY2021 not yet filed -> uses FY2019 (800) -> FY2020 (1000).
    q_prior = loader.quality_metrics_as_of("X", date(2021, 6, 1), payload=payload)
    assert q_prior["asset_growth"] == pytest.approx(0.25)  # 1000/800 - 1


def test_asset_growth_none_with_single_year():
    payload = _payload({"Assets": [_fact("2020-12-31", "2021-02-01", 1000)]})
    loader = FundamentalsLoader()
    q = loader.quality_metrics_as_of("X", date(2021, 6, 1), payload=payload)
    assert q["asset_growth"] is None  # need >=2 annual points


def test_debt_to_equity_and_fcf_point_in_time():
    payload = _payload(
        {
            "NetCashProvidedByUsedInOperatingActivities": [_fact("2020-12-31", "2021-02-01", 500)],
            "PaymentsToAcquirePropertyPlantAndEquipment": [_fact("2020-12-31", "2021-02-01", 120)],
            "Liabilities": [_fact("2020-12-31", "2021-02-01", 300)],
            "StockholdersEquity": [_fact("2020-12-31", "2021-02-01", 600)],
        }
    )
    loader = FundamentalsLoader()

    q = loader.quality_metrics_as_of("X", date(2021, 6, 1), payload=payload)
    assert q["fcf_ttm"] == 380.0  # 500 - 120
    assert q["debt_to_equity"] == 0.5  # 300 / 600
