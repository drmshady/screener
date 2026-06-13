from __future__ import annotations

import pandas as pd

from ..models.strategy import Modification, Strategy, StrategyParameter
from ._artifacts import backtest_bias_passes, load_backtest_summary
from ._registry import registry

SLUG = "shortterm_minervini_vcp"
NAME = "Short-Term Minervini VCP"
CITATION = "Mark Minervini (2013), Trade Like a Stock Market Wizard"
TIMEFRAME = "Short-term"
DESCRIPTION = (
    "Looks for liquid stocks breaking through a recent pivot after volatility contraction, "
    "with trend alignment and breakout-volume confirmation."
)

HOLDING_PERIOD = {"min": 5, "max": 30}

PARAMETERS = {
    "pivot_lookback_days": StrategyParameter(default=50, min=20, max=100, type="int", description="Prior high window used as the breakout pivot"),
    "contraction_lookback_days": StrategyParameter(default=20, min=10, max=40, type="int", description="Recent low window used for contraction risk"),
    "max_adr_ratio": StrategyParameter(default=0.7, min=0.2, max=1.0, type="float", description="Recent ADR divided by prior ADR must be below this value"),
    "min_volume_ratio": StrategyParameter(default=1.5, min=1.0, max=5.0, type="float", description="Breakout-day volume divided by prior 50-day average volume"),
    "max_pivot_extension_pct": StrategyParameter(default=0.03, min=0.0, max=0.15, type="float", description="Maximum close extension above pivot"),
    "max_stop_pct": StrategyParameter(default=0.12, min=0.02, max=0.25, type="float", description="Maximum pivot-to-contraction-low risk"),
    "take_profit_r_multiple": StrategyParameter(default=2.5, min=2.0, max=3.0, type="float", description="Reference target as an R multiple"),
}

REGIME_FAVORABILITY = {
    "Trending up": "Favorable",
    "Range-bound": "Neutral",
    "Trending down": "Unfavorable",
}

MODIFICATIONS = [
    Modification(
        name="ADR-ratio contraction",
        description="Requires recent 20-day average daily range to contract versus the prior 20-day window.",
        citation="Quantified implementation of Minervini's volatility contraction pattern",
    ),
    Modification(
        name="Volume confirmation",
        description="Requires breakout-day volume to exceed the prior 50-day average by at least 1.5x.",
        citation="Minervini (2013), breakout-volume confirmation rule",
    ),
    Modification(
        name="Earnings exclusion default",
        description="Defaults to skipping candidates with known earnings inside seven days once the events layer is enabled.",
        citation="Risk-control overlay for short-term event gaps",
    ),
]


def _empty_like(df: pd.DataFrame) -> pd.DataFrame:
    return df.iloc[0:0].copy()


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce")


def rules(universe_df: pd.DataFrame) -> pd.DataFrame:
    if universe_df.empty:
        return pd.DataFrame()

    required = {
        "close",
        "breakout_high_50",
        "contraction_low_20",
        "adr_ratio_20_20",
        "volume_ratio_50",
        "sma_50",
        "sma_150",
        "sma_200",
        "sma_200_20d_ago",
    }
    if missing := required.difference(universe_df.columns):
        return _empty_like(universe_df.assign(_missing=",".join(sorted(missing))))

    df = universe_df.copy()
    close = _numeric(df, "close")
    pivot = _numeric(df, "breakout_high_50")
    stop = _numeric(df, "contraction_low_20")
    adr_ratio = _numeric(df, "adr_ratio_20_20")
    volume_ratio = _numeric(df, "volume_ratio_50")
    sma_50 = _numeric(df, "sma_50")
    sma_150 = _numeric(df, "sma_150")
    sma_200 = _numeric(df, "sma_200")
    sma_200_prev = _numeric(df, "sma_200_20d_ago")

    stage_two = (close > sma_50) & (sma_50 > sma_150) & (sma_150 > sma_200) & (sma_200 > sma_200_prev)
    pivot_break = (close >= pivot) & (close <= pivot * (1.0 + PARAMETERS["max_pivot_extension_pct"].default))
    contraction = adr_ratio <= PARAMETERS["max_adr_ratio"].default
    volume_confirmed = volume_ratio >= PARAMETERS["min_volume_ratio"].default
    valid_risk = (stop > 0) & (stop < pivot)
    risk_pct = (pivot - stop) / pivot
    tight_stop = risk_pct <= PARAMETERS["max_stop_pct"].default

    matched = df[stage_two & pivot_break & contraction & volume_confirmed & valid_risk & tight_stop].copy()
    if matched.empty:
        return matched

    matched["entry"] = _numeric(matched, "breakout_high_50")
    matched["stop_loss"] = _numeric(matched, "contraction_low_20")
    risk = matched["entry"] - matched["stop_loss"]
    matched["take_profit"] = matched["entry"] + PARAMETERS["take_profit_r_multiple"].default * risk
    matched["score"] = (
        _numeric(matched, "volume_ratio_50")
        / _numeric(matched, "adr_ratio_20_20").clip(lower=0.01)
        * (1.0 - (risk / matched["entry"]).clip(lower=0.0, upper=1.0))
    )
    matched["reason"] = "VCP pivot breakout with ADR contraction and volume confirmation"
    return matched


strategy = Strategy(
    slug=SLUG,
    name=NAME,
    timeframe=TIMEFRAME,
    citation=CITATION,
    description=DESCRIPTION,
    holding_period_days=HOLDING_PERIOD,
    parameters=PARAMETERS,
    regime_favorability=REGIME_FAVORABILITY,
    default_exclude_earnings_within_days=7,
    enabled_by_default=backtest_bias_passes(SLUG),
    modifications=MODIFICATIONS,
    rules=rules,
    backtest_summary=load_backtest_summary(SLUG),
)

registry.register(strategy)
