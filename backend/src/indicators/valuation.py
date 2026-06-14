"""Value-multiple indicators (Fama & French 1992; Lakonishok, Shleifer & Vishny 1994).

Every measure is a **yield** (fundamental / market value), so higher = cheaper and
a negative numerator (negative earnings, negative book value) produces a negative
yield that sorts as *least* cheap — never as artificially cheap, which is the
failure mode of price/earnings or price/book when the denominator is tiny or
negative. Pure functions: no I/O, fixture-tested in tests/indicators/.
"""
from __future__ import annotations

import math
from typing import Mapping


def _is_missing(value) -> bool:
    if value is None:
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return True


def _yield(numerator, market_cap) -> float | None:
    """fundamental / market_cap. None when either input is missing or market_cap
    is non-positive; a negative numerator is preserved (not clamped)."""
    if _is_missing(numerator) or _is_missing(market_cap):
        return None
    mc = float(market_cap)
    if mc <= 0:
        return None
    return float(numerator) / mc


def book_to_market(common_equity, market_cap) -> float | None:
    """Common (book) equity / market cap. Negative equity → negative B/M."""
    return _yield(common_equity, market_cap)


def earnings_yield(net_income_ttm, market_cap) -> float | None:
    """Trailing-12-month net income / market cap (earnings yield, inverse of P/E)."""
    return _yield(net_income_ttm, market_cap)


def cashflow_yield(operating_cf_ttm, market_cap) -> float | None:
    """Trailing-12-month operating cash flow / market cap."""
    return _yield(operating_cf_ttm, market_cap)


def sales_yield(revenue_ttm, market_cap) -> float | None:
    """Trailing-12-month revenue / market cap (inverse of price/sales)."""
    return _yield(revenue_ttm, market_cap)


def value_composite(
    percentile_ranks: Mapping[str, float | None],
) -> tuple[float | None, int]:
    """Mean of the available per-metric cross-sectional percentile ranks.

    `percentile_ranks` maps each value metric to this name's rank in [0, 1]
    (higher = cheaper), or None when that metric was unavailable. Returns
    (composite, n_evaluable). The composite ignores missing members and reports
    how many it used, so a name is never voided by one absent ratio and the
    honesty of partial coverage is preserved.
    """
    present = [float(v) for v in percentile_ranks.values() if not _is_missing(v)]
    if not present:
        return None, 0
    return sum(present) / len(present), len(present)
