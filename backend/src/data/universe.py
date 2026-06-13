import pandas as pd
from typing import List


class UniverseLoader:
    def __init__(self, prices_df: pd.DataFrame):
        self.prices = prices_df

    def get_liquid_universe(
        self, as_of_date: str, min_adv_20d: float = 1_000_000, min_price: float = 5.0
    ) -> List[str]:
        """
        Returns a list of tickers that pass the liquidity gate as of the given date.
        Requires prices_df to have at least 20 days of history prior to as_of_date.
        """
        if self.prices.empty:
            return []

        as_of_ts = pd.Timestamp(as_of_date)

        past_data = self.prices[self.prices["as_of_date"] <= as_of_ts].copy()
        if past_data.empty:
            return []

        past_data["ticker"] = past_data["ticker"].astype(str).str.upper()
        past_data = past_data.sort_values(["ticker", "as_of_date"])
        trailing = past_data.groupby("ticker", sort=False).tail(20).copy()
        if trailing.empty:
            return []

        trailing["dollar_volume"] = trailing["close"].astype(float) * trailing[
            "volume"
        ].astype(float)
        adv = trailing.groupby("ticker", sort=False)["dollar_volume"].mean()
        last_close = (
            trailing.groupby("ticker", sort=False)["close"].last().astype(float)
        )

        liquid = adv[(adv >= min_adv_20d) & (last_close >= min_price)]
        return sorted(liquid.index.astype(str).tolist())
