from __future__ import annotations

import pandas as pd

from ..models.strategy import Modification, Strategy, StrategyParameter
from ._artifacts import backtest_bias_passes, load_backtest_summary
from ._registry import registry

SLUG = "shortterm_atr_breakout"
NAME = "Short-Term ATR Breakout"
CITATION = "Wilder (1978), New Concepts in Technical Trading Systems; Turtle breakout rules"
TIMEFRAME = "Short-term"
DESCRIPTION = (
    "Looks for liquid stocks closing through a recent high, then derives risk from ATR "
    "with a Chandelier-style trailing-exit reference."
)

HOLDING_PERIOD = {"min": 5, "max": 20}

PARAMETERS = {
    "breakout_lookback_days": StrategyParameter(default=20, min=10, max=100, type="int", description="Prior high window for breakout confirmation"),
    "atr_multiplier": StrategyParameter(default=1.5, min=0.5, max=5.0, type="float", description="Initial stop distance in ATR units"),
    "require_above_sma200": StrategyParameter(default=True, type="bool", description="Require close above the 200-day SMA"),
    "require_sma200_rising": StrategyParameter(default=True, type="bool", description="Require the 200-day SMA to be rising"),
    "chandelier_multiplier": StrategyParameter(default=3.0, min=1.0, max=6.0, type="float", description="Chandelier Exit ATR multiplier"),
    "chandelier_target_r_multiple": StrategyParameter(default=1.0, min=0.5, max=3.0, type="float", description="Reference target derived from Chandelier trailing-stop distance"),
}

REGIME_FAVORABILITY = {
    "Trending up": "Favorable",
    "Range-bound": "Neutral",
    "Trending down": "Unfavorable",
}

MODIFICATIONS = [
    Modification(
        name="Trend-of-trend filter",
        description="Requires price above the 200-day SMA and the 200-day SMA rising by default.",
        citation="LeBeau-style long-term trend filter; related to Faber (2007)",
    ),
    Modification(
        name="Chandelier Exit reference",
        description="Calculates a Chandelier long exit from recent highs and ATR; the API target is derived from that trailing-stop distance.",
        citation="Chuck LeBeau; LeBeau & Lucas (1992), Computer Analysis of the Futures Markets",
    ),
    Modification(
        name="Universe liquidity gate",
        description="Uses the shared price and dollar-volume floor before breakout rules run.",
        citation="Institutional momentum/liquidity risk-control convention",
    ),
]


def _empty_like(df: pd.DataFrame) -> pd.DataFrame:
    return df.iloc[0:0].copy()


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce")


def rules(universe_df: pd.DataFrame) -> pd.DataFrame:
    if universe_df.empty:
        return pd.DataFrame()

    required = {"close", "breakout_high_20", "atr", "sma_200", "sma_200_20d_ago", "chandelier_exit"}
    if missing := required.difference(universe_df.columns):
        return _empty_like(universe_df.assign(_missing=",".join(sorted(missing))))

    df = universe_df.copy()
    close = _numeric(df, "close")
    breakout_high = _numeric(df, "breakout_high_20")
    atr = _numeric(df, "atr")
    sma_200 = _numeric(df, "sma_200")
    sma_200_prev = _numeric(df, "sma_200_20d_ago")

    breakout = close >= breakout_high
    valid_atr = atr > 0
    if PARAMETERS["require_above_sma200"].default:
        trend = close > sma_200
    else:
        trend = pd.Series(True, index=df.index)
    if PARAMETERS["require_sma200_rising"].default:
        trend = trend & (sma_200 > sma_200_prev)

    matched = df[breakout & valid_atr & trend].copy()
    if matched.empty:
        return matched

    entry = _numeric(matched, "close")
    atr = _numeric(matched, "atr")
    chandelier_exit = _numeric(matched, "chandelier_exit")
    initial_stop = entry - PARAMETERS["atr_multiplier"].default * atr
    chandelier_risk = (entry - chandelier_exit).clip(lower=atr)

    matched["entry"] = entry
    matched["stop_loss"] = initial_stop
    matched["trailing_stop"] = chandelier_exit
    matched["take_profit"] = entry + PARAMETERS["chandelier_target_r_multiple"].default * chandelier_risk
    matched["score"] = ((entry / _numeric(matched, "breakout_high_20")) - 1.0) / atr.clip(lower=0.01)
    matched["reason"] = "N-day high close with ATR stop and Chandelier trailing-exit reference"
    return matched[matched["stop_loss"] > 0]


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
