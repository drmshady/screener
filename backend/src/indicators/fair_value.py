"""Fair-value / intrinsic-value estimate (feature 011 US3, contracts/fair-value.md).

Two free, point-in-time bases — no new data source. Both are derived from inputs
already produced for the value-composite strategy
([`indicators/valuation.py`](valuation.py) yields +
``FundamentalsLoader.value_metrics_as_of``) plus the latest close:

- ``"intrinsic_model"`` (default): the **Graham number**
  ``sqrt(22.5 * EPS * BVPS)`` (Graham & Dodd / Graham, *The Intelligent Investor*,
  1973 rev., ch. 14) — a textbook conservative intrinsic-value estimate.
- ``"valuation_yields"``: fair value = book value per share (Fama & French 1992;
  Lakonishok, Shleifer & Vishny 1994) — the existing book/market yield expressed as
  a price rather than a ratio.

EPS and BVPS are *back-derived* from the already-computed per-name yields rather
than re-fetched, since ``yield = fundamental / market_cap`` and
``market_cap = shares * close`` imply ``fundamental / shares = yield * close``.
This keeps the estimate a pure function of inputs the engine already computes.

Pure, no I/O; fixture-tested in ``tests/indicators/test_fair_value.py`` (Principle IV).
"""
from __future__ import annotations

import math
from datetime import date

_BASES = {"valuation_yields", "intrinsic_model"}

# Plausibility band relative to price (Edge Cases, FR-018): a fair value outside
# this band relative to close is not trusted. Placeholder pending US4 calibration.
_MAX_PRICE_MULTIPLE = 10.0
_MIN_PRICE_FRACTION = 0.05


def _bvps(book_to_market: float | None, close: float | None) -> float | None:
    if book_to_market is None or close is None:
        return None
    return float(book_to_market) * float(close)


def _eps(earnings_yield: float | None, close: float | None) -> float | None:
    if earnings_yield is None or close is None:
        return None
    return float(earnings_yield) * float(close)


def graham_number(eps: float | None, bvps: float | None) -> float | None:
    """``sqrt(22.5 * EPS * BVPS)``. None unless both EPS and BVPS are positive —
    Graham's formula is undefined (and not conservative) for negative earnings or
    book value."""
    if eps is None or bvps is None or eps <= 0 or bvps <= 0:
        return None
    return math.sqrt(22.5 * eps * bvps)


def estimate_fair_value(
    *,
    close: float | None,
    book_to_market: float | None,
    earnings_yield: float | None,
    period_end: str | None,
    as_of: date,
    basis: str = "intrinsic_model",
    max_stale_days: int = 450,
) -> dict:
    """Pure per-candidate fair-value estimate (data-model.md "Fair-value estimate").

    ``period_end`` is the period end (ISO date string) of the EDGAR filing backing
    ``book_to_market``/``earnings_yield``
    (``FundamentalsLoader.value_metrics_as_of``'s ``period_end``); ``None`` when
    unknown. ``as_of`` is the snapshot/backtest date driving staleness — point in
    time, no hindsight. ``max_stale_days`` mirrors the existing
    ``FundamentalsLoader._SHARES_MAX_STALE_DAYS`` staleness pattern.

    Returns ``{fair_value, basis, source_as_of, provenance, trust_flag,
    margin_of_safety}``. ``trust_flag`` is one of "trusted" / "unavailable" /
    "stale" / "out_of_range" (FR-016/018) — only "trusted" estimates may feed
    downstream sizing conviction or the US2 reward ceiling.
    """
    resolved_basis = basis if basis in _BASES else "intrinsic_model"
    bvps = _bvps(book_to_market, close)
    eps = _eps(earnings_yield, close)

    if resolved_basis == "intrinsic_model":
        fair_value = graham_number(eps, bvps)
        provenance = (
            "EDGAR value_metrics_as_of (book/market + earnings yields) -> "
            "EPS/BVPS -> Graham number sqrt(22.5*EPS*BVPS) "
            "(Graham, The Intelligent Investor, 1973 rev., ch. 14)"
        )
    else:
        fair_value = bvps if bvps is not None and bvps > 0 else None
        provenance = (
            "EDGAR value_metrics_as_of (book/market yield) -> book value per share "
            "(Fama-French 1992; Lakonishok-Shleifer-Vishny 1994)"
        )

    source_as_of = period_end or as_of.isoformat()

    if fair_value is None:
        trust_flag = "unavailable"
    elif period_end is not None and (as_of - date.fromisoformat(period_end)).days > max_stale_days:
        trust_flag = "stale"
    elif (
        close is None
        or close <= 0
        or fair_value > close * _MAX_PRICE_MULTIPLE
        or fair_value < close * _MIN_PRICE_FRACTION
    ):
        trust_flag = "out_of_range"
    else:
        trust_flag = "trusted"

    margin_of_safety = None
    if trust_flag == "trusted" and fair_value and close:
        margin_of_safety = (fair_value - float(close)) / fair_value

    return {
        "fair_value": fair_value,
        "basis": resolved_basis,
        "source_as_of": source_as_of,
        "provenance": provenance,
        "trust_flag": trust_flag,
        "margin_of_safety": margin_of_safety,
    }
