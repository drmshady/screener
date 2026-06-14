"""Piotroski (2000) F-Score — "Value Investing: The Use of Historical Financial
Statement Information".

Nine binary fundamental-health signals; the value premium concentrates in cheap
firms that are financially *improving*, so a high F-Score is the canonical
value-trap filter. Pure functions, fixture-tested in tests/indicators/.

A signal whose inputs are unavailable is scored ``None`` (no point awarded) and
decrements the evaluable count — it is never a silent pass. A signal that is
evaluated and fails scores ``0`` (distinct from missing).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields


@dataclass
class FundamentalsYear:
    """One fiscal year of the inputs the nine signals consume. Any field may be
    None (unavailable point-in-time)."""

    net_income: float | None = None
    total_assets: float | None = None
    operating_cf: float | None = None
    long_term_debt: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None
    shares_outstanding: float | None = None
    gross_profit: float | None = None
    revenue: float | None = None


SIGNAL_NAMES = (
    "roa_positive",
    "cfo_positive",
    "roa_improved",
    "accruals_ok",
    "leverage_down",
    "current_ratio_up",
    "no_dilution",
    "gross_margin_up",
    "asset_turnover_up",
)


def _missing(*values) -> bool:
    for value in values:
        if value is None:
            return True
        try:
            if math.isnan(float(value)):
                return True
        except (TypeError, ValueError):
            return True
    return False


def _ratio(numerator, denominator) -> float | None:
    if _missing(numerator, denominator) or float(denominator) == 0:
        return None
    return float(numerator) / float(denominator)


def _signals(current: FundamentalsYear, prior: FundamentalsYear) -> dict[str, int | None]:
    out: dict[str, int | None] = {}

    # 1. ROA > 0
    roa_now = _ratio(current.net_income, current.total_assets)
    out["roa_positive"] = None if roa_now is None else int(roa_now > 0)

    # 2. Operating cash flow > 0
    out["cfo_positive"] = (
        None if _missing(current.operating_cf) else int(float(current.operating_cf) > 0)
    )

    # 3. ΔROA > 0
    roa_prior = _ratio(prior.net_income, prior.total_assets)
    out["roa_improved"] = (
        None if roa_now is None or roa_prior is None else int(roa_now > roa_prior)
    )

    # 4. Accruals: operating cash flow > net income
    out["accruals_ok"] = (
        None
        if _missing(current.operating_cf, current.net_income)
        else int(float(current.operating_cf) > float(current.net_income))
    )

    # 5. Δ leverage (long-term debt / assets) < 0
    lev_now = _ratio(current.long_term_debt, current.total_assets)
    lev_prior = _ratio(prior.long_term_debt, prior.total_assets)
    out["leverage_down"] = (
        None if lev_now is None or lev_prior is None else int(lev_now < lev_prior)
    )

    # 6. Δ current ratio > 0
    cr_now = _ratio(current.current_assets, current.current_liabilities)
    cr_prior = _ratio(prior.current_assets, prior.current_liabilities)
    out["current_ratio_up"] = (
        None if cr_now is None or cr_prior is None else int(cr_now > cr_prior)
    )

    # 7. No dilution: shares outstanding did not increase
    out["no_dilution"] = (
        None
        if _missing(current.shares_outstanding, prior.shares_outstanding)
        else int(float(current.shares_outstanding) <= float(prior.shares_outstanding))
    )

    # 8. Δ gross margin (gross profit / revenue) > 0
    gm_now = _ratio(current.gross_profit, current.revenue)
    gm_prior = _ratio(prior.gross_profit, prior.revenue)
    out["gross_margin_up"] = (
        None if gm_now is None or gm_prior is None else int(gm_now > gm_prior)
    )

    # 9. Δ asset turnover (revenue / assets) > 0
    at_now = _ratio(current.revenue, current.total_assets)
    at_prior = _ratio(prior.revenue, prior.total_assets)
    out["asset_turnover_up"] = (
        None if at_now is None or at_prior is None else int(at_now > at_prior)
    )

    return out


def f_score(
    current: FundamentalsYear, prior: FundamentalsYear
) -> tuple[int, int, dict[str, int | None]]:
    """Return (f_score 0-9, n_evaluable 0-9, per-signal map).

    f_score sums the signals that evaluated to 1; a missing signal (None)
    contributes nothing and lowers n_evaluable, so partial coverage can be
    reported honestly instead of as a false pass.
    """
    signals = _signals(current, prior)
    score = sum(1 for v in signals.values() if v == 1)
    evaluable = sum(1 for v in signals.values() if v is not None)
    return score, evaluable, signals


def f_score_from_mapping(
    current: dict, prior: dict
) -> tuple[int, int, dict[str, int | None]]:
    """Convenience wrapper: build FundamentalsYear from dicts (snapshot rows)."""
    allowed = {f.name for f in fields(FundamentalsYear)}
    cur = FundamentalsYear(**{k: current.get(k) for k in allowed})
    pri = FundamentalsYear(**{k: prior.get(k) for k in allowed})
    return f_score(cur, pri)
