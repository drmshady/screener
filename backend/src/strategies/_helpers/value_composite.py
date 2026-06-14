"""Cross-sectional value composite (Fama & French 1992; Lakonishok, Shleifer &
Vishny 1994).

The composite is the mean of a name's cross-sectional **percentile ranks** on the
four value yields (book/market, earnings, cash-flow, sales). Percentile ranking is
scale-free, so one large ratio can't dominate, and negative yields (negative
book/earnings) correctly land at the bottom. Ranks are computed within sector by
default so structurally-cheap/expensive sectors (financials, REITs) compete with
their own peers (FR-014). Names missing a yield use the yields they have, and the
count of evaluable yields is recorded for honest accounting.
"""
from __future__ import annotations

import pandas as pd

YIELD_COLUMNS = ("book_to_market", "earnings_yield", "cashflow_yield", "sales_yield")


def compute_value_composite(
    df: pd.DataFrame, *, within_sector: bool = True
) -> pd.DataFrame:
    """Return a copy of ``df`` with ``value_composite`` (higher = cheaper) and
    ``value_metrics_count`` (0-4 evaluable yields) columns added.

    `within_sector` ranks each yield among sector peers; otherwise across the
    whole frame. A row with no evaluable yield gets ``value_composite = NaN`` and
    ``value_metrics_count = 0``.
    """
    out = df.copy()
    present = [c for c in YIELD_COLUMNS if c in out.columns]
    if not present:
        out["value_composite"] = float("nan")
        out["value_metrics_count"] = 0
        return out

    rank_frame = pd.DataFrame(index=out.index)
    for col in present:
        numeric = pd.to_numeric(out[col], errors="coerce")
        if within_sector and "sector" in out.columns:
            # pct rank within each sector; higher yield -> higher (cheaper) rank.
            rank_frame[col] = numeric.groupby(out["sector"]).rank(pct=True)
        else:
            rank_frame[col] = numeric.rank(pct=True)

    out["value_composite"] = rank_frame.mean(axis=1, skipna=True)
    out["value_metrics_count"] = rank_frame.notna().sum(axis=1).astype(int)
    return out
