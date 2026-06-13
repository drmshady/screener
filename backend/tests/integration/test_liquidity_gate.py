from __future__ import annotations

import pandas as pd

from backend.src.data.universe import UniverseLoader


def test_liquidity_gate_excludes_at_least_95_percent_of_sub_1m_adv_tickers():
    dates = pd.bdate_range(end="2026-01-31", periods=25)
    rows: list[dict[str, object]] = []

    for idx in range(95):
        ticker = f"LOW{idx:03d}"
        for as_of_date in dates:
            rows.append(
                {
                    "ticker": ticker,
                    "as_of_date": as_of_date,
                    "close": 10.0,
                    "volume": 50_000,
                }
            )

    for idx in range(5):
        ticker = f"HIGH{idx:03d}"
        for as_of_date in dates:
            rows.append(
                {
                    "ticker": ticker,
                    "as_of_date": as_of_date,
                    "close": 25.0,
                    "volume": 100_000,
                }
            )

    prices = pd.DataFrame(rows)
    liquid = set(
        UniverseLoader(prices).get_liquid_universe(
            as_of_date="2026-01-31",
            min_adv_20d=1_000_000,
            min_price=5.0,
        )
    )
    low_tickers = {f"LOW{idx:03d}" for idx in range(95)}
    high_tickers = {f"HIGH{idx:03d}" for idx in range(5)}

    excluded_low = low_tickers - liquid
    assert len(excluded_low) / len(low_tickers) >= 0.95
    assert high_tickers <= liquid
