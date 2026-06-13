from __future__ import annotations

import numpy as np
import pandas as pd

from backend.src.regime.breadth import calculate_breadth_from_prices
from backend.src.regime.calculator import current_regime_response


def _prices(ticker: str, closes: np.ndarray, end: str = "2026-01-31") -> pd.DataFrame:
    dates = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({"ticker": ticker, "as_of_date": dates, "close": closes})


def test_breadth_counts_constituents_above_200_day_sma():
    frame = pd.concat(
        [
            _prices("AAA", np.linspace(100, 250, 260)),
            _prices(
                "BBB",
                np.concatenate([np.linspace(100, 200, 160), np.linspace(200, 80, 100)]),
            ),
            _prices("CCC", np.linspace(50, 120, 260)),
        ],
        ignore_index=True,
    )

    pct_above, above, eligible = calculate_breadth_from_prices(
        frame, ["AAA", "BBB", "CCC"]
    )

    assert eligible == 3
    assert above == 2
    assert pct_above == 2 / 3


def test_regime_fixed_snapshot_is_identical_across_20_runs():
    spy = _prices(
        "SPY", np.concatenate([np.linspace(300, 450, 160), np.linspace(450, 320, 100)])
    )
    breadth = pd.concat(
        [
            _prices("AAA", np.linspace(100, 250, 260)),
            _prices(
                "BBB",
                np.concatenate([np.linspace(100, 210, 160), np.linspace(210, 90, 100)]),
            ),
            _prices(
                "CCC",
                np.concatenate([np.linspace(100, 190, 150), np.linspace(190, 70, 110)]),
            ),
        ],
        ignore_index=True,
    )

    responses = [
        current_regime_response(
            spy_prices=spy,
            breadth_prices=breadth,
            constituents=["AAA", "BBB", "CCC"],
        ).model_dump(mode="json", exclude={"data_as_of"})
        for _ in range(20)
    ]

    assert all(response == responses[0] for response in responses)
    assert responses[0]["regime"] == "Trending down"
    assert responses[0]["inputs"]["breadth_above_count"] == 1
    assert responses[0]["inputs"]["breadth_eligible_count"] == 3
